import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../theme.dart';
import '../responsive.dart';
import '../offline.dart';
import 'jaap.dart';
import 'sync.dart';

/// Today — the home screen.
///
/// Mirrors `viewToday()` in docs/ui_mockup/web_mockup.html:
///   * a date bar with the score ring on the right
///   * habit rows that are exactly 52px tall
///   * a right column of note / study / fitness / goals cards
/// On wide screens the two columns sit side by side; on phones they stack.
class TodayScreen extends StatefulWidget {
  const TodayScreen({super.key});

  @override
  State<TodayScreen> createState() => _TodayScreenState();
}

class _TodayScreenState extends State<TodayScreen> {
  Timer? _clock;
  DateTime _now = DateTime.now();

  @override
  void initState() {
    super.initState();
    // Tick once a minute: keeps the clock live and rolls the day over at
    // midnight so "Today" never keeps showing yesterday's data.
    _clock = Timer.periodic(const Duration(seconds: 30), (_) {
      final n = DateTime.now();
      final rolled = AppState.iso(n) != AppState.iso(_now);
      setState(() => _now = n);
      if (rolled) context.read<AppState>().loadAll();
    });
  }

  @override
  void dispose() {
    _clock?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    if (state.loading && state.overview == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.overview == null) {
      return ErrorPane(
        message: state.error ?? 'Could not reach the server.',
        onRetry: state.loadAll,
      );
    }

    return RefreshIndicator(
      onRefresh: state.loadAll,
      child: LayoutBuilder(
        builder: (context, c) {
          final wide = c.maxWidth >= 980;
          final habits = _HabitsCard(state: state, now: _now);
          final side = _TodaySideColumn(state: state);
          if (!wide) {
            return ListView(
              padding: const EdgeInsets.fromLTRB(14, 14, 14, 40),
              children: [
                const _OfflineBanner(),
                habits,
                const SizedBox(height: 12),
                side,
              ],
            );
          }
          return SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(18, 16, 18, 40),
            child: Column(
              children: [
                const _OfflineBanner(),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: habits),
                    const SizedBox(width: 16),
                    Expanded(child: side),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}

/// A strip shown only when writes are waiting to reach the server.
///
/// This exists so "I ticked a habit and nothing happened" cannot be confused
/// with data loss: the app says plainly that the change is saved on the phone
/// and will upload on the next sync.
class _OfflineBanner extends StatelessWidget {
  const _OfflineBanner();

  @override
  Widget build(BuildContext context) {
    // Rebuild whenever the queue changes: watching AppState keeps the banner
    // in step, since OfflineStore.notify() pings it on every queue mutation.
    context.watch<AppState>();
    final pending = OfflineStore.length;
    if (pending == 0) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: AppColors.amber.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute(builder: (_) => const SyncScreen()),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              children: [
                const Icon(Icons.cloud_off_outlined, size: 18, color: AppColors.amber),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    'Working offline — $pending change${pending == 1 ? '' : 's'} '
                    'saved on this device. Tap to sync.',
                    style: const TextStyle(fontSize: 12, color: AppColors.text),
                  ),
                ),
                const Icon(Icons.chevron_right, size: 18, color: AppColors.amber),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Left column — the date bar + the habit list
// ---------------------------------------------------------------------------
class _HabitsCard extends StatelessWidget {
  final AppState state;
  final DateTime now;
  const _HabitsCard({required this.state, required this.now});

  @override
  Widget build(BuildContext context) {
    final o = state.overview!;
    final day = DateTime.parse(state.today);
    final isToday = state.today == AppState.iso(DateTime.now());
    final total = asInt(o['habit_total']);
    final done = asInt(o['done_today']);
    final skipped = asInt(o['skipped_today']);
    final inProgress = asInt(o['in_progress_today']);
    final pct = total == 0 ? 0 : (done / total * 100).round();
    final remaining = total - done - skipped - inProgress;
    final statusLine = remaining > 0
        ? '$remaining habit${remaining > 1 ? 's' : ''} left'
        : skipped > 0
            ? '🎉 day complete ($skipped skipped)'
            : '🎉 perfect day';
    // "in progress" is worth surfacing: it explains a score that isn't 100%.
    final progressNote = inProgress > 0 ? ' · $inProgress in progress' : '';

    final habits = List<Map<String, dynamic>>.from(
      (o['habits'] as List).map((h) => Map<String, dynamic>.from(h as Map)),
    );
    // keep original order - don't reorder on status change

    return AppCard(
      padding: const EdgeInsets.fromLTRB(12, 14, 12, 8),
      gradient: AppColors.cardGrad,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(
              children: [
                IcoBtn(Icons.chevron_left, onTap: () => state.shiftDay(-1)),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(_dayTitle(day, isToday),
                            style: const TextStyle(
                                fontSize: 16, fontWeight: FontWeight.w800)),
                        Text(
                          isToday
                              ? '${_clock(now)} · $statusLine$progressNote'
                              : '$statusLine$progressNote',
                          style: const TextStyle(fontSize: 12, color: AppColors.dim),
                        ),
                      ],
                    ),
                  ),
                ),
                IcoBtn(
                  Icons.chevron_right,
                  onTap: isToday ? null : () => state.shiftDay(1),
                ),
                const SizedBox(width: 10),
                ScoreRing(pct),
              ],
            ),
          ),
          ...habits.map((h) => _HabitRow(habit: h, state: state)),
        ],
      ),
    );
  }

  static String _dayTitle(DateTime d, bool isToday) {
    const names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    final prefix = isToday ? 'Today — ' : '';
    return '$prefix${names[d.weekday - 1]}, ${d.day} ${months[d.month - 1]} ${d.year}';
  }

  /// Local wall-clock time, e.g. "06:42".
  static String _clock(DateTime d) =>
      '${d.hour.toString().padLeft(2, '0')}:${d.minute.toString().padLeft(2, '0')}';
}

