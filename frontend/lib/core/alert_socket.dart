/// WebSocket channel for realtime alert push.
///
/// Reconnects with exponential backoff. Missing a push is not a correctness
/// problem: every alert is persisted server-side, so a reconnect followed by a
/// refresh recovers anything dropped while the socket was down.
library;

import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/alert.dart';

enum SocketStatus { disconnected, connecting, connected }

class AlertSocket {
  AlertSocket({required this.baseUrl});

  /// Same host as the API, e.g. http://127.0.0.1:8000
  final String baseUrl;

  static const _maxBackoff = Duration(seconds: 30);

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _reconnectTimer;
  String? _token;
  bool _closedByUser = false;
  int _attempt = 0;

  final _alerts = StreamController<Alert>.broadcast();
  final _status = StreamController<SocketStatus>.broadcast();

  /// Alerts pushed by the backend as they are confirmed.
  Stream<Alert> get alerts => _alerts.stream;

  /// Connection state, for the status indicator in the app bar.
  Stream<SocketStatus> get status => _status.stream;

  /// The token goes in the query string because WebSocket clients cannot set
  /// an Authorization header.
  Uri _socketUri(String token) {
    final base = Uri.parse(baseUrl);
    return base.replace(
      scheme: base.scheme == 'https' ? 'wss' : 'ws',
      path: '/ws/alerts',
      queryParameters: {'token': token},
    );
  }

  void connect(String token) {
    _token = token;
    _closedByUser = false;
    _attempt = 0;
    _open();
  }

  void _open() {
    final token = _token;
    if (token == null || _closedByUser) return;

    _status.add(SocketStatus.connecting);
    try {
      final channel = WebSocketChannel.connect(_socketUri(token));
      _channel = channel;
      _subscription = channel.stream.listen(
        _onMessage,
        onDone: _scheduleReconnect,
        onError: (_) => _scheduleReconnect(),
        cancelOnError: true,
      );
      _status.add(SocketStatus.connected);
      _attempt = 0;
    } on Exception {
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic raw) {
    try {
      final decoded = jsonDecode(raw as String);
      if (decoded is Map<String, dynamic> && decoded['type'] == 'alert') {
        _alerts.add(Alert.fromJson(decoded['data'] as Map<String, dynamic>));
      }
    } on FormatException {
      // A malformed frame is not worth tearing the connection down for.
    }
  }

  void _scheduleReconnect() {
    _status.add(SocketStatus.disconnected);
    _subscription?.cancel();
    _subscription = null;
    _channel = null;
    if (_closedByUser) return;

    // 1s, 2s, 4s ... capped at 30s.
    final seconds = (1 << _attempt).clamp(1, _maxBackoff.inSeconds);
    _attempt = (_attempt + 1).clamp(0, 5);
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(Duration(seconds: seconds), _open);
  }

  Future<void> disconnect() async {
    _closedByUser = true;
    _reconnectTimer?.cancel();
    await _subscription?.cancel();
    await _channel?.sink.close();
    _channel = null;
    _status.add(SocketStatus.disconnected);
  }

  Future<void> dispose() async {
    await disconnect();
    await _alerts.close();
    await _status.close();
  }
}
