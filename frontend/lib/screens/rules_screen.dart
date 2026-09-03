/// Saved technical rule profiles.
///
/// Editing individual rule parameters is a follow-up; this screen lists saved
/// profiles, shows what each contains, and switches which one the pipeline uses.
library;

import 'package:flutter/material.dart';

import '../models/alert.dart';
import '../state/app_state.dart';

class RulesScreen extends StatelessWidget {
  const RulesScreen({super.key, required this.state});

  final AppState state;

  String _describe(RuleSpec rule) {
    final params = rule.params.entries
        .map((e) => '${e.key}=${e.value}')
        .join(', ');
    return params.isEmpty ? rule.label : '${rule.label}  ($params)';
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListenableBuilder(
      listenable: state,
      builder: (context, _) {
        final ruleSets = state.ruleSets;
        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Rule sets',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'The active profile decides what counts as technical '
                'confirmation for your alerts.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: ruleSets.isEmpty
                    ? const Center(child: CircularProgressIndicator())
                    : ListView.builder(
                        itemCount: ruleSets.length,
                        itemBuilder: (context, i) {
                          final rs = ruleSets[i];
                          return Card(
                            margin: const EdgeInsets.only(bottom: 12),
                            child: Padding(
                              padding: const EdgeInsets.all(14),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Text(
                                        rs.name,
                                        style: const TextStyle(
                                          fontWeight: FontWeight.w700,
                                          fontSize: 16,
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Chip(
                                        label: Text(
                                          rs.combinator.toUpperCase(),
                                          style: const TextStyle(fontSize: 11),
                                        ),
                                        visualDensity: VisualDensity.compact,
                                      ),
                                      const Spacer(),
                                      if (rs.isActive)
                                        const Chip(
                                          avatar: Icon(Icons.check, size: 14),
                                          label: Text('Active'),
                                          visualDensity: VisualDensity.compact,
                                        )
                                      else
                                        TextButton(
                                          onPressed: () =>
                                              state.activateRuleSet(rs.id),
                                          child: const Text('Use this'),
                                        ),
                                    ],
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    rs.combinator == 'and'
                                        ? 'Every rule must fire:'
                                        : 'Any one rule confirms:',
                                    style: theme.textTheme.labelSmall,
                                  ),
                                  const SizedBox(height: 6),
                                  Wrap(
                                    spacing: 6,
                                    runSpacing: 6,
                                    children: [
                                      for (final rule in rs.rules)
                                        Chip(
                                          label: Text(
                                            _describe(rule),
                                            style: const TextStyle(
                                              fontSize: 11,
                                            ),
                                          ),
                                          visualDensity: VisualDensity.compact,
                                        ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
              ),
            ],
          ),
        );
      },
    );
  }
}