/// A single habit row — exactly 52px, matching `.habit-card`.
class _HabitRow extends StatelessWidget {
  final Map<String, dynamic> habit;
  final AppState state;
  const _HabitRow({required this.habit, required this.state});

  @override
  Widget build(BuildContext context) {
    final color = hexColor(habit['color'] as String?);
    final status = (habit['status_today'] ?? '').toString();
    final done = habit['done_today'] == true;
    final skipped = status == 'skipped';
    final inProgress = status == 'in_progress';
    final paused = habit['is_paused'] == true;
    final streak = asInt(habit['streak']);
    final note = (habit['today_note'] ?? '').toString();
    final target = asDouble(habit['target_value']);
    final isCount = target > 0;
    final value = asDouble(habit['today_value']);
    final unit = (habit['target_unit'] ?? '').toString();

    /// Local completion/skip time, e.g. " · 06:42".
    String stamp() {
      final raw = habit['logged_at']?.toString();
      if (raw == null || raw.isEmpty) return '';
      final d = DateTime.tryParse(raw);
      if (d == null) return '';
      final local = d.toLocal();
      return ' · ${local.hour.toString().padLeft(2, '0')}:'
          '${local.minute.toString().padLeft(2, '0')}';
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Container(
        height: 52,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(
          gradient: done
              ? LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Color.alphaBlend(color.withValues(alpha: .09), AppColors.surface),
                    const Color(0xFF10162A),
                  ],
                )
              : AppColors.cardGrad,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: done
                ? Color.alphaBlend(color.withValues(alpha: .48), AppColors.border)
                : skipped
                    ? AppColors.amber.withValues(alpha: .45)
                    : inProgress
                        ? AppColors.sky.withValues(alpha: .40)
                        : AppColors.border,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: Color.alphaBlend(color.withValues(alpha: .16), const Color(0xFF0E1424)),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: color.withValues(alpha: .30)),
              ),
              child: Text(habit['emoji'] as String? ?? '✅',
                  style: const TextStyle(fontSize: 16)),
            ),
            const SizedBox(width: 11),
            // fixed 48px clip box: a note or progress bar can never grow the row
            Expanded(
              child: SizedBox(
                height: 48,
                child: ClipRect(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      SizedBox(
                        height: 18,
                        child: Row(
                          children: [
                            Flexible(
                              child: Text(
                                habit['name'] as String? ?? '',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                    fontSize: 13.5, fontWeight: FontWeight.w700),
                              ),
                            ),
                            if (paused) ...[
                              const SizedBox(width: 6),
                              Pill('paused', color: AppColors.amber),
                            ],
                          ],
                        ),
                      ),
                      SizedBox(
                        height: 15,
                        child: Row(
                          children: [
                            Text('🔥 $streak',
                                style: const TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w800,
                                    color: AppColors.orange)),
                            const SizedBox(width: 8),
                            Flexible(
                              child: Text(
                                isCount
                                    ? '${fmtNum(value)} / ${fmtNum(target)} $unit'
                                    : (done
                                        ? 'completed${stamp()}'
                                        : skipped
                                            ? 'skipped${stamp()} — won\'t break your streak'
                                            : inProgress
                                                ? 'in progress${stamp()}'
                                                : 'pending'),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 11, color: AppColors.dim),
                              ),
                            ),
                          ],
                        ),
                      ),
                      SizedBox(
                        height: 13,
                        child: note.isNotEmpty
                            ? Row(
                                children: [
                                  const Text('📝 ', style: TextStyle(fontSize: 10.5)),
                                  Expanded(
                                    child: Text(
                                      note,
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                          fontSize: 10.5, color: AppColors.blueText),
                                    ),
                                  ),
                                ],
                              )
                            : (isCount
                                ? Padding(
                                    padding: const EdgeInsets.only(top: 5, right: 60),
                                    child: ProgressBar(
                                      value: target == 0
                                          ? 0
                                          : (value / target).clamp(0.0, 1.0),
                                      color: color,
                                      height: 3,
                                    ),
                                  )
                                : const SizedBox.shrink()),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            if (isCount)
              _Counter(
                value: value,
                target: target,
                unit: unit,
                onDelta: (d) => state.saveHabitValue(habit['id'] as int, state.today, value + d),
              )
            else
              _StatusButton(
                color: color,
                status: status,
                onTap: () => state.cycleHabitStatus(habit['id'] as int),
                onLongPress: () => _pickStatus(context, state, habit, status),
              ),
          ],
        ),
      ),
    );
  }

  /// Long-press the status button → pick any status explicitly.
  ///
  /// Tap cycles the quick path (pending → done → skipped); this is how a habit
  /// is marked *in progress* or pushed back to *pending* without cycling.
  static Future<void> _pickStatus(
    BuildContext context,
    AppState state,
    Map<String, dynamic> habit,
    String current,
  ) async {
    final id = habit['id'] as int;
    final chosen = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 10),
            Container(
              width: 38,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18),
              child: Row(
                children: [
                  Text(habit['emoji'] as String? ?? '✅',
                      style: const TextStyle(fontSize: 20)),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      habit['name'] as String? ?? '',
                      style: const TextStyle(
                          fontSize: 15, fontWeight: FontWeight.w800),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            for (final opt in const [
              (
                'done',
                'Done',
                Icons.check_circle_outline,
                AppColors.emerald
              ),
              (
                'in_progress',
                'In progress',
                Icons.timelapse_rounded,
                AppColors.sky
              ),
              (
                'pending',
                'Pending',
                Icons.radio_button_unchecked,
                AppColors.dim
              ),
              (
                'skipped',
                'Skipped',
                Icons.remove_circle_outline,
                AppColors.amber
              ),
            ])
              ListTile(
                dense: true,
                leading: Icon(opt.$3, size: 20, color: opt.$4),
                title: Text(opt.$2,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                trailing: current == opt.$1
                    ? Icon(Icons.check, size: 18, color: opt.$4)
                    : null,
                onTap: () => Navigator.pop(ctx, opt.$1),
              ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (chosen == null) return;
    await state.setHabitStatusToday(id, chosen);
  }
}

/// The 3-state cycle button: pending → done → skipped → pending
class _StatusButton extends StatelessWidget {
  final Color color;
  final String status; // '', 'pending', 'in_progress', 'done', 'skipped'
  final VoidCallback onTap;
  final VoidCallback? onLongPress;
  const _StatusButton({
    required this.color,
    required this.status,
    required this.onTap,
    this.onLongPress,
  });

  @override
  Widget build(BuildContext context) {
    final done = status == 'done';
    final skipped = status == 'skipped';
    final inProgress = status == 'in_progress';
    final borderColor = done
        ? color
        : skipped
            ? AppColors.amber
            : inProgress
                ? AppColors.sky
                : Color.alphaBlend(color.withValues(alpha: .55), AppColors.border);
    return GestureDetector(
      onTap: onTap,
      onLongPress: onLongPress,
      child: Tooltip(
        message: done
            ? 'Done — tap for skipped'
            : skipped
                ? 'Skipped — tap for pending'
                : inProgress
                    ? 'In progress — tap for done'
                    : 'Pending — tap for done\nLong-press for more options',
        child: Container(
          width: 34,
          height: 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: done
                ? color
                : skipped
                    ? AppColors.amber.withValues(alpha: .18)
                    : inProgress
                        ? AppColors.sky.withValues(alpha: .20)
                        : Colors.transparent,
            shape: BoxShape.circle,
            border: Border.all(color: borderColor, width: 2),
          ),
          child: done
              ? const Text('✓',
                  style: TextStyle(
                      fontSize: 15, fontWeight: FontWeight.w900, color: Color(0xFF04140A)))
              : skipped
                  ? const Text('–',
                      style: TextStyle(
                          fontSize: 16, fontWeight: FontWeight.w900, color: AppColors.amber))
                  : inProgress
                      // half-filled circle: started, not finished
                      ? Container(
                          width: 13,
                          height: 13,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(color: AppColors.sky, width: 2),
                          ),
                          child: Align(
                            alignment: Alignment.bottomCenter,
                            child: Container(
                              width: 9,
                              height: 5,
                              decoration: const BoxDecoration(
                                color: AppColors.sky,
                                borderRadius: BorderRadius.only(
                                  topLeft: Radius.circular(5),
                                  topRight: Radius.circular(5),
                                ),
                              ),
                            ),
                          ),
                        )
                      : null,
        ),
      ),
    );
  }
}

