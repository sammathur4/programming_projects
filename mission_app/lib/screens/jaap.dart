import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../sound.dart';
import '../state.dart';
import '../theme.dart';

/// Jaap Counter — count a mantra on a bead ring.
///
/// Tap the ring to move one bead. The bead count per round is the user's
/// choice (108 is the tradition, not a rule), so the ring is drawn from it and
/// a round completes — with a bell — when the last bead is reached.
class JaapScreen extends StatefulWidget {
  const JaapScreen({super.key});

  @override
  State<JaapScreen> createState() => _JaapScreenState();
}

class _JaapScreenState extends State<JaapScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AppState>().loadJaap();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final active = state.jaapActive;
    if (active == null) {
      return Center(
        child: state.error != null
            ? ErrorPane(message: state.error!, onRetry: state.loadJaap)
            : const Center(child: CircularProgressIndicator()),
      );
    }

    final id = asInt(active['id']);
    final beads = asInt(active['beads'], asInt(active['mala_size'], 108));
    final count = state.jaapCountOf(id);
    final malas = state.jaapMalasOf(id);
    final goal = asInt(active['goal'], 1);
    final color = hexColor(active['color'] as String?, AppColors.gold);
    final wide = MediaQuery.of(context).size.width >= 900;

    final ring = Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        MalaRing(
          count: count,
          beads: beads,
          color: color,
          completedMalas: malas,
          size: wide ? 300 : 250,
          onTap: () => _tap(state, id),
        ),
        const SizedBox(height: 10),
        Text(
          '$count',
          style: TextStyle(
            fontSize: 34,
            fontWeight: FontWeight.w900,
            color: color,
            height: 1,
          ),
        ),
        Text(
          malas > 0
              ? '$malas mala${malas == 1 ? '' : 's'} complete'
              : 'tap the ring to count',
          style: const TextStyle(fontSize: 12, color: AppColors.dim),
        ),
      ],
    );

    return RefreshIndicator(
      onRefresh: state.loadJaap,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 40),
        children: [
          _MantraPicker(
            state: state,
            onPick: (mid) => setState(() => state.jaapActiveId = mid),
          ),
          const SizedBox(height: 16),
          if (wide)
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(child: Center(child: ring)),
                Expanded(child: _SidePanel(state: state, active: active, id: id)),
              ],
            )
          else ...[
            Center(child: ring),
            const SizedBox(height: 18),
            _SidePanel(state: state, active: active, id: id),
          ],
        ],
      ),
    );
  }

  Future<void> _tap(AppState state, int id) async {
    // A light tick per bead; the bell is for the completed round.
    HapticFeedback.selectionClick();
    final completed = await state.tapJaap(id);
    if (completed) {
      HapticFeedback.mediumImpact();
      await Bell.ring();
    }
  }
}

/// The mantra chips across the top.
class _MantraPicker extends StatelessWidget {
  const _MantraPicker({required this.state, required this.onPick});
  final AppState state;
  final ValueChanged<int> onPick;

