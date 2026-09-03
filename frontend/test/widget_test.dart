/// Widget tests. These run without a backend: the app must render its login
/// screen and its dashboard states offline.
library;

import 'package:confluence/core/alert_socket.dart';
import 'package:confluence/core/api_client.dart';
import 'package:confluence/models/alert.dart';
import 'package:confluence/screens/dashboard_screen.dart';
import 'package:confluence/state/app_state.dart';
import 'package:confluence/widgets/alert_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

Alert _alert({
  int id = 1,
  String ticker = 'AAPL',
  Direction direction = Direction.bullish,
  double confidence = 0.87,
}) {
  return Alert(
    id: id,
    ticker: ticker,
    direction: direction,
    confidence: confidence,
    why: 'Earnings beat by 12%. Confirmed bullish by: opening range breakout.',
    catalystType: CatalystType.earningsSurprise,
    ruleTags: const ['orb', 'volume_spike'],
    status: AlertStatus.confirmed,
    createdAt: DateTime(2026, 9, 3, 14, 30),
  );
}

AppState _state() => AppState(
  api: ApiClient(baseUrl: 'http://127.0.0.1:1'),
  socket: AlertSocket(baseUrl: 'http://127.0.0.1:1'),
);

void main() {
  group('AlertCard', () {
    testWidgets('shows ticker, direction, confidence and rule tags', (
      tester,
    ) async {
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: AlertCard(alert: _alert()))),
      );

      expect(find.text('AAPL'), findsOneWidget);
      expect(find.text('Bullish'), findsOneWidget);
      expect(find.text('87%'), findsOneWidget);
      expect(find.text('Earnings'), findsOneWidget);
      expect(find.text('ORB'), findsOneWidget);
      expect(find.text('Volume spike'), findsOneWidget);
    });

    testWidgets('bearish alerts read as bearish', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AlertCard(alert: _alert(direction: Direction.bearish)),
          ),
        ),
      );
      expect(find.text('Bearish'), findsOneWidget);
      expect(find.byIcon(Icons.trending_down), findsOneWidget);
    });

    testWidgets('direction is never conveyed by colour alone', (tester) async {
      // Accessibility: an arrow icon and a text label must accompany the hue.
      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: AlertCard(alert: _alert()))),
      );
      expect(find.byIcon(Icons.trending_up), findsOneWidget);
      expect(find.text('Bullish'), findsOneWidget);
    });

    testWidgets('new alerts are badged', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: AlertCard(alert: _alert(), isNew: true)),
        ),
      );
      expect(find.text('NEW'), findsOneWidget);
    });
  });

  group('Alert parsing', () {
    test('round-trips the backend payload shape', () {
      final alert = Alert.fromJson({
        'id': 7,
        'ticker': 'TSLA',
        'direction': 'bearish',
        'confidence': 0.42,
        'why': 'why text',
        'catalyst_type': 'options_flow',
        'rule_tags': ['vwap_reclaim'],
        'status': 'confirmed',
        'created_at': '2026-09-03T14:30:00+00:00',
      });

      expect(alert.id, 7);
      expect(alert.ticker, 'TSLA');
      expect(alert.direction, Direction.bearish);
      expect(alert.confidencePercent, 42);
      expect(alert.catalystType, CatalystType.optionsFlow);
      expect(alert.ruleTags, ['vwap_reclaim']);
    });

    test('unknown catalyst type degrades instead of throwing', () {
      final alert = Alert.fromJson({
        'id': 1,
        'ticker': 'X',
        'direction': 'bullish',
        'confidence': 0.1,
        'why': '',
        'catalyst_type': 'something_new_from_the_backend',
        'rule_tags': <String>[],
        'status': 'confirmed',
        'created_at': '2026-09-03T14:30:00Z',
      });
      expect(alert.catalystType, CatalystType.news);
    });
  });

  group('AlertFilters', () {
    test('starts inactive and reports activity once set', () {
      const filters = AlertFilters();
      expect(filters.isActive, isFalse);
      expect(filters.copyWith(minConfidence: 0.5).isActive, isTrue);
      expect(filters.copyWith(confirmedOnly: false).isActive, isTrue);
    });

    test('clearDirection removes the direction filter', () {
      const filters = AlertFilters(direction: Direction.bullish);
      expect(filters.copyWith(clearDirection: true).direction, isNull);
    });
  });

  group('DashboardScreen', () {
    testWidgets('renders an empty state with no alerts', (tester) async {
      final state = _state();
      addTearDown(state.dispose);

      await tester.pumpWidget(
        MaterialApp(home: Scaffold(body: DashboardScreen(state: state))),
      );
      await tester.pump();

      expect(find.text('Watching for confluence'), findsOneWidget);
    });
  });
}