/// The −/value/+ control for count habits — `.counter`.
class _Counter extends StatelessWidget {
  final double value;
  final double target;
  final String unit;
  final void Function(double) onDelta;
  const _Counter({
    required this.value,
    required this.target,
    required this.unit,
    required this.onDelta,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IcoBtn(Icons.remove, size: 28, onTap: () => onDelta(-1)),
        SizedBox(
          width: 62,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(fmtNum(value),
                  style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800, height: 1.1)),
              Text('of ${fmtNum(target)} $unit',
                  style: const TextStyle(fontSize: 9.5, color: AppColors.dim, fontWeight: FontWeight.w600)),
            ],
          ),
        ),
        IcoBtn(Icons.add, size: 28, onTap: () => onDelta(1)),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Right column — note, study, fitness, goals
// ---------------------------------------------------------------------------
class _TodaySideColumn extends StatelessWidget {
  final AppState state;
  const _TodaySideColumn({required this.state});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const SizedBox(height: 10),
        _JaapCard(state: state),
        const SizedBox(height: 10),
        _FitnessCard(state: state),
        const SizedBox(height: 10),
        _GoalsCard(state: state),
      ],
    );
  }
}

/// A compact jaap summary on the Today screen: how many today, and the
/// streak. Tapping opens the counter.
class _JaapCard extends StatelessWidget {
  final AppState state;
  const _JaapCard({required this.state});

