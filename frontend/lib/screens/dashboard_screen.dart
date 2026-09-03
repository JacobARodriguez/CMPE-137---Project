/// The dashboard: a responsive grid of confirmed-alert cards.
library;

import 'package:flutter/material.dart';

import '../core/alert_socket.dart';
import '../models/alert.dart';
import '../state/app_state.dart';
import '../widgets/alert_card.dart';
import '../widgets/filter_bar.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key, required this.state});

  final AppState state;

  /// Card columns by width. Desktop is the primary target, so wide layouts get
  /// real use out of the space rather than one stretched column.
  int _columnsFor(double width) {
    if (width >= 1600) return 4;
    if (width >= 1150) return 3;
    if (width >= 760) return 2;
    return 1;
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: state,
      builder: (context, _) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _Header(state: state),
            const Divider(height: 1),
            Expanded(
              child: RefreshIndicator(
                onRefresh: state.refreshAlerts,
                child: CustomScrollView(
                  slivers: [
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                      sliver: SliverToBoxAdapter(
                        child: FilterBar(
                          filters: state.filters,
                          watchlist: state.watchlist,
                          onChanged: state.updateFilters,
                          onClear: state.clearFilters,
                        ),
                      ),
                    ),
                    if (state.errorMessage != null)
                      SliverToBoxAdapter(
                        child: _ErrorBanner(message: state.errorMessage!),
                      ),
                    if (state.isLoading && state.alerts.isEmpty)
                      const SliverFillRemaining(
                        hasScrollBody: false,
                        child: Center(child: CircularProgressIndicator()),
                      )
                    else if (state.alerts.isEmpty)
                      SliverFillRemaining(
                        hasScrollBody: false,
                        child: _EmptyState(hasFilters: state.filters.isActive),
                      )
                    else
                      SliverPadding(
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                        // SliverLayoutBuilder, not LayoutBuilder: inside a
                        // sliver we need SliverConstraints to read the real
                        // cross-axis width.
                        sliver: SliverLayoutBuilder(
                          builder: (context, constraints) {
                            return SliverGrid(
                              gridDelegate:
                                  SliverGridDelegateWithFixedCrossAxisCount(
                                    crossAxisCount: _columnsFor(
                                      constraints.crossAxisExtent,
                                    ),
                                    mainAxisSpacing: 12,
                                    crossAxisSpacing: 12,
                                    mainAxisExtent: 260,
                                  ),
                              delegate: SliverChildBuilderDelegate((
                                context,
                                index,
                              ) {
                                final alert = state.alerts[index];
                                return AlertCard(
                                  alert: alert,
                                  isNew: state.unseenAlertIds.contains(
                                    alert.id,
                                  ),
                                );
                              }, childCount: state.alerts.length),
                            );
                          },
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.state});

  final AppState state;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final confirmed = state.alerts
        .where((a) => a.status == AlertStatus.confirmed)
        .length;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 12),
      child: Row(
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Confirmed alerts',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                '$confirmed signal${confirmed == 1 ? '' : 's'} '
                'across ${state.watchlist.length} watched ticker'
                '${state.watchlist.length == 1 ? '' : 's'}',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
          const Spacer(),
          _SocketIndicator(status: state.socketStatus),
          const SizedBox(width: 12),
          IconButton(
            tooltip: 'Refresh',
            onPressed: state.isLoading ? null : state.refreshAlerts,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
    );
  }
}

/// Live-connection indicator. Traders need to know at a glance whether the
/// feed is actually live -- a silent dashboard and a dead socket look identical
/// otherwise.
class _SocketIndicator extends StatelessWidget {
  const _SocketIndicator({required this.status});

  final SocketStatus status;

  @override
  Widget build(BuildContext context) {
    final (color, label) = switch (status) {
      SocketStatus.connected => (Colors.green, 'Live'),
      SocketStatus.connecting => (Colors.amber, 'Connecting'),
      SocketStatus.disconnected => (Colors.grey, 'Offline'),
    };
    return Tooltip(
      message: 'Realtime alert feed: $label',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 6),
          Text(label, style: Theme.of(context).textTheme.labelSmall),
        ],
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.errorContainer,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            const Icon(Icons.error_outline, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.hasFilters});

  final bool hasFilters;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              hasFilters ? Icons.filter_alt_off : Icons.radar,
              size: 44,
              color: theme.colorScheme.onSurfaceVariant,
            ),
            const SizedBox(height: 12),
            Text(
              hasFilters ? 'No alerts match these filters' : 'Watching for confluence',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 6),
            Text(
              hasFilters
                  ? 'Try lowering the minimum confidence or clearing a filter.'
                  : 'An alert fires when a catalyst and one of your technical '
                        'rules line up inside the confirmation window.',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
