/// Watchlist management: add and remove tickers.
library;

import 'package:flutter/material.dart';

import '../state/app_state.dart';

class WatchlistScreen extends StatefulWidget {
  const WatchlistScreen({super.key, required this.state});

  final AppState state;

  @override
  State<WatchlistScreen> createState() => _WatchlistScreenState();
}

class _WatchlistScreenState extends State<WatchlistScreen> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _add() async {
    final ticker = _controller.text.trim();
    if (ticker.isEmpty) return;
    await widget.state.addTicker(ticker);
    _controller.clear();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListenableBuilder(
      listenable: widget.state,
      builder: (context, _) {
        final watchlist = widget.state.watchlist;
        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Watchlist',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'The backend polls each of these once per interval, no matter '
                'how many people watch it.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      textCapitalization: TextCapitalization.characters,
                      decoration: const InputDecoration(
                        labelText: 'Add ticker',
                        hintText: 'AAPL',
                        prefixIcon: Icon(Icons.add),
                      ),
                      onSubmitted: (_) => _add(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(onPressed: _add, child: const Text('Add')),
                ],
              ),
              const SizedBox(height: 16),
              Expanded(
                child: watchlist.isEmpty
                    ? Center(
                        child: Text(
                          'No tickers yet. Add one above to start receiving alerts.',
                          style: theme.textTheme.bodyMedium,
                        ),
                      )
                    : ListView.separated(
                        itemCount: watchlist.length,
                        separatorBuilder: (context, index) =>
                            const Divider(height: 1),
                        itemBuilder: (context, i) {
                          final item = watchlist[i];
                          return ListTile(
                            leading: CircleAvatar(
                              child: Text(
                                item.ticker.substring(0, 1),
                                style: const TextStyle(fontSize: 14),
                              ),
                            ),
                            title: Text(
                              item.ticker,
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            subtitle: item.sector == null
                                ? null
                                : Text(item.sector!),
                            trailing: IconButton(
                              tooltip: 'Remove',
                              icon: const Icon(Icons.delete_outline),
                              onPressed: () =>
                                  widget.state.removeTicker(item.ticker),
                            ),
                          );
                        },
                      ),
              ),
            ],
          ),
        );
      },
    );
  }
}