  @override
  Widget build(BuildContext context) {
    if (state.jaapMantras.isEmpty) return const SizedBox.shrink();
    final total = state.jaapTodayTotal;
    final streak = _streak();
    return AppCard(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      onTap: () => _openCounter(context),
      child: Row(
        children: [
          const Text('🙏', style: TextStyle(fontSize: 20)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('Jaap',
                    style:
                        TextStyle(fontSize: 13, fontWeight: FontWeight.w800)),
                Text(
                  total > 0
                      ? '$total today${streak > 0 ? ' · 🔥 $streak day streak' : ''}'
                      : 'Tap to start counting',
                  style: const TextStyle(fontSize: 11.5, color: AppColors.dim),
                ),
              ],
            ),
          ),
          if (total > 0)
            Text('$total',
                style: const TextStyle(
                    fontSize: 20, fontWeight: FontWeight.w900,
                    color: AppColors.gold)),
        ],
      ),
    );
  }

  int _streak() {
    final stats = state.jaapStats;
    for (final p in (stats['per_mantra'] as List? ?? [])) {
      final row = Map<String, dynamic>.from(p as Map);
      final s = asInt(row['streak']);
      if (s > 0) return s;
    }
    return 0;
  }

  void _openCounter(BuildContext context) {
    // Prefer switching the shell's tab; fall back to a direct push when this
    // screen is shown on its own (e.g. in a test).
    if (TabSwitch.goTo(context, 'jaap')) return;
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const JaapScreen()),
    );
  }
}

