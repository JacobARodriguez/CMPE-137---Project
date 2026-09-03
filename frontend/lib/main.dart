/// Confluence - Flutter client.
///
/// Windows desktop is the primary target; mobile is secondary. Layout adapts at
/// a single breakpoint (see `AppShell`) rather than branching into separate
/// desktop and mobile trees.
library;

import 'package:flutter/material.dart';

import 'core/alert_socket.dart';
import 'core/api_client.dart';
import 'core/theme.dart';
import 'screens/login_screen.dart';
import 'screens/shell.dart';
import 'state/app_state.dart';

/// Backend base URL.
///
/// Override without editing code:
///   flutter run --dart-define=CONFLUENCE_API=http://192.168.1.20:8000
///
/// 127.0.0.1 works for Windows desktop and iOS simulator. The Android emulator
/// reaches the host machine at 10.0.2.2, so pass --dart-define there.
const String kApiBaseUrl = String.fromEnvironment(
  'CONFLUENCE_API',
  defaultValue: 'http://127.0.0.1:8000',
);

void main() {
  runApp(const ConfluenceApp());
}

class ConfluenceApp extends StatefulWidget {
  const ConfluenceApp({super.key});

  @override
  State<ConfluenceApp> createState() => _ConfluenceAppState();
}

class _ConfluenceAppState extends State<ConfluenceApp> {
  late final AppState _state;

  @override
  void initState() {
    super.initState();
    _state = AppState(
      api: ApiClient(baseUrl: kApiBaseUrl),
      socket: AlertSocket(baseUrl: kApiBaseUrl),
    );
  }

  @override
  void dispose() {
    _state.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Confluence',
      debugShowCheckedModeBanner: false,
      theme: buildLightTheme(),
      darkTheme: buildDarkTheme(),
      themeMode: ThemeMode.dark,
      home: ListenableBuilder(
        listenable: _state,
        builder: (context, _) => _state.isAuthenticated
            ? AppShell(state: _state)
            : LoginScreen(state: _state),
      ),
    );
  }
}
