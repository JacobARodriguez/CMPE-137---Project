/// Client-side mirrors of the backend's Pydantic schemas.
///
/// Field names here must match `backend/app/schemas.py` exactly. Renaming a
/// field on either side is a breaking change.
library;

enum Direction { bullish, bearish }

enum AlertStatus { pending, confirmed, expired }

enum CatalystType {
  earningsSurprise('earnings_surprise', 'Earnings'),
  insiderBuy('insider_buy', 'Insider buy'),
  insiderSell('insider_sell', 'Insider sell'),
  optionsFlow('options_flow', 'Options flow'),
  filing8k('filing_8k', '8-K filing'),
  news('news', 'News');

  const CatalystType(this.wire, this.label);

  /// The value used on the wire; matches the backend enum.
  final String wire;

  /// Human-readable label for chips and filters.
  final String label;

  static CatalystType fromWire(String value) => CatalystType.values.firstWhere(
    (t) => t.wire == value,
    orElse: () => CatalystType.news,
  );
}

enum RuleType {
  orb('orb', 'ORB'),
  emaCross('ema_cross', 'EMA cross'),
  volumeSpike('volume_spike', 'Volume spike'),
  vwapReclaim('vwap_reclaim', 'VWAP');

  const RuleType(this.wire, this.label);

  final String wire;
  final String label;

  static String labelFor(String wire) => RuleType.values
      .firstWhere(
        (r) => r.wire == wire,
        orElse: () => RuleType.orb,
      )
      .label;
}

/// One confirmed signal -- a dashboard card.
class Alert {
  const Alert({
    required this.id,
    required this.ticker,
    required this.direction,
    required this.confidence,
    required this.why,
    required this.catalystType,
    required this.ruleTags,
    required this.status,
    required this.createdAt,
  });

  final int id;
  final String ticker;
  final Direction direction;

  /// 0..1 ranking score.
  final double confidence;

  /// Plain-English explanation built by the backend ranker.
  final String why;
  final CatalystType catalystType;
  final List<String> ruleTags;
  final AlertStatus status;
  final DateTime createdAt;

  bool get isBullish => direction == Direction.bullish;

  /// Confidence as a rounded whole percentage, for display.
  int get confidencePercent => (confidence * 100).round();

  factory Alert.fromJson(Map<String, dynamic> json) {
    return Alert(
      id: json['id'] as int,
      ticker: json['ticker'] as String,
      direction: json['direction'] == 'bearish'
          ? Direction.bearish
          : Direction.bullish,
      confidence: (json['confidence'] as num).toDouble(),
      why: json['why'] as String? ?? '',
      catalystType: CatalystType.fromWire(json['catalyst_type'] as String),
      ruleTags: (json['rule_tags'] as List<dynamic>? ?? const [])
          .map((e) => e.toString())
          .toList(),
      status: switch (json['status']) {
        'pending' => AlertStatus.pending,
        'expired' => AlertStatus.expired,
        _ => AlertStatus.confirmed,
      },
      createdAt:
          DateTime.tryParse(json['created_at'] as String? ?? '')?.toLocal() ??
          DateTime.now(),
    );
  }
}

/// One ticker on the user's watchlist.
class WatchlistItem {
  const WatchlistItem({
    required this.id,
    required this.ticker,
    this.sector,
  });

  final int id;
  final String ticker;
  final String? sector;

  factory WatchlistItem.fromJson(Map<String, dynamic> json) => WatchlistItem(
    id: json['id'] as int,
    ticker: json['ticker'] as String,
    sector: json['sector'] as String?,
  );
}

/// A saved technical rule profile.
class RuleSet {
  const RuleSet({
    required this.id,
    required this.name,
    required this.combinator,
    required this.isActive,
    required this.rules,
  });

  final int id;
  final String name;

  /// "and" or "or".
  final String combinator;
  final bool isActive;
  final List<RuleSpec> rules;

  factory RuleSet.fromJson(Map<String, dynamic> json) => RuleSet(
    id: json['id'] as int,
    name: json['name'] as String,
    combinator: json['combinator'] as String,
    isActive: json['is_active'] as bool? ?? false,
    rules: (json['rules'] as List<dynamic>? ?? const [])
        .map((e) => RuleSpec.fromJson(e as Map<String, dynamic>))
        .toList(),
  );
}

class RuleSpec {
  const RuleSpec({
    required this.type,
    required this.params,
    required this.enabled,
  });

  final String type;
  final Map<String, dynamic> params;
  final bool enabled;

  String get label => RuleType.labelFor(type);

  factory RuleSpec.fromJson(Map<String, dynamic> json) => RuleSpec(
    type: json['type'] as String,
    params: Map<String, dynamic>.from(json['params'] as Map? ?? const {}),
    enabled: json['enabled'] as bool? ?? true,
  );

  Map<String, dynamic> toJson() => {
    'type': type,
    'params': params,
    'enabled': enabled,
  };
}
