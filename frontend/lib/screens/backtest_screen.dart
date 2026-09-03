/// Backtest view: replay the active rule set over historical bars.
///
/// The backend scores this with the SAME rule-evaluation function the live
/// engine uses, so these numbers describe the rules actually running.
library;

import 'package:flutter/material.dart';

import '../models/alert.dart';
import '../state/app_state.dart';

class BacktestScreen extends StatefulWidget {
  const BacktestScreen({super.key, required this.state});

  final AppState state;

  @override
  State<BacktestScreen> createState() => _BacktestScreenState();
}

class _BacktestScreenState extends State<BacktestScreen> {
  final _ticker = TextEditingController(text: 'AAPL');
  Direction _direction = Direction.bullish;
  Map<String, dynamic>? _result;
  String? _error;
  bool _running = false;

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  Future<void> _run() async {
    final ruleSets = widget.state.ruleSets;
    if (ruleSets.isEmpty) {
      setState(() => _error = 'No rule set available yet.');
      return;
    }
    final active = ruleSets.firstWhere(
      (r) => r.isActive,
      orElse: () => ruleSets.first,
    );

    setState(() {
      _running = true;
      _error = null;
    });
    try {
      final result = await widget.state.api.backtest(
        ticker: _ticker.text.trim().toUpperCase(),
        ruleSetId: active.id,
        direction: _direction,
      );
      if (mounted) setState(() => _result = result);
    } on Exception catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _running = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Backtest',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Replays your active rule set bar by bar. No look-ahead: each bar '
            'is judged only on data available at that moment.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SizedBox(
                width: 160,
                child: TextField(
                  controller: _ticker,
                  textCapitalization: TextCapitalization.characters,
                  decoration: const InputDecoration(labelText: 'Ticker'),
                ),
              ),
              SegmentedButton<Direction>(
                segments: const [
                  ButtonSegment(
                    value: Direction.bullish,
                    label: Text('Bullish'),
                  ),
                  ButtonSegment(
                    value: Direction.bearish,
                    label: Text('Bearish'),
                  ),
                ],
                selected: {_direction},
                showSelectedIcon: false,
                onSelectionChanged: (s) => setState(() => _direction = s.first),
              ),
              FilledButton.icon(
                onPressed: _running ? null : _run,
                icon: _running
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.play_arrow),
                label: const Text('Run'),
              ),
            ],
          ),
          const SizedBox(height: 20),
          if (_error != null)
            Text(_error!, style: TextStyle(color: theme.colorScheme.error)),
          if (_result != null) _Results(result: _result!),
        ],
      ),
    );
  }
}

class _Results extends StatelessWidget {
  const _Results({required this.result});

  final Map<String, dynamic> result;

  @override
  Widget build(BuildContext context) {
    final signals = (result['signals'] as List?) ?? const [];
    final hitRate = ((result['hit_rate'] as num? ?? 0) * 100).round();
    final avgMove = (result['average_move_pct'] as num? ?? 0).toDouble();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            _Stat(label: 'Signals', value: '${result['signal_count'] ?? 0}'),
            _Stat(label: 'Hit rate', value: '$hitRate%'),
            _Stat(label: 'Avg move', value: '${avgMove.toStringAsFixed(2)}%'),
            _Stat(label: 'Bars tested', value: '${result['bars_tested'] ?? 0}'),
          ],
        ),
        const SizedBox(height: 20),
        if (signals.isEmpty)
          const Text('This rule set never fired over the tested range.')
        else ...[
          Text('Signals', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              columnSpacing: 24,
              columns: const [
                DataColumn(label: Text('Bar')),
                DataColumn(label: Text('Entry')),
                DataColumn(label: Text('Exit')),
                DataColumn(label: Text('Move')),
                DataColumn(label: Text('Rules')),
              ],
              rows: [
                for (final s in signals.cast<Map<String, dynamic>>())
                  DataRow(
                    cells: [
                      DataCell(Text('${s['index']}')),
                      DataCell(Text('${s['entry_price']}')),
                      DataCell(Text('${s['exit_price']}')),
                      DataCell(
                        Text(
                          '${(s['move_pct'] as num).toStringAsFixed(2)}%',
                          style: TextStyle(
                            color: (s['favorable'] as bool? ?? false)
                                ? Colors.green
                                : Colors.red,
                          ),
                        ),
                      ),
                      DataCell(
                        Text(
                          (s['rule_tags'] as List)
                              .map((t) => RuleType.labelFor('$t'))
                              .join(', '),
                        ),
                      ),
                    ],
                  ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 130,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          const SizedBox(height: 4),
          Text(
            value,
            style: Theme.of(
              context,
            ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}
