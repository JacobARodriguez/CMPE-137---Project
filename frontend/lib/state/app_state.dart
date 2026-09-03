/// Application state.
///
/// Plain `ChangeNotifier` with `ListenableBuilder` -- no state-management
/// package. For an app this size that is less machinery to learn and one fewer
/// dependency to keep current; swap in Riverpod later if the tree outgrows it.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../core/alert_socket.dart';
import '../core/api_client.dart';
import '../models/alert.dart';

/// Dashboard filter state. Mirrors `AlertFilters` in the backend schemas.
class AlertFilters {
  const AlertFilters({
    this.tickers = const [],
    this.catalystTypes = const [],
    this.direction,
    this.minConfidence = 0.0,
    this.confirmedOnly = true,
    this.sortBy = 'confidence',
  });

  final List<String> tickers;
  final List<CatalystType> catalystTypes;
  final Direction? direction;
  final double minConfidence;

  /// False also shows catalysts still inside their confirmation window.
  final bool confirmedOnly;

  /// "confidence" or "recency".
  final String sortBy;

  bool get isActive =>
      tickers.isNotEmpty ||
      catalystTypes.isNotEmpty ||
      direction != null ||
      minConfidence > 0 ||
      !confirmedOnly;

  AlertFilters copyWith({
    List<String>? tickers,
    List<CatalystType>? catalystTypes,
    Direction? direction,
    bool clearDirection = false,
    double? minConfidence,
    bool? confirmedOnly,
    String? sortBy,
  }) {
    return AlertFilters(
      tickers: tickers ?? this.tickers,
      catalystTypes: catalystTypes ?? this.catalystTypes,
      direction: clearDirection ? null : (direction ?? this.direction),
      minConfidence: minConfidence ?? this.minConfidence,
      confirmedOnly: confirmedOnly ?? this.confirmedOnly,
      sortBy: sortBy ?? this.sortBy,
    );
  }
}

class AppState extends ChangeNotifier {
  AppState({required this.api, required this.socket}) {
    _socketSub = socket.alerts.listen(_onPushedAlert);
    _statusSub = socket.status.listen((s) {
      socketStatus = s;
      notifyListeners();
    });
  }

  final ApiClient api;
  final AlertSocket socket;

  late final StreamSubscription<Alert> _socketSub;
  late final StreamSubscription<SocketStatus> _statusSub;

  bool isAuthenticated = false;
  bool isLoading = false;
  String? errorMessage;
  SocketStatus socketStatus = SocketStatus.disconnected;

  List<Alert> alerts = [];
  List<WatchlistItem> watchlist = [];
  List<RuleSet> ruleSets = [];
  AlertFilters filters = const AlertFilters();

  /// Alerts that arrived over the socket since the last manual refresh, so the
  /// UI can badge them as new.
  final Set<int> unseenAlertIds = {};

  // -------------------------------------------------------------- auth -----

  Future<bool> login(String email, String password) =>
      _authenticate(() => api.login(email, password));

  Future<bool> register(String email, String password) =>
      _authenticate(() => api.register(email, password));

  Future<bool> _authenticate(Future<String> Function() action) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();
    try {
      final token = await action();
      isAuthenticated = true;
      socket.connect(token);
      await refreshAll();
      return true;
    } on ApiException catch (e) {
      errorMessage = e.message;
      return false;
    } on Exception catch (e) {
      errorMessage = 'Could not reach the server. $e';
      return false;
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    await socket.disconnect();
    api.logout();
    isAuthenticated = false;
    alerts = [];
    watchlist = [];
    ruleSets = [];
    unseenAlertIds.clear();
    notifyListeners();
  }

  // ------------------------------------------------------------- data ------

  Future<void> refreshAll() async {
    await Future.wait([refreshAlerts(), refreshWatchlist(), refreshRuleSets()]);
  }

  Future<void> refreshAlerts() async {
    isLoading = true;
    notifyListeners();
    try {
      alerts = await api.fetchAlerts(
        tickers: filters.tickers,
        catalystTypes: filters.catalystTypes,
        direction: filters.direction,
        minConfidence: filters.minConfidence,
        confirmedOnly: filters.confirmedOnly,
        sortBy: filters.sortBy,
      );
      unseenAlertIds.clear();
      errorMessage = null;
    } on ApiException catch (e) {
      errorMessage = e.message;
      if (e.isUnauthorized) isAuthenticated = false;
    } on Exception catch (e) {
      errorMessage = 'Could not load alerts. $e';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<void> refreshWatchlist() async {
    try {
      watchlist = await api.fetchWatchlist();
    } on Exception {
      // The dashboard is still usable without the watchlist sidebar.
    }
    notifyListeners();
  }

  Future<void> refreshRuleSets() async {
    try {
      ruleSets = await api.fetchRuleSets();
    } on Exception {
      // Non-fatal for the dashboard.
    }
    notifyListeners();
  }

  Future<void> addTicker(String ticker) async {
    try {
      final item = await api.addTicker(ticker.trim().toUpperCase());
      watchlist = [...watchlist, item]
        ..sort((a, b) => a.ticker.compareTo(b.ticker));
      errorMessage = null;
    } on ApiException catch (e) {
      errorMessage = e.message;
    }
    notifyListeners();
  }

  Future<void> removeTicker(String ticker) async {
    try {
      await api.removeTicker(ticker);
      watchlist = watchlist.where((w) => w.ticker != ticker).toList();
    } on ApiException catch (e) {
      errorMessage = e.message;
    }
    notifyListeners();
  }

  Future<void> activateRuleSet(int id) async {
    try {
      await api.activateRuleSet(id);
      await refreshRuleSets();
    } on ApiException catch (e) {
      errorMessage = e.message;
      notifyListeners();
    }
  }

  // ----------------------------------------------------------- filters -----

  void updateFilters(AlertFilters next) {
    filters = next;
    notifyListeners();
    refreshAlerts();
  }

  void clearFilters() => updateFilters(const AlertFilters());

  // ------------------------------------------------------------ socket -----

  void _onPushedAlert(Alert alert) {
    // Drop a push that the current filters would hide, so the list stays
    // consistent with what the user asked to see.
    if (!_matchesFilters(alert)) return;

    alerts = [alert, ...alerts.where((a) => a.id != alert.id)];
    if (filters.sortBy == 'confidence') {
      alerts.sort((a, b) => b.confidence.compareTo(a.confidence));
    }
    unseenAlertIds.add(alert.id);
    notifyListeners();
  }

  bool _matchesFilters(Alert alert) {
    if (filters.confirmedOnly && alert.status != AlertStatus.confirmed) {
      return false;
    }
    if (filters.direction != null && alert.direction != filters.direction) {
      return false;
    }
    if (alert.confidence < filters.minConfidence) return false;
    if (filters.tickers.isNotEmpty && !filters.tickers.contains(alert.ticker)) {
      return false;
    }
    if (filters.catalystTypes.isNotEmpty &&
        !filters.catalystTypes.contains(alert.catalystType)) {
      return false;
    }
    return true;
  }

  @override
  void dispose() {
    _socketSub.cancel();
    _statusSub.cancel();
    socket.dispose();
    api.dispose();
    super.dispose();
  }
}
