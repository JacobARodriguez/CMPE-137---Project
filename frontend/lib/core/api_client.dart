/// HTTP client for the Confluence backend.
///
/// The client NEVER calls an external market-data provider. Every quote,
/// filing, and options print comes from our own backend, which polls each
/// ticker once and fans the result out. That rule is what keeps API costs flat
/// as users are added, so please keep it: no third-party URLs in this file.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/alert.dart';

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);

  final int statusCode;
  final String message;

  bool get isUnauthorized => statusCode == 401;

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiClient {
  ApiClient({required this.baseUrl, http.Client? httpClient})
    : _http = httpClient ?? http.Client();

  /// e.g. http://127.0.0.1:8000
  final String baseUrl;
  final http.Client _http;

  String? _token;

  bool get isAuthenticated => _token != null;

  /// Bearer token from login/register. Cleared on 401.
  set token(String? value) => _token = value;

  Map<String, String> get _headers => {
    'Content-Type': 'application/json',
    if (_token != null) 'Authorization': 'Bearer $_token',
  };

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final normalised = query?.map(
      (key, value) => MapEntry(
        key,
        value is List ? value.map((e) => e.toString()).toList() : '$value',
      ),
    );
    return Uri.parse('$baseUrl$path').replace(queryParameters: normalised);
  }

  dynamic _decode(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    }
    if (response.statusCode == 401) _token = null;

    String message = response.reasonPhrase ?? 'Request failed';
    try {
      final body = jsonDecode(response.body);
      if (body is Map && body['detail'] != null) {
        message = body['detail'].toString();
      }
    } on FormatException {
      // Non-JSON error body; the reason phrase is the best we have.
    }
    throw ApiException(response.statusCode, message);
  }

  // ------------------------------------------------------------------ auth --

  Future<String> register(String email, String password) async {
    final body = _decode(
      await _http.post(
        _uri('/auth/register'),
        headers: _headers,
        body: jsonEncode({'email': email, 'password': password}),
      ),
    );
    return _token = body['access_token'] as String;
  }

  Future<String> login(String email, String password) async {
    final body = _decode(
      await _http.post(
        _uri('/auth/login'),
        headers: _headers,
        body: jsonEncode({'email': email, 'password': password}),
      ),
    );
    return _token = body['access_token'] as String;
  }

  void logout() => _token = null;

  // ---------------------------------------------------------------- alerts --

  /// The dashboard query. Filtering happens server-side so the client never
  /// downloads alerts it will immediately hide.
  Future<List<Alert>> fetchAlerts({
    List<String>? tickers,
    List<CatalystType>? catalystTypes,
    Direction? direction,
    double minConfidence = 0.0,
    bool confirmedOnly = true,
    String sortBy = 'confidence',
    int limit = 100,
  }) async {
    final body = _decode(
      await _http.get(
        _uri('/alerts', {
          if (tickers != null && tickers.isNotEmpty) 'tickers': tickers,
          if (catalystTypes != null && catalystTypes.isNotEmpty)
            'catalyst_types': catalystTypes.map((c) => c.wire).toList(),
          if (direction != null) 'direction': direction.name,
          'min_confidence': minConfidence,
          'confirmed_only': confirmedOnly,
          'sort_by': sortBy,
          'limit': limit,
        }),
        headers: _headers,
      ),
    );
    return (body as List)
        .map((e) => Alert.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ------------------------------------------------------------- watchlist --

  Future<List<WatchlistItem>> fetchWatchlist() async {
    final body = _decode(
      await _http.get(_uri('/watchlist'), headers: _headers),
    );
    return (body as List)
        .map((e) => WatchlistItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<WatchlistItem> addTicker(String ticker, {String? sector}) async {
    final body = _decode(
      await _http.post(
        _uri('/watchlist'),
        headers: _headers,
        body: jsonEncode({'ticker': ticker, 'sector': sector}),
      ),
    );
    return WatchlistItem.fromJson(body as Map<String, dynamic>);
  }

  Future<void> removeTicker(String ticker) async {
    _decode(await _http.delete(_uri('/watchlist/$ticker'), headers: _headers));
  }

  // ------------------------------------------------------------- rule sets --

  Future<List<RuleSet>> fetchRuleSets() async {
    final body = _decode(
      await _http.get(_uri('/rule-sets'), headers: _headers),
    );
    return (body as List)
        .map((e) => RuleSet.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<RuleSet> activateRuleSet(int id) async {
    final body = _decode(
      await _http.post(_uri('/rule-sets/$id/activate'), headers: _headers),
    );
    return RuleSet.fromJson(body as Map<String, dynamic>);
  }

  // -------------------------------------------------------------- backtest --

  Future<Map<String, dynamic>> backtest({
    required String ticker,
    required int ruleSetId,
    Direction direction = Direction.bullish,
    int horizonBars = 15,
    int bars = 200,
  }) async {
    final body = _decode(
      await _http.post(
        _uri('/backtest'),
        headers: _headers,
        body: jsonEncode({
          'ticker': ticker,
          'rule_set_id': ruleSetId,
          'direction': direction.name,
          'horizon_bars': horizonBars,
          'bars': bars,
        }),
      ),
    );
    return body as Map<String, dynamic>;
  }

  // ---------------------------------------------------------------- system --

  Future<Map<String, dynamic>> health() async {
    final body = _decode(await _http.get(_uri('/health')));
    return body as Map<String, dynamic>;
  }

  void dispose() => _http.close();
}
