/// Visual language for Confluence.
///
/// Dark-first: this is a tool traders keep open beside charting software, and a
/// bright panel in that context is genuinely unpleasant. Direction colour is
/// never the only signal -- every bullish/bearish cue is paired with an arrow
/// glyph and a text label, so the dashboard stays readable for red/green colour
/// blindness, which is common enough to matter in a finance tool.
library;

import 'package:flutter/material.dart';

class AppColors {
  const AppColors._();

  static const bullish = Color(0xFF10B981);
  static const bearish = Color(0xFFF43F5E);
  static const accent = Color(0xFF6366F1);

  static const surfaceDark = Color(0xFF12141A);
  static const cardDark = Color(0xFF1A1D26);
  static const borderDark = Color(0xFF272B36);

  /// Confidence bands used by the meter and the score chip.
  static Color forConfidence(double confidence) {
    if (confidence >= 0.75) return bullish;
    if (confidence >= 0.5) return const Color(0xFFF59E0B);
    return const Color(0xFF64748B);
  }
}

ThemeData buildDarkTheme() {
  final scheme = ColorScheme.fromSeed(
    seedColor: AppColors.accent,
    brightness: Brightness.dark,
  ).copyWith(surface: AppColors.surfaceDark);

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.surfaceDark,
    cardTheme: CardThemeData(
      color: AppColors.cardDark,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: AppColors.borderDark),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.cardDark,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.borderDark),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(10),
        borderSide: const BorderSide(color: AppColors.borderDark),
      ),
    ),
    chipTheme: ChipThemeData(
      side: const BorderSide(color: AppColors.borderDark),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
    ),
    dividerColor: AppColors.borderDark,
  );
}

ThemeData buildLightTheme() {
  return ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(seedColor: AppColors.accent),
    cardTheme: CardThemeData(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Colors.grey.shade300),
      ),
    ),
  );
}