class _NoteCard extends StatefulWidget {
  final AppState state;
  const _NoteCard({required this.state});

  @override
  State<_NoteCard> createState() => _NoteCardState();
}

class _NoteCardState extends State<_NoteCard> {
  late final TextEditingController _c;

  @override
  void initState() {
    super.initState();
    _c = TextEditingController(text: _saved());
    widget.state.addListener(_sync);
  }

  @override
  void dispose() {
    widget.state.removeListener(_sync);
    _c.dispose();
    super.dispose();
  }

  void _sync() {
    final s = _saved();
    if (!_focused && _c.text != s) _c.text = s;
  }

  bool _focused = false;

  String _saved() => (widget.state.overview?['day_note'] ?? '').toString();

  @override
  Widget build(BuildContext context) {
    return AppCard(
      gradient: AppColors.cardGrad,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('📝 NOTE FOR TODAY',
              style: TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w800,
                  color: AppColors.dim,
                  letterSpacing: .7)),
          const SizedBox(height: 8),
          Focus(
            onFocusChange: (f) => _focused = f,
            child: TextField(
              controller: _c,
              maxLines: 4,
              style: const TextStyle(fontSize: 13.5),
              decoration: const InputDecoration(
                hintText: 'How did today go? Wins, blockers, ideas…',
                filled: true,
                fillColor: AppColors.surface2,
              ),
              onSubmitted: (v) => widget.state.saveDayNote(v),
              onTapOutside: (_) => widget.state.saveDayNote(_c.text),
            ),
          ),
        ],
      ),
    );
  }
}

class _StudyCard extends StatelessWidget {
  final AppState state;
  const _StudyCard({required this.state});

