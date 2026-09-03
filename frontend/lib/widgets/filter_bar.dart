/// Dashboard filter controls.
///
/// Filtering is applied server-side; this widget only edits filter state and
/// hands it back. See `AppState.updateFilters`.
library;

import 'package:flutter/material.dart';

import '../models/alert.dart';
import '../state/app_state.dart';

class FilterBar extends StatelessWidget {
  const FilterBar({
    super.key,
    required this.filters,
    required this.watchlist,
    required this.onChanged,
    required this.onClear,
  });

  final AlertFilters filters;
  final List<WatchlistItem> watchlist;
  final ValueChanged<AlertFilters> onChanged;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            // "Confirmed only" vs also showing pending catalysts.
            SegmentedButton<bool>(
              segments: const [
                ButtonSegment(value: true, label: Text('Confirmed')),
                ButtonSegment(value: false, label: Text('Incl. pending')),
              ],
              selected: {filters.confirmedOnly},
              showSelectedIcon: false,
              onSelectionChanged: (s) =>
                  onChanged(filters.copyWith(confirmedOnly: s.first)),
            ),
            _DirectionFilter(
              direction: filters.direction,
              onChanged: (d) => onChanged(
                d == null
                    ? filters.copyWith(clearDirection: true)
                    : filters.copyWith(direction: d),
              ),
            ),
            DropdownMenu<String>(
              initialSelection: filters.sortBy,
              label: const Text('Sort'),
              width: 170,
              dropdownMenuEntries: const [
                DropdownMenuEntry(value: 'confidence', label: 'Confidence'),
                DropdownMenuEntry(value: 'recency', label: 'Most recent'),
              ],
              onSelected: (v) =>
                  v == null ? null : onChanged(filters.copyWith(sortBy: v)),
            ),
            if (filters.isActive)
              TextButton.icon(
                onPressed: onClear,
                icon: const Icon(Icons.clear, size: 16),
                label: const Text('Clear'),
              ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Text('Min confidence', style: theme.textTheme.labelMedium),
            Expanded(
              child: Slider(
                value: filters.minConfidence,
                divisions: 20,
                label: '${(filters.minConfidence * 100).round()}%',
                onChanged: (v) => onChanged(filters.copyWith(minConfidence: v)),
              ),
            ),
            SizedBox(
              width: 44,
              child: Text(
                '${(filters.minConfidence * 100).round()}%',
                style: theme.textTheme.labelMedium,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text('Catalyst type', style: theme.textTheme.labelMedium),
        const SizedBox(height: 6),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            for (final type in CatalystType.values)
              FilterChip(
                label: Text(type.label),
                selected: filters.catalystTypes.contains(type),
                onSelected: (selected) {
                  final next = [...filters.catalystTypes];
                  selected ? next.add(type) : next.remove(type);
                  onChanged(filters.copyWith(catalystTypes: next));
                },
              ),
          ],
        ),
        if (watchlist.isNotEmpty) ...[
          const SizedBox(height: 12),
          Text('Ticker', style: theme.textTheme.labelMedium),
          const SizedBox(height: 6),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final item in watchlist)
                FilterChip(
                  label: Text(item.ticker),
                  selected: filters.tickers.contains(item.ticker),
                  onSelected: (selected) {
                    final next = [...filters.tickers];
                    selected ? next.add(item.ticker) : next.remove(item.ticker);
                    onChanged(filters.copyWith(tickers: next));
                  },
                ),
            ],
          ),
        ],
      ],
    );
  }
}

class _DirectionFilter extends StatelessWidget {
  const _DirectionFilter({required this.direction, required this.onChanged});

  final Direction? direction;
  final ValueChanged<Direction?> onChanged;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<int>(
      segments: const [
        ButtonSegment(value: 0, label: Text('All')),
        ButtonSegment(value: 1, icon: Icon(Icons.trending_up, size: 16)),
        ButtonSegment(value: 2, icon: Icon(Icons.trending_down, size: 16)),
      ],
      selected: {
        switch (direction) {
          null => 0,
          Direction.bullish => 1,
          Direction.bearish => 2,
        },
      },
      showSelectedIcon: false,
      onSelectionChanged: (s) => onChanged(switch (s.first) {
        1 => Direction.bullish,
        2 => Direction.bearish,
        _ => null,
      }),
    );
  }
}
