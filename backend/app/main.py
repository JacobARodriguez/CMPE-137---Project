"""FastAPI application: routes, WebSocket channel, and the polling loop."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings, warn_if_insecure
from app.db.session import dispose_engine, get_session_factory, init_db
from app.pipeline.ranking import build_ranker
from app.pipeline.runner import PipelineRunner, group_watchers
from app.pipeline.windows import build_window_store
from app.realtime.hub import hub
from app.repository import alert_to_payload, load_watchers, persist_alert
from app.schemas import HealthResponse
from app.security import decode_access_token
from app.services.registry import build_services

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def poll_loop(app: FastAPI) -> None:
    """Run the pipeline forever, once per POLL_INTERVAL_SECONDS.

    One cycle: load every (ticker, user, rule set) triple, run the pipeline
    (which polls each ticker exactly once), persist the alerts, push them.
    """
    settings = get_settings()
    runner: PipelineRunner = app.state.runner
    session_factory = get_session_factory()

    while True:
        try:
            async with session_factory() as session:
                rows = await load_watchers(session)
                if not rows:
                    await asyncio.sleep(settings.poll_interval_seconds)
                    continue

                alerts, report = await runner.run_cycle(group_watchers(rows))

                payloads: dict[int, list[dict]] = {}
                for alert in alerts:
                    row = await persist_alert(session, alert)
                    payloads.setdefault(alert.user_id, []).append(alert_to_payload(row))
                await session.commit()

            delivered = await hub.broadcast(payloads)
            app.state.last_cycle = report
            logger.info(
                "cycle: tickers=%d fetches=%d catalysts=%d evals=%d alerts=%d pushed=%d",
                report.tickers_polled,
                report.external_fetches,
                report.catalysts_detected,
                report.rule_evaluations,
                report.alerts_confirmed,
                delivered,
            )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the loop must survive a bad cycle
            logger.exception("Poll cycle failed; continuing")

        await asyncio.sleep(settings.poll_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()

    services = build_services(settings)
    window_store = await build_window_store(settings.redis_url)
    app.state.services = services
    app.state.window_store = window_store
    app.state.runner = PipelineRunner(
        services, window_store, build_ranker(), bar_lookback=settings.bar_lookback
    )
    app.state.last_cycle = None

    for problem in warn_if_insecure(settings):
        logger.warning("INSECURE CONFIG: %s", problem)
    logger.info("Providers: %s", services.selection)
    task = asyncio.create_task(poll_loop(app))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await dispose_engine()


app = FastAPI(
    title="Confluence API",
    version="0.1.0",
    description=(
        "Short-term trade signals from aligned fundamental catalysts and "
        "technical confirmation."
    ),
    lifespan=lifespan,
)

# The Flutter desktop/mobile client is a separate origin. Tighten before deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Reports which providers are live -- mock vs real is never a mystery."""
    services = getattr(app.state, "services", None)
    window_store = getattr(app.state, "window_store", None)
    return HealthResponse(
        status="ok",
        environment=get_settings().confluence_env,
        services=services.selection if services else {},
        window_store=type(window_store).__name__ if window_store else "uninitialised",
    )


@app.websocket("/ws/alerts")
async def alerts_socket(websocket: WebSocket, token: str = "") -> None:
    """Realtime alert channel.

    The token arrives as a query parameter because browser WebSocket clients
    cannot set an Authorization header.
    """
    settings = get_settings()
    user_id = decode_access_token(token, settings.secret_key) if token else None
    if user_id is None:
        await websocket.close(code=4401)  # application-level "unauthorized"
        return

    await websocket.accept()
    await hub.connect(user_id, websocket)
    try:
        while True:
            # No inbound protocol yet; this keeps the socket open and detects
            # disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(user_id, websocket)