  @override
  Widget build(BuildContext context) {
    // Harden against a malformed 'study' payload — an unhandled cast here is
    // what turned the whole card into a grey error box in release builds.
    final raw = state.overview?['study'];
    final s = raw is Map ? Map<String, dynamic>.from(raw) : <String, dynamic>{};
    final hours = asDouble(s['study_hours']);
    final target = asDouble(state.settingValue('study_target_hours', '6'), 6);
    final rawSlots = s['slots'];
    final slots = rawSlots is List
        ? rawSlots.whereType<Map>().toList()
        : const <Map>[];

    return AppCard(
      gradient: AppColors.cardGrad,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('📚 Study today',
              style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(fmtNum(hours),
                  style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w900, height: 1)),
              const SizedBox(width: 6),
              const Text('hrs', style: TextStyle(fontSize: 12, color: AppColors.dim)),
              const Spacer(),
              Pill('target ${fmtNum(target)}h', color: AppColors.blueText),
            ],
          ),
          const SizedBox(height: 9),
          ProgressBar(
            value: target == 0 ? 0 : (hours / target).clamp(0.0, 1.0),
            color: AppColors.blue,
          ),
          const SizedBox(height: 11),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              Pill((s['mode'] ?? 'WFH').toString(), color: AppColors.dim),
              Pill('${asInt(s['aw_count'])} answers', color: AppColors.dim),
              Pill('${asInt(s['mcq_count'])} MCQ', color: AppColors.dim),
              for (final sl in slots.take(2))
                Pill((sl['subject'] ?? '').toString(), color: AppColors.dim),
            ],
          ),
          const SizedBox(height: 11),
          Row(
            children: [
              Expanded(
                child: SmBtn(
                  '- 0.5h',
                  onTap: hours <= 0
                      ? null
                      : () => state.saveStudy({'study_hours': hours - 0.5}),
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: SmBtn('+ 0.5h',
                    onTap: () => state.saveStudy({'study_hours': hours + 0.5})),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _FitnessCard extends StatefulWidget {
  final AppState state;
  const _FitnessCard({required this.state});

  @override
  State<_FitnessCard> createState() => _FitnessCardState();
}

class _FitnessCardState extends State<_FitnessCard> {
  List<Map<String, dynamic>> _weights = [];
  bool _loaded = false;

  @override
  void initState() {
    super.initState();
    _loadWeights();
  }

  Future<void> _loadWeights() async {
    try {
      final r = await Api.get('fitness/weight/', {'limit': '90'});
      final list = r is List ? r : [];
      if (!mounted) return;
      setState(() {
        _weights = list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _loaded = true;
      });
    } catch (_) {
      if (mounted) setState(() => _loaded = true);
    }
  }

  Future<void> _logWeightDialog() async {
    final saved = await _logWeight(context, widget.state);
    if (saved) {
      await _loadWeights();
      if (mounted) await widget.state.loadAll();
    }
  }

  Future<void> _editWeightEntry(Map<String, dynamic> point) async {
    final saved = await _logWeight(context, widget.state, existing: point);
    if (saved) {
      await _loadWeights();
      if (mounted) await widget.state.loadAll();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.state;
    final raw = state.overview?['fitness'];
    final f = raw is Map ? Map<String, dynamic>.from(raw) : <String, dynamic>{};
    // The overview resolves the latest weigh-in (WeightLog first). Fall back to
    // the freshest locally-fetched entry so a just-logged value shows instantly.
    final latestLocal = _weights.isNotEmpty ? _weights.first : null;
    final weight = f['weight_kg'] ?? latestLocal?['weight_kg'];
    final weightDate = f['weight_date'] ?? latestLocal?['date'];
    final weightTime = f['weight_time'] ?? latestLocal?['time'];
    final change = asDouble(f['weight_change_kg']);
    final exercises = (f['exercises'] as List? ?? []);
    final cardio = (f['cardio_items'] as List? ?? []);

    return AppCard(
      gradient: AppColors.cardGrad,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('🏋️ Fitness today',
              style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(weight == null ? '—' : fmt2(weight),
                  style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w900, height: 1)),
              const SizedBox(width: 6),
              const Text('kg', style: TextStyle(fontSize: 12, color: AppColors.dim)),
              const Spacer(),
              if (weight != null && change != 0)
                Pill('${change > 0 ? '+' : ''}${fmtNum(change)} kg',
                    color: change <= 0 ? AppColors.greenText : AppColors.amberText),
            ],
          ),
          if (weight != null && weightDate != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                'weighed $weightDate'
                '${weightTime != null ? ' at ${_shortTime(weightTime)}' : ''}',
                style: const TextStyle(fontSize: 10.5, color: AppColors.faint),
              ),
            ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final m in const ['WFO', 'WFH', 'Holiday']) ...[
                      _SegChip(
                        label: m,
                        selected: (f['mode'] ?? 'WFO').toString() == m,
                        onTap: () => state.saveFitness({'mode': m}),
                      ),
                    ],
                  ],
                ),
              ),
              SmBtn('+ Log Weight', onTap: _logWeightDialog),
            ],
          ),
          if (_loaded)
            WeightTrendChart(
              points: _weights.reversed.toList(),
              onTapPoint: (p) => _editWeightEntry(p),
            ),
          const SizedBox(height: 8),
          Text(
            exercises.isEmpty
                ? 'No workout logged yet'
                : '${exercises.length} exercises · ${exercises.fold<int>(0, (a, e) => a + asInt(e['sets']))} sets',
            style: const TextStyle(fontSize: 11.5, color: AppColors.dim),
          ),
          if (cardio.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Text(
                cardio
                    .map((c) => '${c['type']} ${fmtNum(c['quantity'])}${c['unit'] ?? ''}')
                    .join(' · '),
                style: const TextStyle(fontSize: 11.5, color: AppColors.dim),
              ),
            ),
        ],
      ),
    );
  }
}

class _GoalsCard extends StatelessWidget {
  final AppState state;
  const _GoalsCard({required this.state});

