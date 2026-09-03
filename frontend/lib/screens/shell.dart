/// Responsive app shell.
///
/// NavigationRail on wide screens (the Windows desktop target), NavigationBar
/// on narrow ones (mobile). One breakpoint, one widget tree -- no separate
/// mobile and desktop implementations to keep in sync.
library;

import 'package:flutter/material.dart';

import '../state/app_state.dart';
import 'backtest_screen.dart';
import 'dashboard_screen.dart';
import 'rules_screen.dart';
import 'watchlist_screen.dart';

/// Below this width, use a bottom NavigationBar.
const double kWideLayoutBreakpoint = 900;

class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.state});

  final AppState state;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;

  static const _destinations = [
    (icon: Icons.dashboard_outlined, selected: Icons.dashboard, label: 'Dashboard'),
    (icon: Icons.list_alt_outlined, selected: Icons.list_alt, label: 'Watchlist'),
    (icon: Icons.rule_outlined, selected: Icons.rule, label: 'Rules'),
    (icon: Icons.query_stats_outlined, selected: Icons.query_stats, label: 'Backtest'),
  ];

  Widget _screenFor(int index) => switch (index) {
    1 => WatchlistScreen(state: widget.state),
    2 => RulesScreen(state: widget.state),
    3 => BacktestScreen(state: widget.state),
    _ => DashboardScreen(state: widget.state),
  };

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.sizeOf(context).width >= kWideLayoutBreakpoint;
    final body = _screenFor(_index);

    if (isWide) {
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              selectedIndex: _index,
              onDestinationSelected: (i) => setState(() => _index = i),
              labelType: NavigationRailLabelType.all,
              leading: const Padding(
                padding: EdgeInsets.symmetric(vertical: 16),
                child: _Logo(),
              ),
              trailing: Expanded(
                child: Align(
                  alignment: Alignment.bottomCenter,
                  child: Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: IconButton(
                      tooltip: 'Sign out',
                      onPressed: widget.state.logout,
                      icon: const Icon(Icons.logout),
                    ),
                  ),
                ),
              ),
              destinations: [
                for (final d in _destinations)
                  NavigationRailDestination(
                    icon: Icon(d.icon),
                    selectedIcon: Icon(d.selected),
                    label: Text(d.label),
                  ),
              ],
            ),
            const VerticalDivider(width: 1),
            Expanded(child: SafeArea(child: body)),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(_destinations[_index].label),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            onPressed: widget.state.logout,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SafeArea(child: body),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [
          for (final d in _destinations)
            NavigationDestination(
              icon: Icon(d.icon),
              selectedIcon: Icon(d.selected),
              label: d.label,
            ),
        ],
      ),
    );
  }
}

class _Logo extends StatelessWidget {
  const _Logo();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Icon(Icons.hub, color: Theme.of(context).colorScheme.primary),
        const SizedBox(height: 4),
        const Text(
          'Confluence',
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
        ),
      ],
    );
  }
}