  @override
  Widget build(BuildContext context) {
    if (state.jaapMantras.isEmpty) {
      return const SizedBox(
        height: 40,
        child: Center(child: CircularProgressIndicator(strokeWidth: 2)),
      );
    }
    return SizedBox(
      height: 46,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: state.jaapMantras.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (ctx, i) {
          final m = state.jaapMantras[i];
          final id = asInt(m['id']);
          final on = state.jaapActiveId == id ||
              (state.jaapActiveId == null && i == 0);
          final color = hexColor(m['color'] as String?, AppColors.gold);
          final count = state.jaapCountOf(id);
          return InkWell(
            onTap: () => onPick(id),
            borderRadius: BorderRadius.circular(14),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: on ? color.withValues(alpha: 0.16) : AppColors.surface,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                  color: on ? color : AppColors.border,
                  width: on ? 1.5 : 1,
                ),
              ),
              child: Row(
                children: [
                  Text(m['emoji'] as String? ?? '🙏',
                      style: const TextStyle(fontSize: 16)),
                  const SizedBox(width: 8),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        m['name'] as String? ?? '',
                        style: const TextStyle(
                            fontSize: 12.5, fontWeight: FontWeight.w700),
                      ),
                      if (count > 0)
                        Text('$count today',
                            style: const TextStyle(
                                fontSize: 10, color: AppColors.faint)),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

/// Goal, streak, beads-per-round and the undo button.
class _SidePanel extends StatelessWidget {
  const _SidePanel({
    required this.state,
    required this.active,
    required this.id,
  });
  final AppState state;
  final Map<String, dynamic> active;
  final int id;

  @override
  Widget build(BuildContext context) {
    final beads = asInt(active['beads'], asInt(active['mala_size'], 108));
    final goal = asInt(active['goal'], 1);
    final count = state.jaapCountOf(id);
    final stats = state.jaapStats;
    final per = <Map<String, dynamic>>[];
    for (final p in (stats['per_mantra'] as List? ?? [])) {
      per.add(Map<String, dynamic>.from(p as Map));
    }
    final mine = per.where((p) => asInt(p['mantra']) == id).toList();
    final streak = mine.isEmpty ? 0 : asInt(mine.first['streak']);
    final total = mine.isEmpty ? 0 : asInt(mine.first['total']);
    final color = hexColor(active['color'] as String?, AppColors.gold);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // ---- goal ring
        AppCard(
          color: AppColors.surface,
          child: Row(
            children: [
              _MiniRing(
                value: goal <= 0 ? 0 : (count / goal).clamp(0.0, 1.0),
                color: color,
                label: '$count/$goal',
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Daily goal',
                      style: const TextStyle(
                          fontSize: 11, color: AppColors.faint),
                    ),
                    Text(
                      goal > 0
                          ? (count >= goal
                              ? 'Goal met ✓'
                              : '${goal - count} to go')
                          : 'No goal set',
                      style: const TextStyle(
                          fontSize: 15, fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Pill('🔥 $streak day streak',
                            color: AppColors.orange),
                        const SizedBox(width: 6),
                        Pill('$total lifetime',
                            color: AppColors.dim),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // ---- controls
        AppCard(
          color: AppColors.surface,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Beads per round',
                  style:
                      TextStyle(fontSize: 11, color: AppColors.faint)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final n in const [10, 27, 54, 108, 1008])
                    _Chip(
                      label: '$n',
                      on: n == beads,
                      onTap: () => _setBeads(n),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: count > 0 ? () => _undo() : null,
                      icon: const Icon(Icons.undo, size: 16),
                      label: const Text('Undo'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _editGoal(context),
                      icon: const Icon(Icons.flag_outlined, size: 16),
                      label: const Text('Goal'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // ---- the mantra itself
        AppCard(
          color: AppColors.surface,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(active['emoji'] as String? ?? '🙏',
                      style: const TextStyle(fontSize: 18)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      active['name'] as String? ?? '',
                      style: const TextStyle(
                          fontSize: 14, fontWeight: FontWeight.w800),
                    ),
                  ),
                ],
              ),
              if ((active['devanagari'] as String? ?? '').isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  active['devanagari'] as String,
                  style: const TextStyle(
                    fontFamily: 'NotoSansDevanagari',
                    fontSize: 15,
                    color: AppColors.text,
                    height: 1.5,
                  ),
                ),
              ],
              if ((active['transliteration'] as String? ?? '').isNotEmpty) ...[
                const SizedBox(height: 4),
                Text(
                  active['transliteration'] as String,
                  style: const TextStyle(
                      fontSize: 11.5, color: AppColors.faint, height: 1.4),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _undo() async {
    HapticFeedback.selectionClick();
    await state.tapJaap(id, delta: -1);
  }

  Future<void> _setBeads(int n) async {
    try {
      await Api.send('PATCH', 'jaap-mantras/$id/', {'mala_size': n},
          label: 'Beads $n', dedupeId: 'jaap-beads-$id');
      await state.loadJaap();
    } catch (e) {
      state.error = 'Could not change the bead count';
      state.notifyListeners();
    }
  }

  Future<void> _editGoal(BuildContext context) async {
    final ctrl = TextEditingController(
        text: asInt(active['goal'], 1).toString());
    final value = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Daily goal'),
        content: TextField(
          controller: ctrl,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(
            labelText: 'Jaaps per day',
            helperText: '0 means no goal',
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () =>
                Navigator.pop(ctx, int.tryParse(ctrl.text.trim()) ?? 0),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    if (value == null) return;
    try {
      await Api.send('PATCH', 'jaap-mantras/$id/', {'daily_goal': value},
          label: 'Goal $value', dedupeId: 'jaap-goal-$id');
      await state.loadJaap();
    } catch (e) {
      state.error = 'Could not save the goal';
      state.notifyListeners();
    }
  }
}

/// A small circular progress ring for the daily goal.
class _MiniRing extends StatelessWidget {
  const _MiniRing({required this.value, required this.color, required this.label});
  final double value;
  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 58,
      height: 58,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox(
            width: 58,
            height: 58,
            child: CircularProgressIndicator(
              value: value,
              strokeWidth: 5,
              backgroundColor: AppColors.track,
              valueColor: AlwaysStoppedAnimation(color),
            ),
          ),
          Text(
            label,
            style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800),
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.on, required this.onTap});
  final String label;
  final bool on;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: on ? AppColors.violet.withValues(alpha: 0.18) : AppColors.surface2,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
              color: on ? AppColors.violet : AppColors.border,
              width: on ? 1.5 : 1),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: on ? AppColors.violetText : AppColors.dim,
          ),
        ),
      ),
    );
  }
}