  @override
  Widget build(BuildContext context) {
    final objectives = (state.stats?['objectives'] ?? state.overview?['objectives'] ?? []);
    final active = List<Map<String, dynamic>>.from(
      (objectives as List).where((o) {
        final m = Map<String, dynamic>.from(o as Map);
        return (m['status'] ?? 'active') == 'active';
      }).map((o) => Map<String, dynamic>.from(o as Map)),
    );
    if (active.isEmpty) return const SizedBox.shrink();

    return AppCard(
      gradient: AppColors.cardGrad,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('🎯 Goals touching today',
              style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          for (final o in active.take(4)) ...[
            Padding(
              padding: const EdgeInsets.only(bottom: 11),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text((o['area'] ?? o['name'] ?? '').toString(),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
                      ),
                      Text('${asInt(o['progress'])}%',
                          style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w900,
                              color: AppColors.forScore(asInt(o['progress'])))),
                    ],
                  ),
                  const SizedBox(height: 6),
                  ProgressBar(
                    value: asDouble(o['progress']) / 100,
                    color: AppColors.forScore(asInt(o['progress'])),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Segmented mode chip (WFO / WFH / Holiday)
// ---------------------------------------------------------------------------
class _SegChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback? onTap;
  const _SegChip({required this.label, required this.selected, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
        decoration: BoxDecoration(
          color: selected ? AppColors.surface3 : AppColors.surface2,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.border),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
            color: selected ? AppColors.text : AppColors.dim,
          ),
        ),
      ),
    );
  }
}

/// "07:15:00" -> "07:15". Handles both plain clock and full ISO strings.
String _shortTime(dynamic t) {
  final s = t.toString();
  final m = RegExp(r'(\d{2}:\d{2})').firstMatch(s);
  return m?.group(1) ?? s;
}

Future<bool> _logWeight(BuildContext context, AppState state,
    {Map<String, dynamic>? existing}) async {
  final ctrl = TextEditingController(
      text: existing == null ? '' : fmt2(existing['weight_kg']));
  final timeCtrl = TextEditingController();
  final dateCtrl = TextEditingController(
    text: (existing?['date'] as String?) ??
        DateTime.now().toIso8601String().substring(0, 10),
  );
  String? validation;
  final saved = await showDialog<bool>(
    context: context,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setS) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(existing == null ? 'Log Weight' : 'Correct weight entry'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: ctrl,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Weight (kg)'),
            ),
            TextField(
              controller: dateCtrl,
              decoration: const InputDecoration(labelText: 'Date (YYYY-MM-DD)'),
            ),
            TextField(
              controller: timeCtrl,
              decoration: const InputDecoration(
                  labelText: 'Time (HH:MM:SS, optional, local)'),
            ),
            if (validation != null)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(validation!,
                    style: const TextStyle(color: AppColors.rose, fontSize: 12)),
              ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          TextButton(
            onPressed: () async {
              final w = double.tryParse(ctrl.text.trim());
              final d = dateCtrl.text.trim();
              if (w == null || w <= 0) {
                setS(() => validation = 'Enter a positive number, e.g. 104.8');
                return;
              }
              final body = <String, dynamic>{
                'date': d.isEmpty
                    ? DateTime.now().toIso8601String().substring(0, 10)
                    : d,
                'weight_kg': w,
              };
              if (timeCtrl.text.trim().isNotEmpty) {
                body['time'] = timeCtrl.text.trim();
              }
              try {
                if (existing == null) {
                  await Api.send('POST', 'fitness/weight/', body,
                      label: 'Weight ${w}kg · ${body['date']}',
                      dedupeId: 'weight-${body['date']}');
                } else {
                  await Api.send('PATCH', 'fitness/weight/${existing['id']}/', body,
                      label: 'Weight ${w}kg · ${body['date']}',
                      dedupeId: 'weight-${body['date']}');
                }
                if (ctx.mounted) Navigator.pop(ctx, true);
                await state.loadAll();
              } catch (e) {
                if (ctx.mounted) {
                  setS(() => validation = 'Could not save: $e');
                }
              }
            },
            child: Text(existing == null ? 'Save' : 'Update'),
          ),
        ],
      ),
    ),
  );
  return saved == true;
}

// ---------------------------------------------------------------------------
// Weight trend chart — last 30 days, lightweight CustomPaint line.
// ---------------------------------------------------------------------------
class WeightTrendChart extends StatefulWidget {
  final List<Map<String, dynamic>> points;
  final void Function(Map<String, dynamic>)? onTapPoint;
  const WeightTrendChart({super.key, required this.points, this.onTapPoint});

  @override
  State<WeightTrendChart> createState() => _WeightTrendChartState();
}

class _WeightTrendChartState extends State<WeightTrendChart> {
  int? _selected;

  @override
  Widget build(BuildContext context) {
    final all = widget.points
        .where((p) => p['weight_kg'] != null)
        .toList();
    if (all.length < 2) {
      return Container(
        margin: const EdgeInsets.only(top: 10),
        padding: const EdgeInsets.symmetric(vertical: 18),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: AppColors.surface2,
          borderRadius: BorderRadius.circular(10),
        ),
        child: const Text(
          'No weight history yet — log two or more entries to see a trend.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 11.5, color: AppColors.faint),
        ),
      );
    }
    final cutoff = DateTime.now().subtract(const Duration(days: 29));
    var pts = all.where((p) {
      final d = DateTime.tryParse(p['date'] as String? ?? '');
      return d != null && !d.isBefore(DateTime(cutoff.year, cutoff.month, cutoff.day));
    }).toList();
    if (pts.length < 2) pts = all;

    final values = pts.map((p) => asDouble(p['weight_kg'])).toList();
    final minV = values.reduce((a, b) => a < b ? a : b);
    final maxV = values.reduce((a, b) => a > b ? a : b);
    final span = (maxV - minV).abs() < 0.1 ? 1.0 : (maxV - minV);
    final latest = values.last;
    final net = latest - values.first;

    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 6),
      decoration: BoxDecoration(
        color: AppColors.surface2,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('Weight trend',
                  style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800)),
              const Spacer(),
              Pill('${fmt2(latest)} kg',
                  color: AppColors.sky),
              const SizedBox(width: 6),
              Pill('${net >= 0 ? '+' : ''}${fmt2(net)} kg',
                  color: net <= 0 ? AppColors.greenText : AppColors.amberText),
            ],
          ),
          const SizedBox(height: 6),
          SizedBox(
            height: 72,
            width: double.infinity,
            child: GestureDetector(
              onTapDown: (d) {
                final box = context.findRenderObject() as RenderBox?;
                if (box == null) return;
                final w = box.size.width;
                final idx =
                    ((d.localPosition.dx / (w == 0 ? 1 : w)) * (pts.length - 1))
                        .round()
                        .clamp(0, pts.length - 1);
                setState(() => _selected = idx);
                widget.onTapPoint?.call(pts[idx]);
              },
              child: CustomPaint(
                painter: _WeightPainter(
                  values: values,
                  minV: minV,
                  span: span,
                  selected: _selected,
                ),
              ),
            ),
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Text('${pts.first['date']}',
                  style: const TextStyle(fontSize: 9.5, color: AppColors.faint)),
              const Spacer(),
              Text('${pts.last['date']}',
                  style: const TextStyle(fontSize: 9.5, color: AppColors.faint)),
            ],
          ),
          if (_selected != null && _selected! < pts.length)
            Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Text(
                '${pts[_selected!]['date']} · ${fmt2(pts[_selected!]['weight_kg'])} kg'
                '${pts[_selected!]['time'] != null ? ' at ${_shortTime(pts[_selected!]['time'])}' : ''}'
                ' · tap to edit',
                style: const TextStyle(fontSize: 10.5, color: AppColors.dim),
              ),
            ),
        ],
      ),
    );
  }
}

class _WeightPainter extends CustomPainter {
  final List<double> values;
  final double minV;
  final double span;
  final int? selected;
  _WeightPainter({
    required this.values,
    required this.minV,
    required this.span,
    this.selected,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;
    const padY = 8.0;
    final h = size.height - padY * 2;
    final dx = size.width / (values.length - 1);
    final points = <Offset>[];
    for (var i = 0; i < values.length; i++) {
      final y = padY + h - ((values[i] - minV) / span) * h;
      points.add(Offset(i * dx, y));
    }
    final path = Path()..moveTo(points.first.dx, points.first.dy);
    for (final p in points.skip(1)) {
      path.lineTo(p.dx, p.dy);
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = AppColors.sky
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
    final fill = Path.from(path)
      ..lineTo(points.last.dx, size.height)
      ..lineTo(points.first.dx, size.height)
      ..close();
    canvas.drawPath(
      fill,
      Paint()..color = AppColors.sky.withValues(alpha: 0.12),
    );
    for (var i = 0; i < points.length; i++) {
      final isSel = i == selected;
      canvas.drawCircle(
        points[i],
        isSel ? 4.5 : 2.5,
        Paint()..color = isSel ? Colors.white : AppColors.sky,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _WeightPainter old) =>
      old.values != values || old.selected != selected || old.minV != minV || old.span != span;
}
