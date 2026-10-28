import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api.dart';
import '../theme.dart';

/// Legend-style training hub.
///
/// The tab is organised around the core loop Legend is built on:
///   Today    — see the day's routine, run the workout set-by-set (with a rest
///              timer and last-session autofill), then finish it.
///   Routines — the named training days (Push / Pull / Legs…), startable.
///   Progress — per-exercise strength trend + bodyweight analytics.
///   Weight   — weigh-ins with a chart, BMI and goal tracking.
///   Measures — circumference chart per site.
///   Drinks   — water and other beverages, one tap per serving.
///   Library  — the exercise catalog with instructions.
class FitnessScreen extends StatefulWidget {
  const FitnessScreen({super.key});

  @override
  State<FitnessScreen> createState() => _FitnessScreenState();
}

class _FitnessScreenState extends State<FitnessScreen> with TickerProviderStateMixin {
  late final TabController _tabs;
  String _date = DateFormat('yyyy-MM-dd').format(DateTime.now());
  bool _loading = true;
  String? _error;

  Map<String, dynamic>? _workout;
  List<dynamic> _history = [];
  List<dynamic> _exercises = [];
  List<dynamic> _modules = [];
  Map<String, dynamic> _fatigue = {'muscles': {}};
  Map<String, dynamic>? _schedule;
  Map<String, dynamic> _weightAnalytics = {};
  Map<String, dynamic>? _measurements;
  Map<String, dynamic>? _insights;
  Map<String, dynamic>? _drinks;
  List<dynamic> _drinkPresets = [];

  StartupTimer? _restTimer;
  int _restRemaining = 0;
  int _restTotal = 0;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 7, vsync: this);
    _loadAll();
  }

  @override
  void dispose() {
    _restTimer?.cancel();
    _tabs.dispose();
    super.dispose();
  }

  Future<void> _loadAll() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await Future.wait([
        Api.get('workout/$_date/'),
        Api.get('workout-history/?limit=40'),
        Api.get('exercises/?limit=300'),
        Api.get('muscle-fatigue/?days=14'),
        Api.get('workout-schedule/'),
        Api.get('workout-modules/'),
        Api.get('fitness/analytics/?days=90'),
      ]);
      setState(() {
        _workout = r[0] as Map<String, dynamic>;
        _history = (r[1]['results'] as List? ?? []);
        _exercises = (r[2]['results'] as List? ?? []);
        _fatigue = (r[3] as Map<String, dynamic>);
        _schedule = (r[4] as Map<String, dynamic>);
        _modules = (r[5] as List? ?? []);
        _weightAnalytics = (r[6] as Map<String, dynamic>);
        _loading = false;
      });
      // body data is secondary — a failure here shouldn't blank the tab
      await _loadBody();
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  /// Weight / measurements / drinks data shared by the three body tabs.
  Future<void> _loadBody() async {
    final today = DateFormat('yyyy-MM-dd').format(DateTime.now());
    try {
      final r = await Future.wait([
        Api.get('body-measurements/'),
        Api.get('weight-insights/'),
        Api.get('drinks/', {'date': today}),
      ]);
      if (!mounted) return;
      setState(() {
        _measurements = r[0] as Map<String, dynamic>;
        _insights = r[1] as Map<String, dynamic>;
        _drinks = r[2] as Map<String, dynamic>;
        _drinkPresets = (r[2]['presets'] as List? ?? []);
      });
    } catch (_) {
      // leave whatever we had; the individual tabs show their own empty states
    }
  }

  Future<void> _changeDate(int delta) async {
    final d = DateTime.parse(_date).add(Duration(days: delta));
    setState(() => _date = DateFormat('yyyy-MM-dd').format(d));
    await _loadWorkoutOnly();
  }

  Future<void> _loadWorkoutOnly() async {
    try {
      final w = await Api.get('workout/$_date/');
      setState(() => _workout = w as Map<String, dynamic>);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  // ------------------------------------------------------------- rest timer
  void _startRest(int seconds) {
    if (seconds <= 0) return;
    _restTimer?.cancel();
    setState(() {
      _restTotal = seconds;
      _restRemaining = seconds;
    });
    _restTimer = StartupTimer(seconds, (remaining) {
      if (!mounted) return;
      setState(() => _restRemaining = remaining);
      if (remaining <= 0) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Rest done — next set!'), duration: Duration(seconds: 2)),
          );
        }
      }
    });
  }

  void _stopRest() {
    _restTimer?.cancel();
    setState(() {
      _restRemaining = 0;
      _restTotal = 0;
    });
  }

  // ------------------------------------------------------------- actions
  Future<void> _startModule(Map<String, dynamic> module) async {
    try {
      await Api.send('POST', 'workout/$_date/start/', {'module': module['id']},
          label: 'Start ${module['name']}', dedupeId: 'workout-start-$_date');      await _loadWorkoutOnly();
      await _loadAll();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Started ${module['name']}'), duration: const Duration(seconds: 2)),
      );
      _tabs.animateTo(0);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  Future<void> _finishWorkout() async {
    final w = _workout ?? {};
    final exs = (w['exercises'] as List? ?? []);
    if (exs.isEmpty) return;
    try {
      await Api.send('PATCH', 'workout/$_date/', {
        'status': 'Completed',
        'notes': (w['notes'] ?? '').toString(),
      }, label: 'Finish workout · $_date', dedupeId: 'workout-finish-$_date');
      await _loadAll();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Workout finished 💪'), duration: Duration(seconds: 2)),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return ErrorPane(message: _error!, onRetry: _loadAll);
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Training'),
        bottom: TabBar(
          controller: _tabs,
          isScrollable: true,
          tabs: const [
            Tab(text: 'Today'),
            Tab(text: 'Routines'),
            Tab(text: 'Progress'),
            Tab(text: 'Weight'),
            Tab(text: 'Measures'),
            Tab(text: 'Drinks'),
            Tab(text: 'Library'),
          ],
        ),
      ),
      body: Column(
        children: [
          if (_restRemaining > 0) _RestBanner(
            remaining: _restRemaining,
            total: _restTotal,
            onStop: _stopRest,
            onAdd: () => _startRest(_restRemaining + 30),
          ),
          Expanded(
            child: TabBarView(
              controller: _tabs,
              children: [
                _TodayTab(
                  workout: _workout,
                  date: _date,
                  schedule: _schedule,
                  modules: _modules,
                  onChanged: _loadWorkoutOnly,
                  onStartModule: _startModule,
                  onFinish: _finishWorkout,
                  onAddExercise: _openAddExercise,
                  onRest: _startRest,
                  onDateStep: _changeDate,
                  onPickDate: _pickDate,
                ),
                _RoutinesTab(
                  modules: _modules,
                  schedule: _schedule,
                  onStart: _startModule,
                ),
                _ProgressTab(
                  exercises: _exercises,
                  history: _history,
                  weightAnalytics: _weightAnalytics,
                  fatigue: _fatigue,
                ),
                _WeightTab(
                  analytics: _weightAnalytics,
                  insights: _insights,
                  onChanged: _loadAll,
                ),
                _MeasuresTab(
                  measurements: _measurements,
                  onChanged: _loadBody,
                ),
                _DrinksTab(
                  drinks: _drinks,
                  presets: _drinkPresets,
                  onChanged: _loadBody,
                ),
                _LibraryTab(exercises: _exercises),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: DateTime.parse(_date),
      firstDate: DateTime(2025),
      lastDate: DateTime(2028),
    );
    if (picked != null) {
      setState(() => _date = DateFormat('yyyy-MM-dd').format(picked));
      await _loadWorkoutOnly();
    }
  }

  Future<void> _openAddExercise() async {
    final added = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (ctx) => _AddExerciseSheet(exercises: _exercises, date: _date),
    );
    if (added == true) await _loadWorkoutOnly();
  }
}

/// A tiny cancellable countdown used for the rest timer.
class StartupTimer {
  StartupTimer(int seconds, void Function(int) onTick) : _total = seconds, _onTick = onTick {
    _onTick(_total);
    _t = Timer.periodic(const Duration(seconds: 1), (_) {
      _left--;
      if (_left <= 0) {
        cancel();
        _onTick(0);
      } else {
        _onTick(_left);
      }
    });
  }

  final void Function(int) _onTick;
  Timer? _t;
  late int _left = _total;
  final int _total;

  void cancel() {
    _t?.cancel();
    _t = null;
  }
}

/// Floating countdown shown while resting between sets.
class _RestBanner extends StatelessWidget {
  final int remaining;
  final int total;
  final VoidCallback onStop;
  final VoidCallback onAdd;
  const _RestBanner({
    required this.remaining,
    required this.total,
    required this.onStop,
    required this.onAdd,
  });

  @override
  Widget build(BuildContext context) {
    final m = remaining ~/ 60;
    final s = remaining % 60;
    final pct = total == 0 ? 0.0 : remaining / total;
    return Container(
      color: AppColors.violet.withValues(alpha: 0.16),
      padding: const EdgeInsets.fromLTRB(14, 8, 8, 8),
      child: Row(
        children: [
          const Icon(Icons.timer_outlined, size: 18, color: AppColors.violet),
          const SizedBox(width: 8),
          Text('Rest $m:${s.toString().padLeft(2, '0')}',
              style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13)),
          const SizedBox(width: 12),
          Expanded(child: ProgressBar(value: pct, color: AppColors.violet, height: 5)),
          const SizedBox(width: 8),
          TextButton(onPressed: onAdd, child: const Text('+30s', style: TextStyle(fontSize: 12))),
          IconButton(
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.close, size: 18),
            onPressed: onStop,
          ),
        ],
      ),
    );
  }
}

// =====================================================================
// Today — the active workout
// =====================================================================
class _TodayTab extends StatelessWidget {
  final Map<String, dynamic>? workout;
  final String date;
  final Map<String, dynamic>? schedule;
  final List<dynamic> modules;
  final Future<void> Function() onChanged;
  final Future<void> Function(Map<String, dynamic>) onStartModule;
  final Future<void> Function() onFinish;
  final Future<void> Function() onAddExercise;
  final void Function(int) onRest;
  final Future<void> Function(int) onDateStep;
  final Future<void> Function() onPickDate;

  const _TodayTab({
    this.workout,
    required this.date,
    this.schedule,
    required this.modules,
    required this.onChanged,
    required this.onStartModule,
    required this.onFinish,
    required this.onAddExercise,
    required this.onRest,
    required this.onDateStep,
    required this.onPickDate,
  });

  @override
  Widget build(BuildContext context) {
    final w = workout ?? {};
    final exs = (w['exercises'] as List? ?? []);
    final totals = (w['totals'] as Map? ?? {});
    final week = (schedule?['week'] as List? ?? []);
    final status = (w['status'] ?? 'Pending').toString();
    final done = status.toLowerCase() == 'completed';

    return RefreshIndicator(
      onRefresh: onChanged,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          _DateBar(date: date, onStep: onDateStep, onPick: onPickDate),
          const SizedBox(height: 10),
          if (week.isNotEmpty) _WeekStrip(week: week),
          const SizedBox(height: 10),
          AppCard(
            gradient: LinearGradient(
              colors: [
                AppColors.violet.withValues(alpha: 0.20),
                AppColors.surface,
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(w['module']?.toString() ?? 'No routine set',
                              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
                          const SizedBox(height: 2),
                          Text(DateFormat('EEEE, MMM d, yyyy').format(DateTime.parse(date)),
                              style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                        ],
                      ),
                    ),
                    Pill(
                      done ? 'Completed' : status,
                      color: done ? AppColors.greenText : AppColors.amber,
                      icon: done ? Icons.check_circle : Icons.pending_outlined,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    _miniStat('${totals['sets'] ?? 0}', 'sets'),
                    _miniStat('${totals['reps'] ?? 0}', 'reps'),
                    _miniStat(fmtNum(totals['volume_kg'] ?? 0), 'kg moved'),
                    _miniStat('${exs.length}', 'exercises'),
                  ],
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    if (modules.isNotEmpty && !done)
                      PopupMenuButton<Map<String, dynamic>>(
                        onSelected: onStartModule,
                        itemBuilder: (_) => [
                          for (final m in modules)
                            PopupMenuItem(
                              value: Map<String, dynamic>.from(m as Map),
                              child: Text('Start ${m['name']}'),
                            ),
                        ],
                        child: _actionBtn('Start routine', Icons.play_arrow, AppColors.emerald),
                      ),
                    const SizedBox(width: 8),
                    if (exs.isNotEmpty && !done)
                      _actionBtnTap('Finish', Icons.flag, AppColors.orange, onFinish),
                    const Spacer(),
                    _actionBtnTap('Add exercise', Icons.add, AppColors.sky, onAddExercise),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          if (exs.isEmpty)
            EmptyState(
              icon: Icons.fitness_center_outlined,
              title: 'Nothing logged for this day',
              subtitle: 'Start a routine above, or add exercises one by one.',
              action: TextButton.icon(
                onPressed: onAddExercise,
                icon: const Icon(Icons.add),
                label: const Text('Add exercise'),
              ),
            )
          else
            ...[
              SectionLabel('Exercises', icon: Icons.list_alt),
              ...exs.map((e) => _ExerciseCard(
                    ex: Map<String, dynamic>.from(e as Map),
                    onChanged: onChanged,
                    onRest: onRest,
                  )),
            ],
        ],
      ),
    );
  }

  Widget _miniStat(String value, String label) => Expanded(
        child: Column(
          children: [
            Text(value, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
            Text(label, style: const TextStyle(fontSize: 10, color: AppColors.faint)),
          ],
        ),
      );

  Widget _actionBtn(String label, IconData icon, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.16),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withValues(alpha: 0.4)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 15, color: color),
          const SizedBox(width: 5),
          Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: color)),
        ]),
      );

  Widget _actionBtnTap(String label, IconData icon, Color color, VoidCallback onTap) =>
      InkWell(onTap: onTap, borderRadius: BorderRadius.circular(10), child: _actionBtn(label, icon, color));
}

class _DateBar extends StatelessWidget {
  final String date;
  final Future<void> Function(int) onStep;
  final Future<void> Function() onPick;
  const _DateBar({required this.date, required this.onStep, required this.onPick});

  @override
  Widget build(BuildContext context) {
    final isToday = DateFormat('yyyy-MM-dd').format(DateTime.now()) == date;
    return Row(
      children: [
        IconButton(icon: const Icon(Icons.chevron_left), onPressed: () => onStep(-1)),
        Expanded(
          child: InkWell(
            onTap: onPick,
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Column(
                children: [
                  Text(DateFormat('EEE, dd MMM yyyy').format(DateTime.parse(date)),
                      textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w800)),
                  if (isToday) const Text('Today', style: TextStyle(fontSize: 10.5, color: AppColors.greenText)),
                ],
              ),
            ),
          ),
        ),
        IconButton(icon: const Icon(Icons.chevron_right), onPressed: () => onStep(1)),
      ],
    );
  }
}

class _WeekStrip extends StatelessWidget {
  final List<dynamic> week;
  const _WeekStrip({required this.week});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 12),
      child: Row(
        children: week.map((w) {
          final isToday = w['is_today'] == true;
          final color = w['color'] == null ? AppColors.faint : hexColor(w['color']);
          final hasModule = w['module'] != null;
          return Expanded(
            child: Column(
              children: [
                Text(w['day'],
                    style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, color: isToday ? AppColors.text : AppColors.faint)),
                const SizedBox(height: 6),
                Container(
                  height: 38,
                  width: 38,
                  decoration: BoxDecoration(
                    color: hasModule ? color.withValues(alpha: isToday ? .26 : .12) : Colors.white.withValues(alpha: .04),
                    borderRadius: BorderRadius.circular(11),
                    border: Border.all(
                      color: isToday ? color.withValues(alpha: .8) : (hasModule ? color.withValues(alpha: .28) : AppColors.border),
                      width: isToday ? 1.6 : 1,
                    ),
                  ),
                  alignment: Alignment.center,
                  child: Text(w['emoji'] ?? '·', style: const TextStyle(fontSize: 16)),
                ),
                const SizedBox(height: 5),
                Text(hasModule ? w['module'] : 'Rest',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: 9.5, fontWeight: FontWeight.w700, color: hasModule ? color : AppColors.faint)),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

/// One exercise in the active workout: header, last-session hint, set list and
/// an inline "log a set" row prefilled from the most recent session.
class _ExerciseCard extends StatefulWidget {
  final Map<String, dynamic> ex;
  final Future<void> Function() onChanged;
  final void Function(int) onRest;
  const _ExerciseCard({required this.ex, required this.onChanged, required this.onRest});

  @override
  State<_ExerciseCard> createState() => _ExerciseCardState();
}

class _ExerciseCardState extends State<_ExerciseCard> {
  final _w = TextEditingController();
  final _r = TextEditingController();
  final _rpe = TextEditingController();
  String _type = 'working';
  bool _saving = false;
  bool _open = true;
  bool _prefilled = false;

  @override
  void dispose() {
    _w.dispose();
    _r.dispose();
    _rpe.dispose();
    super.dispose();
  }

  /// Legend autofills the input with the suggested numbers from last time.
  void _prefillFromLast() {
    if (_prefilled) return;
    _prefilled = true;
    final last = widget.ex['last_time'] as Map?;
    if (last == null) return;
    final sw = last['suggested_weight'];
    final sr = last['suggested_reps'];
    if (sw != null) _w.text = fmtNum(sw);
    if (sr != null) _r.text = sr.toString();
  }

  @override
  Widget build(BuildContext context) {
    final ex = widget.ex;
    final sets = (ex['sets'] as List? ?? []);
    final last = ex['last_time'] as Map?;
    final completedSets = sets.where((s) => (s as Map)['completed'] == true).length;

    if (_open && !_prefilled) _prefillFromLast();

    return AppCard(
      margin: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: () => setState(() => _open = !_open),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(ex['name'], style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800)),
                      Text(
                        '${ex['muscle'] ?? ''} • ${asInt(ex['target_sets'])}×${ex['target_reps'] ?? ''} • ${asInt(ex['rest_seconds'])}s rest',
                        style: const TextStyle(fontSize: 11, color: AppColors.faint),
                      ),
                    ],
                  ),
                ),
                if (ex['strength_level'] != null) Pill(ex['strength_level'], color: AppColors.sky),
                const SizedBox(width: 6),
                Pill('$completedSets/${sets.length}', color: completedSets == sets.length && sets.isNotEmpty ? AppColors.greenText : AppColors.dim),
                Icon(_open ? Icons.expand_less : Icons.expand_more, color: AppColors.faint),
              ],
            ),
          ),
          if (last != null) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: .04),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Row(
                children: [
                  const Icon(Icons.history, size: 14, color: AppColors.dim),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Last ${last['date']}: ${last['best_set']}'
                      '${last['suggested_weight'] != null ? ' → try ${fmtNum(last['suggested_weight'])}kg × ${last['suggested_reps']}' : ''}',
                      style: const TextStyle(fontSize: 11, color: AppColors.dim),
                    ),
                  ),
                ],
              ),
            ),
          ],
          if (_open) ...[
            const SizedBox(height: 8),
            ...sets.asMap().entries.map((me) => _setRow(context, me.key, me.value as Map<String, dynamic>)),
            const SizedBox(height: 10),
            _addSetRow(),
          ],
        ],
      ),
    );
  }

  Widget _setRow(BuildContext context, int i, Map<String, dynamic> s) {
    final completed = s['completed'] == true;
    final isWarm = s['set_type'] == 'warmup';
    final isCardio = s['distance_km'] != null;
    final label = isCardio
        ? '${fmtNum(s['distance_km'])}km • ${asInt(s['duration_sec'])}s'
        : '${fmtNum(s['weight_kg'])}kg × ${s['reps']}';

    return InkWell(
      onTap: () async {
        await Api.send('PATCH', 'workout-set/${s['id']}/', {'completed': !completed},
            label: '${widget.ex['name']} · set ${s['order']}', 
            dedupeId: 'wset-${s['id']}-${!completed}');
        if (!completed) {
          // completing a set kicks off the rest timer
          widget.onRest(asInt(widget.ex['rest_seconds'], 90));
        }
        await widget.onChanged();
      },
      borderRadius: BorderRadius.circular(8),
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 3),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        decoration: BoxDecoration(
          color: completed ? AppColors.emerald.withValues(alpha: 0.08) : Colors.white.withValues(alpha: 0.02),
          borderRadius: BorderRadius.circular(9),
          border: Border.all(color: completed ? AppColors.emerald.withValues(alpha: 0.3) : AppColors.border),
        ),
        child: Row(
          children: [
            SizedBox(
              width: 22,
              child: Text('${i + 1}', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12)),
            ),
            if (s['set_type'] != null && s['set_type'] != 'working') ...[
              Pill(s['set_type'], color: isWarm ? AppColors.amber : AppColors.rose, filled: true),
              const SizedBox(width: 6),
            ],
            Expanded(
              child: Text(
                label,
                style: TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                  decoration: completed ? TextDecoration.lineThrough : null,
                  color: completed ? AppColors.dim : AppColors.text,
                ),
              ),
            ),
            if (s['rpe'] != null) ...[
              Pill('RPE ${fmtNum(s['rpe'])}', color: AppColors.violet),
              const SizedBox(width: 6),
            ],
            if (s['est_1rm'] != null && asDouble(s['est_1rm']) > 0) ...[
              Pill('${fmtNum(s['est_1rm'])} 1RM', color: AppColors.sky),
              const SizedBox(width: 6),
            ],
            Icon(completed ? Icons.check_circle : Icons.circle_outlined,
                size: 19, color: completed ? AppColors.emerald : AppColors.faint),
          ],
        ),
      ),
    );
  }

  Widget _addSetRow() {
    return Row(
      children: [
        SizedBox(
          width: 66,
          child: TextField(
            controller: _w,
            decoration: const InputDecoration(labelText: 'kg', isDense: true),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
          ),
        ),
        const SizedBox(width: 6),
        SizedBox(
          width: 62,
          child: TextField(
            controller: _r,
            decoration: const InputDecoration(labelText: 'reps', isDense: true),
            keyboardType: TextInputType.number,
          ),
        ),
        const SizedBox(width: 6),
        SizedBox(
          width: 58,
          child: TextField(
            controller: _rpe,
            decoration: const InputDecoration(labelText: 'RPE', isDense: true),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
          ),
        ),
        const SizedBox(width: 6),
        DropdownButton<String>(
          value: _type,
          isDense: true,
          underline: const SizedBox.shrink(),
          dropdownColor: AppColors.surface2,
          style: const TextStyle(fontSize: 12, color: AppColors.text),
          items: const [
            DropdownMenuItem(value: 'working', child: Text('Working')),
            DropdownMenuItem(value: 'warmup', child: Text('Warm-up')),
            DropdownMenuItem(value: 'drop', child: Text('Drop')),
            DropdownMenuItem(value: 'failure', child: Text('Failure')),
            DropdownMenuItem(value: 'amrap', child: Text('AMRAP')),
          ],
          onChanged: (v) => setState(() => _type = v ?? 'working'),
        ),
        const Spacer(),
        FilledButton.icon(
          onPressed: _saving ? null : _addSet,
          icon: _saving
              ? const SizedBox(width: 13, height: 13, child: CircularProgressIndicator(strokeWidth: 1.5))
              : const Icon(Icons.add, size: 16),
          label: const Text('Log set'),
        ),
      ],
    );
  }

  Future<void> _addSet() async {
    setState(() => _saving = true);
    try {
      final body = <String, dynamic>{
        'weight_kg': double.tryParse(_w.text.trim()),
        'reps': int.tryParse(_r.text.trim()),
        'set_type': _type,
        'completed': true,
      };
      if (_rpe.text.trim().isNotEmpty) body['rpe'] = double.tryParse(_rpe.text.trim());
      await Api.send('POST', 'workout-exercise/${widget.ex['id']}/sets/', body,
          label: '${widget.ex['name']} · new set',
          dedupeId: 'wset-new-${DateTime.now().microsecondsSinceEpoch}');
      widget.onRest(asInt(widget.ex['rest_seconds'], 90));
      setState(() => _type = 'working');
      await widget.onChanged();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }
}

/// Bottom sheet for adding an exercise from the library (or a custom one).
class _AddExerciseSheet extends StatefulWidget {
  final List<dynamic> exercises;
  final String date;
  const _AddExerciseSheet({required this.exercises, required this.date});

  @override
  State<_AddExerciseSheet> createState() => _AddExerciseSheetState();
}

class _AddExerciseSheetState extends State<_AddExerciseSheet> {
  final nameCtrl = TextEditingController();
  final muscleCtrl = TextEditingController();
  final setsCtrl = TextEditingController(text: '3');
  final repsCtrl = TextEditingController(text: '8-10');
  final restCtrl = TextEditingController(text: '90');
  String q = '';
  bool saving = false;

  @override
  void dispose() {
    nameCtrl.dispose();
    muscleCtrl.dispose();
    setsCtrl.dispose();
    repsCtrl.dispose();
    restCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = widget.exercises.where((e) {
      if (q.isEmpty) return true;
      final n = (e['name'] as String).toLowerCase();
      final m = (e['muscle'] as String).toLowerCase();
      return n.contains(q) || m.contains(q);
    }).toList();
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom, top: 16, left: 16, right: 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Add exercise', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          const SizedBox(height: 12),
          TextField(
            decoration: const InputDecoration(labelText: 'Search library…', isDense: true),
            onChanged: (v) => setState(() => q = v.toLowerCase()),
          ),
          const SizedBox(height: 8),
          SizedBox(
            height: 200,
            child: filtered.isEmpty
                ? const Center(child: Text('No matches', style: TextStyle(color: AppColors.dim)))
                : ListView.builder(
                    itemCount: filtered.length,
                    itemBuilder: (_, i) {
                      final e = filtered[i];
                      return ListTile(
                        dense: true,
                        title: Text(e['name']),
                        subtitle: Text('${e['muscle']} • ${e['equipment']}'),
                        onTap: () => setState(() {
                          nameCtrl.text = e['name'];
                          muscleCtrl.text = e['muscle'] ?? '';
                        }),
                      );
                    },
                  ),
          ),
          const Divider(),
          Row(
            children: [
              Expanded(child: TextField(controller: nameCtrl, decoration: const InputDecoration(labelText: 'Name', isDense: true))),
              const SizedBox(width: 8),
              Expanded(child: TextField(controller: muscleCtrl, decoration: const InputDecoration(labelText: 'Muscle', isDense: true))),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: TextField(controller: setsCtrl, decoration: const InputDecoration(labelText: 'Sets', isDense: true), keyboardType: TextInputType.number)),
              const SizedBox(width: 8),
              Expanded(child: TextField(controller: repsCtrl, decoration: const InputDecoration(labelText: 'Reps', isDense: true))),
              const SizedBox(width: 8),
              Expanded(child: TextField(controller: restCtrl, decoration: const InputDecoration(labelText: 'Rest (s)', isDense: true), keyboardType: TextInputType.number)),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Spacer(),
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
              FilledButton(
                onPressed: saving ? null : _save,
                child: const Text('Add'),
              ),
            ],
          ),
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Future<void> _save() async {
    if (nameCtrl.text.trim().isEmpty) return;
    setState(() => saving = true);
    try {
      await Api.send('POST', 'workout/${widget.date}/exercise/', {
        'name': nameCtrl.text.trim(),
        'muscle': muscleCtrl.text.trim(),
        'target_sets': int.tryParse(setsCtrl.text.trim()),
        'target_reps': repsCtrl.text.trim(),
        'rest_seconds': int.tryParse(restCtrl.text.trim()),
      }, label: 'Add ${nameCtrl.text.trim()}',
          dedupeId: 'wex-new-${DateTime.now().microsecondsSinceEpoch}');
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) {
        setState(() => saving = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }
}

// =====================================================================
// Routines — named training days
// =====================================================================
class _RoutinesTab extends StatelessWidget {
  final List<dynamic> modules;
  final Map<String, dynamic>? schedule;
  final Future<void> Function(Map<String, dynamic>) onStart;
  const _RoutinesTab({required this.modules, this.schedule, required this.onStart});

  @override
  Widget build(BuildContext context) {
    if (modules.isEmpty) {
      return const EmptyState(icon: Icons.event_note_outlined, title: 'No routines yet', subtitle: 'Training days (Push, Pull, Legs…) will appear here.');
    }
    final week = (schedule?['week'] as List? ?? []);
    final todayModule = week.firstWhere((w) => w['is_today'] == true, orElse: () => null)?['module'];

    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        SectionLabel('Your routines', icon: Icons.event_note_outlined),
        ...modules.map((m) {
          final mod = Map<String, dynamic>.from(m as Map);
          final days = (mod['days'] as List? ?? []);
          final exs = (mod['exercises'] as List? ?? []);
          final muscles = (mod['muscles'] as Map? ?? {});
          final color = reqColor(mod);
          final isToday = todayModule != null && todayModule == mod['name'];
          return AppCard(
            margin: const EdgeInsets.only(bottom: 10),
            borderColor: isToday ? color.withValues(alpha: 0.6) : null,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.16),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: color.withValues(alpha: 0.4)),
                      ),
                      alignment: Alignment.center,
                      child: Text(mod['emoji'] ?? '🏋️', style: const TextStyle(fontSize: 19)),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text(mod['name'], style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900)),
                              if (isToday) ...[
                                const SizedBox(width: 6),
                                Pill('Today', color: AppColors.greenText, filled: true),
                              ],
                            ],
                          ),
                          Text('${exs.length} exercises • ${asInt(mod['total_sets'])} sets • ${fmtNum(mod['volume_kg'])}kg',
                              style: const TextStyle(fontSize: 11, color: AppColors.faint)),
                        ],
                      ),
                    ),
                    FilledButton.icon(
                      onPressed: () => onStart(mod),
                      icon: const Icon(Icons.play_arrow, size: 17),
                      label: const Text('Start'),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Wrap(spacing: 6, runSpacing: 6, children: [
                  for (final d in days) Pill(d.toString(), color: AppColors.dim),
                ]),
                const SizedBox(height: 8),
                Wrap(spacing: 6, runSpacing: 6, children: [
                  for (final me in muscles.entries)
                    Pill('${me.key} ${me.value}', color: AppColors.violet),
                ]),
                const SizedBox(height: 10),
                ...exs.map((e) => Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Row(
                        children: [
                          const Icon(Icons.drag_indicator, size: 15, color: AppColors.faint),
                          const SizedBox(width: 6),
                          Expanded(child: Text(e['name'], style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600))),
                          Text('${e['sets']} × ${e['reps']}', style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                        ],
                      ),
                    )),
              ],
            ),
          );
        }),
      ],
    );
  }

  static Color reqColor(Map<String, dynamic> mod) =>
      mod['color'] == null ? AppColors.emerald : hexColor(mod['color'] as String);
}

// =====================================================================
// Progress — strength trend + bodyweight
// =====================================================================
class _ProgressTab extends StatefulWidget {
  final List<dynamic> exercises;
  final List<dynamic> history;
  final Map<String, dynamic> weightAnalytics;
  final Map<String, dynamic> fatigue;
  const _ProgressTab({
    required this.exercises,
    required this.history,
    required this.weightAnalytics,
    required this.fatigue,
  });

  @override
  State<_ProgressTab> createState() => _ProgressTabState();
}

class _ProgressTabState extends State<_ProgressTab> {
  String? _name;
  Map<String, dynamic>? _progress;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _pickFirst();
  }

  void _pickFirst() {
    if (widget.exercises.isNotEmpty) {
      setState(() => _name = widget.exercises.first['name'] as String);
      _load();
    }
  }

  Future<void> _load() async {
    final name = _name;
    if (name == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final p = await Api.get('exercise-progress/?name=${Uri.encodeComponent(name)}');
      setState(() {
        _progress = p as Map<String, dynamic>;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final wa = widget.weightAnalytics;
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        // ---------------- bodyweight analytics
        SectionLabel('Bodyweight', icon: Icons.monitor_weight_outlined),
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(child: StatBlock(fmt2(wa['latest']), 'current kg', color: AppColors.text)),
                  Expanded(child: StatBlock('${wa['workout_days'] ?? 0}', 'workout days', color: AppColors.sky)),
                  Expanded(child: StatBlock('${wa['total_sets'] ?? 0}', 'sets logged', color: AppColors.violet)),
                  Expanded(
                    child: StatBlock(
                      wa['lost_kg'] == null ? '—' : fmtNum(wa['lost_kg']),
                      'kg lost',
                      color: AppColors.emerald,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              _WeightSpark(series: (wa['series'] as List? ?? [])),
              const SizedBox(height: 8),
              Text(
                'Goal ${fmtNum(wa['goal_weight'])}kg • target ${wa['calorie_target'] ?? 0} kcal • adherence ${wa['calorie_adherence_pct'] ?? 0}%',
                style: const TextStyle(fontSize: 11, color: AppColors.faint),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),

        // ---------------- per-exercise strength
        SectionLabel('Strength trend', icon: Icons.trending_up),
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              DropdownButtonFormField<String>(
                initialValue: _name,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Exercise', isDense: true),
                dropdownColor: AppColors.surface2,
                items: [
                  for (final e in widget.exercises)
                    DropdownMenuItem(value: e['name'] as String, child: Text(e['name'] as String, overflow: TextOverflow.ellipsis)),
                ],
                onChanged: (v) {
                  setState(() => _name = v);
                  _load();
                },
              ),
              const SizedBox(height: 12),
              if (_loading)
                const Padding(padding: EdgeInsets.all(20), child: Center(child: CircularProgressIndicator()))
              else if (_error != null)
                Text('Could not load progress: $_error', style: const TextStyle(color: AppColors.rose, fontSize: 12))
              else if (_progress == null || _progress!['found'] != true)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Text('No logged sets for this exercise yet.', style: TextStyle(color: AppColors.dim)),
                )
              else
                _progressBody(_progress!),
            ],
          ),
        ),
        const SizedBox(height: 14),

        // ---------------- muscle volume / fatigue
        SectionLabel('Muscle volume (14d)', icon: Icons.donut_small_outlined),
        AppCard(
          child: Column(
            children: (widget.fatigue['muscles'] as Map? ?? {}).entries.map((me) {
              final v = (me.value as Map? ?? {});
              final sets = asInt(v['sets']);
              final maxSets = (widget.fatigue['muscles'] as Map).values
                  .map((m) => asInt((m as Map)['sets']))
                  .fold<int>(1, (a, b) => a > b ? a : b);
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(
                  children: [
                    SizedBox(width: 84, child: Text(me.key, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700))),
                    Expanded(child: ProgressBar(value: maxSets == 0 ? 0 : sets / maxSets, color: AppColors.violet, height: 7)),
                    const SizedBox(width: 8),
                    SizedBox(width: 34, child: Text('$sets', textAlign: TextAlign.right, style: const TextStyle(fontSize: 11.5))),
                    SizedBox(width: 62, child: Text('${asInt(v['days_since'])}d ago', textAlign: TextAlign.right, style: const TextStyle(fontSize: 10.5, color: AppColors.faint))),
                  ],
                ),
              );
            }).toList(),
          ),
        ),
        const SizedBox(height: 14),

        // ---------------- recent sessions
        SectionLabel('Recent sessions', icon: Icons.history),
        if (widget.history.isEmpty)
          const Text('No sessions logged yet.', style: TextStyle(color: AppColors.dim))
        else
          ...widget.history.take(10).map((h) => AppCard(
                margin: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(DateFormat('EEE, dd MMM yyyy').format(DateTime.parse(h['date'])),
                              style: const TextStyle(fontWeight: FontWeight.w800)),
                          const SizedBox(height: 2),
                          Wrap(spacing: 6, runSpacing: 6, children: (h['muscles'] as List? ?? []).map((m) => Pill(m.toString(), color: AppColors.dim)).toList()),
                        ],
                      ),
                    ),
                    if (h['module'] != null) Pill(h['module'], color: AppColors.sky),
                    const SizedBox(width: 6),
                    Pill('${h['sets']} sets • ${fmtNum(h['volume_kg'])}kg', color: AppColors.emerald),
                  ],
                ),
              )),
      ],
    );
  }

  Widget _progressBody(Map<String, dynamic> p) {
    final history = (p['history'] as List? ?? []);
    final best = history.isEmpty
        ? null
        : history.reduce((a, b) => asDouble(a['est_1rm']) >= asDouble(b['est_1rm']) ? a : b);
    final gains = p['gains_pct'];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(child: StatBlock(best == null ? '—' : fmtNum(best['est_1rm']), 'best e1RM kg', color: AppColors.emerald)),
            Expanded(child: StatBlock(best == null ? '—' : '${best['top_weight']}', 'top set kg', color: AppColors.sky)),
            Expanded(child: StatBlock(best == null ? '—' : '${best['total_reps']}', 'best reps', color: AppColors.violet)),
            Expanded(
              child: StatBlock(
                gains == null ? '—' : '${asDouble(gains) >= 0 ? '+' : ''}${fmtNum(gains)}%',
                'gains',
                color: (asDouble(gains) >= 0) ? AppColors.greenText : AppColors.rose,
              ),
            ),
          ],
        ),
        const SizedBox(height: 14),
        _E1rmSpark(history: history),
        const SizedBox(height: 12),
        Text('Best set: ${best == null ? '—' : best['best_set']}', style: const TextStyle(fontSize: 12, color: AppColors.dim)),
        const SizedBox(height: 10),
        ...history.reversed.take(8).map((h) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  SizedBox(width: 92, child: Text(DateFormat('dd MMM yyyy').format(DateTime.parse(h['date'])), style: const TextStyle(fontSize: 11.5, color: AppColors.dim))),
                  Expanded(child: Text(h['best_set'], style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600))),
                  Text('e1RM ${fmtNum(h['est_1rm'])}', style: const TextStyle(fontSize: 11.5, color: AppColors.sky)),
                ],
              ),
            )),
      ],
    );
  }
}

/// Estimated 1RM trend across logged sessions (relative bar chart).
class _E1rmSpark extends StatelessWidget {
  final List<dynamic> history;
  const _E1rmSpark({required this.history});

  @override
  Widget build(BuildContext context) {
    if (history.length < 2) {
      return const Text('Not enough sessions to chart a trend yet.', style: TextStyle(fontSize: 12, color: AppColors.faint));
    }
    return _RelativeSpark(
      values: history.map((h) => asDouble(h['est_1rm'])).toList(),
      color: AppColors.emerald,
      height: 120,
    );
  }
}

/// Bodyweight trend from the analytics series (relative bar chart).
class _WeightSpark extends StatelessWidget {
  final List<dynamic> series;
  const _WeightSpark({required this.series});

  @override
  Widget build(BuildContext context) {
    if (series.length < 2) {
      return const SizedBox(
        height: 90,
        child: Center(child: Text('Log bodyweight to see the trend.', style: TextStyle(color: AppColors.faint))),
      );
    }
    return _RelativeSpark(
      values: series.map((s) => asDouble(s['kg'])).toList(),
      color: AppColors.violet,
      height: 110,
    );
  }
}

/// Bar sparkline that scales an arbitrary numeric series to its own range.
///
/// [Sparkline] expects 0..100 values, so this maps the observed min/max onto
/// that range before handing the data over.
class _RelativeSpark extends StatelessWidget {
  final List<double> values;
  final Color color;
  final double height;
  const _RelativeSpark({required this.values, required this.color, required this.height});

  @override
  Widget build(BuildContext context) {
    if (values.length < 2) return SizedBox(height: height);
    final lo = values.reduce((a, b) => a < b ? a : b);
    final hi = values.reduce((a, b) => a > b ? a : b);
    final span = (hi - lo).abs() < 1e-9 ? 1.0 : (hi - lo);
    final scaled = [
      for (final v in values) (12 + (v - lo) / span * 88).round(),
    ];
    return Sparkline(values: scaled, color: color, height: height);
  }
}

// =====================================================================
// Weight — weigh-ins, chart, BMI and goal tracking
// =====================================================================
class _WeightTab extends StatefulWidget {
  final Map<String, dynamic> analytics;
  final Map<String, dynamic>? insights;
  final Future<void> Function() onChanged;
  const _WeightTab({required this.analytics, this.insights, required this.onChanged});

  @override
  State<_WeightTab> createState() => _WeightTabState();
}

class _WeightTabState extends State<_WeightTab> {
  @override
  Widget build(BuildContext context) {
    final wa = widget.analytics;
    final ins = widget.insights ?? {};
    final series = (wa['series'] as List? ?? []);
    final points = [
      for (final s in series)
        ChartPoint(_shortDate(s['date']), asDouble(s['kg'])),
    ];
    final goal = ins['goal_weight_kg'] ?? wa['goal_weight'];
    final guides = <ChartGuide>[
      if (goal != null) ChartGuide(asDouble(goal), 'goal ${fmtNum(goal)}kg', color: AppColors.emerald),
    ];

    return RefreshIndicator(
      onRefresh: widget.onChanged,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          // ---------------- current + BMI
          AppCard(
            gradient: LinearGradient(
              colors: [AppColors.violet.withValues(alpha: 0.18), AppColors.surface],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('CURRENT WEIGHT',
                              style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 1.1, color: AppColors.dim)),
                          const SizedBox(height: 3),
                          Text.rich(TextSpan(children: [
                            TextSpan(
                                text: ins['weight_kg'] == null ? fmt2(wa['latest']) : fmt2(ins['weight_kg']),
                                style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w900, height: 1)),
                            const TextSpan(text: ' kg', style: TextStyle(fontSize: 15, color: AppColors.dim)),
                          ])),
                          if (wa['lost_kg'] != null)
                            Text('${fmtNum(wa['lost_kg'])} kg lost',
                                style: const TextStyle(fontSize: 11.5, color: AppColors.greenText)),
                        ],
                      ),
                    ),
                    if (ins['bmi'] != null)
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Pill('BMI ${fmt2(ins['bmi'])}', color: _bmiColor(asDouble(ins['bmi'])), filled: true),
                          const SizedBox(height: 6),
                          Text((ins['bmi_category'] ?? '').toString(),
                              style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                        ],
                      ),
                  ],
                ),
                const SizedBox(height: 14),
                LineChart(
                  points: points,
                  color: AppColors.violet,
                  height: 170,
                  unit: 'kg',
                  guides: guides,
                ),
              ],
            ),
          ),

          // ---------------- insights grid
          const SizedBox(height: 14),
          SectionLabel('Body composition', icon: Icons.info_outline, trailing:
            TextButton.icon(
              onPressed: () => _openProfileSheet(context),
              icon: const Icon(Icons.edit, size: 15),
              label: const Text('Edit profile'),
            ),
          ),
          AppCard(
            child: ins['bmi'] == null
                ? const Text(
                    'Add your height in Settings (or “Edit profile” above) to see your BMI, '
                    'healthy weight range and how far you are from your goal.',
                    style: TextStyle(fontSize: 12.5, color: AppColors.dim, height: 1.5),
                  )
                : Column(
                    children: [
                      Row(
                        children: [
                          Expanded(child: StatBlock(fmt2(ins['bmi']), 'BMI', color: _bmiColor(asDouble(ins['bmi'])))),
                          Expanded(child: StatBlock(
                            ins['healthy_min_kg'] == null || ins['healthy_max_kg'] == null
                                ? '—'
                                : '${fmtNum(ins['healthy_min_kg'])}–${fmtNum(ins['healthy_max_kg'])}',
                            'healthy kg',
                            color: AppColors.emerald,
                          )),
                          Expanded(child: StatBlock(
                            ins['to_goal_kg'] == null
                                ? '—'
                                : '${asDouble(ins['to_goal_kg']) > 0 ? '+' : ''}${fmtNum(ins['to_goal_kg'])}',
                            'to goal kg',
                            color: asDouble(ins['to_goal_kg']) <= 0 ? AppColors.greenText : AppColors.amber,
                          )),
                          Expanded(child: StatBlock(
                            ins['age'] == null ? '—' : '${ins['age']}',
                            'age',
                            color: AppColors.violet,
                          )),
                        ],
                      ),
                      const SizedBox(height: 14),
                      _bmiBar(asDouble(ins['bmi'])),
                      if (ins['trend_30d_kg'] != null) ...[
                        const SizedBox(height: 10),
                        Text(
                          '30-day trend: ${asDouble(ins['trend_30d_kg']) > 0 ? '+' : ''}${fmtNum(ins['trend_30d_kg'])} kg',
                          style: TextStyle(
                            fontSize: 12,
                            color: asDouble(ins['trend_30d_kg']) <= 0 ? AppColors.greenText : AppColors.rose,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ],
                    ],
                  ),
          ),

          // ---------------- quick log
          const SizedBox(height: 14),
          SectionLabel('Log a weigh-in', icon: Icons.add_chart),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Record today\'s bodyweight — it feeds the chart above, your BMI '
                  'and the goal progress.',
                  style: TextStyle(fontSize: 12, color: AppColors.dim, height: 1.4),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () => _openWeightSheet(context),
                    icon: const Icon(Icons.monitor_weight_outlined, size: 18),
                    label: const Text('Log today\'s weight'),
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 14),
          SectionLabel('History', icon: Icons.history),
          if (series.isEmpty)
            const Text('No weigh-ins logged yet.', style: TextStyle(color: AppColors.dim))
          else
            ...(series.reversed.take(20).map((s) {
              final kg = asDouble(s['kg']);
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    SizedBox(width: 92, child: Text(_shortDate(s['date']), style: const TextStyle(fontSize: 12, color: AppColors.dim))),
                    Expanded(child: Text('${fmt2(kg)} kg', style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700))),
                    if (goal != null)
                      Text('${kg - asDouble(goal) > 0 ? '+' : ''}${fmtNum(kg - asDouble(goal))} to goal',
                          style: const TextStyle(fontSize: 11, color: AppColors.faint)),
                  ],
                ),
              );
            })),
        ],
      ),
    );
  }

  Widget _bmiBar(double bmi) {
    // 15..35 BMI mapped across the bar, with the category bands
    const lo = 15.0, hi = 35.0;
    final f = ((bmi - lo) / (hi - lo)).clamp(0.02, 0.98);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(999),
          child: SizedBox(
            height: 10,
            child: Row(
              children: const [
                Expanded(flex: 35, child: ColoredBox(color: Color(0xFF3D5A99))), // <18.5
                Expanded(flex: 65, child: ColoredBox(color: Color(0xFF2E7D57))), // 18.5–25
                Expanded(flex: 50, child: ColoredBox(color: Color(0xFF8A6A2A))), // 25–30
                Expanded(flex: 50, child: ColoredBox(color: Color(0xFF7A2E3A))), // 30+
              ],
            ),
          ),
        ),
        const SizedBox(height: 4),
        LayoutBuilder(builder: (ctx, c) {
          return Stack(
            children: [
              Positioned(
                left: (c.maxWidth * f) - 9,
                child: const Icon(Icons.arrow_drop_down, size: 18, color: AppColors.text),
              ),
              const SizedBox(height: 18),
            ],
          );
        }),
        const SizedBox(height: 16),
        const Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('15', style: TextStyle(fontSize: 9.5, color: AppColors.faint)),
            Text('18.5', style: TextStyle(fontSize: 9.5, color: AppColors.faint)),
            Text('25', style: TextStyle(fontSize: 9.5, color: AppColors.faint)),
            Text('30', style: TextStyle(fontSize: 9.5, color: AppColors.faint)),
            Text('35', style: TextStyle(fontSize: 9.5, color: AppColors.faint)),
          ],
        ),
      ],
    );
  }

  Future<void> _openWeightSheet(BuildContext context) async {
    final ctrl = TextEditingController(
        text: widget.insights?['weight_kg'] == null ? '' : fmtNum(widget.insights!['weight_kg']));
    final note = TextEditingController();
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom, top: 16, left: 16, right: 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Log weight', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            TextField(
              controller: ctrl,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Weight (kg)', isDense: true),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
            const SizedBox(height: 10),
            TextField(controller: note, decoration: const InputDecoration(labelText: 'Note (optional)', isDense: true)),
            const SizedBox(height: 14),
            Row(
              children: [
                const Spacer(),
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                FilledButton(
                  onPressed: () async {
                    final kg = double.tryParse(ctrl.text.trim());
                    if (kg == null) return;
                    try {
                      final todayIso = DateFormat('yyyy-MM-dd').format(DateTime.now());
                      await Api.send('POST', 'fitness/weight/', {
                        'date': todayIso,
                        'weight_kg': kg,
                        if (note.text.trim().isNotEmpty) 'notes': note.text.trim(),
                      }, label: 'Weight ${kg}kg · $todayIso', dedupeId: 'weight-$todayIso');
                      if (ctx.mounted) Navigator.pop(ctx, true);
                    } catch (e) {
                      if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('Failed: $e')));
                    }
                  },
                  child: const Text('Save'),
                ),
              ],
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    ctrl.dispose();
    note.dispose();
    if (saved == true) await widget.onChanged();
  }

  /// Small profile sheet so height/goal can be set from the fitness flow too —
  /// the same Settings keys the Settings screen writes.
  Future<void> _openProfileSheet(BuildContext context) async {
    final ins = widget.insights ?? {};
    final height = TextEditingController(text: ins['height_cm'] == null ? '' : fmtNum(ins['height_cm']));
    final goal = TextEditingController(text: ins['goal_weight_kg'] == null ? '' : fmtNum(ins['goal_weight_kg']));
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom, top: 16, left: 16, right: 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Body profile', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            const Text('Used for BMI and goal tracking.', style: TextStyle(fontSize: 11.5, color: AppColors.faint)),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: height,
                    decoration: const InputDecoration(labelText: 'Height (cm)', isDense: true),
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: TextField(
                    controller: goal,
                    decoration: const InputDecoration(labelText: 'Goal weight (kg)', isDense: true),
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                const Spacer(),
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                FilledButton(
                  onPressed: () async {
                    try {
                      if (height.text.trim().isNotEmpty) {
                        await Api.send('POST', 'settings/', {'key': 'height_cm', 'value': height.text.trim()},
                            label: 'Height', dedupeId: 'setting-height_cm');
                      }
                      if (goal.text.trim().isNotEmpty) {
                        await Api.send('POST', 'settings/', {'key': 'goal_weight_kg', 'value': goal.text.trim()},
                            label: 'Goal weight', dedupeId: 'setting-goal_weight_kg');
                      }
                      if (ctx.mounted) Navigator.pop(ctx, true);
                    } catch (e) {
                      if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('Failed: $e')));
                    }
                  },
                  child: const Text('Save'),
                ),
              ],
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    height.dispose();
    goal.dispose();
    if (saved == true) await widget.onChanged();
  }

  static Color _bmiColor(double bmi) {
    if (bmi < 18.5) return AppColors.blue;
    if (bmi < 25) return AppColors.emerald;
    if (bmi < 30) return AppColors.amber;
    return AppColors.danger;
  }
}

String _shortDate(dynamic iso) {
  final d = DateTime.tryParse((iso ?? '').toString());
  return d == null ? '' : DateFormat('dd MMM').format(d);
}

// =====================================================================
// Measures — circumference chart per site
// =====================================================================
class _MeasuresTab extends StatefulWidget {
  final Map<String, dynamic>? measurements;
  final Future<void> Function() onChanged;
  const _MeasuresTab({this.measurements, required this.onChanged});

  @override
  State<_MeasuresTab> createState() => _MeasuresTabState();
}

class _MeasuresTabState extends State<_MeasuresTab> {
  String _site = 'waist_cm';

  static const _siteLabels = <String, String>{
    'bodyweight_kg': 'Weight (kg)',
    'neck_cm': 'Neck',
    'chest_cm': 'Chest',
    'waist_cm': 'Waist',
    'hips_cm': 'Hips',
    'left_arm_cm': 'L arm',
    'right_arm_cm': 'R arm',
    'left_thigh_cm': 'L thigh',
    'right_thigh_cm': 'R thigh',
    'left_calf_cm': 'L calf',
    'right_calf_cm': 'R calf',
    'body_fat_pct': 'Body fat (%)',
  };

  @override
  Widget build(BuildContext context) {
    final m = widget.measurements ?? {};
    final latest = (m['latest'] as Map? ?? {});
    final seriesMap = (m['series'] as Map? ?? {});
    final results = (m['results'] as List? ?? []);
    final unit = _site == 'body_fat_pct' ? '%' : 'cm';
    final siteSeries = (seriesMap[_site] as List? ?? []);
    final points = [
      for (final p in siteSeries) ChartPoint(_shortDate(p['date']), asDouble(p['value'])),
    ];

    return RefreshIndicator(
      onRefresh: widget.onChanged,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          SectionLabel('Latest', icon: Icons.straighten, trailing: TextButton.icon(
            onPressed: () => _openMeasureSheet(context, latest),
            icon: const Icon(Icons.add, size: 15),
            label: const Text('Log'),
          )),
          AppCard(
            child: Column(
              children: [
                for (final e in _siteLabels.entries)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 5),
                    child: InkWell(
                      onTap: () => setState(() => _site = e.key),
                      borderRadius: BorderRadius.circular(8),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(e.value,
                                style: TextStyle(
                                    fontSize: 12.5,
                                    color: _site == e.key ? AppColors.text : AppColors.dim,
                                    fontWeight: _site == e.key ? FontWeight.w800 : FontWeight.w500)),
                          ),
                          Text(latest[e.key] == null ? '—' : fmtNum(latest[e.key]),
                              style: TextStyle(
                                  fontSize: 13.5,
                                  fontWeight: FontWeight.w800,
                                  color: latest[e.key] == null ? AppColors.faint : AppColors.text)),
                          const SizedBox(width: 8),
                          Icon(Icons.show_chart, size: 15,
                              color: _site == e.key ? AppColors.violet : AppColors.faint),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          SectionLabel('${_siteLabels[_site]} trend', icon: Icons.timeline),
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(child: StatBlock(latest[_site] == null ? '—' : fmtNum(latest[_site]), 'latest $unit', color: AppColors.violet)),
                    Expanded(child: StatBlock('${points.length}', 'entries', color: AppColors.sky)),
                    Expanded(
                      child: StatBlock(
                        points.length < 2 ? '—' : fmtNum(points.last.value - points.first.value),
                        'total $unit',
                        color: points.length >= 2 && points.last.value <= points.first.value
                            ? AppColors.greenText
                            : AppColors.amber,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                LineChart(points: points, color: AppColors.violet, height: 170, unit: unit),
              ],
            ),
          ),
          const SizedBox(height: 14),
          SectionLabel('History', icon: Icons.history),
          if (results.isEmpty)
            const Text('No measurements logged yet.', style: TextStyle(color: AppColors.dim))
          else
            ...results.take(15).map((r) => AppCard(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(DateFormat('EEE, dd MMM yyyy').format(DateTime.parse(r['date'])),
                              style: const TextStyle(fontWeight: FontWeight.w800)),
                          const Spacer(),
                          IconButton(
                            visualDensity: VisualDensity.compact,
                            icon: const Icon(Icons.delete_outline, size: 17, color: AppColors.faint),
                            onPressed: () async {
                              await Api.delete('body-measurements/${r['id']}/', null, true,
                                  'Delete measurements');
                              await widget.onChanged();
                            },
                          ),
                        ],
                      ),
                      Wrap(spacing: 6, runSpacing: 6, children: [
                        for (final e in _siteLabels.entries)
                          if (r[e.key] != null)
                            Pill('${e.value} ${fmtNum(r[e.key])}', color: AppColors.violet),
                      ]),
                    ],
                  ),
                )),
        ],
      ),
    );
  }

  Future<void> _openMeasureSheet(BuildContext context, Map latest) async {
    final ctrls = {
      for (final k in _siteLabels.keys)
        k: TextEditingController(text: latest[k] == null ? '' : fmtNum(latest[k])),
    };
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom, top: 16, left: 16, right: 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Measurements', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            const SizedBox(height: 4),
            const Text('Blank fields are left unchanged for today. Prefilled with the latest values.',
                style: TextStyle(fontSize: 11.5, color: AppColors.faint)),
            const SizedBox(height: 12),
            SizedBox(
              height: 330,
              child: SingleChildScrollView(
                child: Column(
                  children: _siteLabels.entries.map((e) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: TextField(
                          controller: ctrls[e.key],
                          decoration: InputDecoration(labelText: e.value, isDense: true),
                          keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        ),
                      )).toList(),
                ),
              ),
            ),
            Row(
              children: [
                const Spacer(),
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                FilledButton(
                  onPressed: () async {
                    final body = <String, dynamic>{
                      'date': DateFormat('yyyy-MM-dd').format(DateTime.now()),
                    };
                    for (final e in ctrls.entries) {
                      final t = e.value.text.trim();
                      if (t.isNotEmpty) body[e.key] = double.tryParse(t);
                    }
                    try {
                      await Api.send('POST', 'body-measurements/', body,
                          label: 'Measurements · ${body['date']}',
                          dedupeId: 'measures-${body['date']}');
                      if (ctx.mounted) Navigator.pop(ctx, true);
                    } catch (err) {
                      if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('Failed: $err')));
                    }
                  },
                  child: const Text('Save'),
                ),
              ],
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    for (final c in ctrls.values) {
      c.dispose();
    }
    if (saved == true) await widget.onChanged();
  }
}

// =====================================================================
// Drinks — water and other beverages
// =====================================================================
class _DrinksTab extends StatefulWidget {
  final Map<String, dynamic>? drinks;
  final List<dynamic> presets;
  final Future<void> Function() onChanged;
  const _DrinksTab({this.drinks, required this.presets, required this.onChanged});

  @override
  State<_DrinksTab> createState() => _DrinksTabState();
}

class _DrinksTabState extends State<_DrinksTab> {
  bool _busy = false;

  @override
  Widget build(BuildContext context) {
    final d = widget.drinks ?? {};
    final summary = (d['summary'] as Map? ?? {});
    final rows = (d['results'] as List? ?? []);
    final presets = widget.presets;

    final totalMl = asInt(summary['total_ml']);
    final waterMl = asInt(summary['water_ml']);
    final goal = asInt(summary['water_goal_ml'], 3000);
    final hydration = asInt(summary['hydration_pct']);
    final caffeine = asInt(summary['caffeine_mg']);
    final kcal = asInt(summary['calories']);
    final byType = (summary['by_type'] as List? ?? []);

    return RefreshIndicator(
      onRefresh: widget.onChanged,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          // ---------------- hydration ring
          AppCard(
            gradient: LinearGradient(
              colors: [AppColors.blue.withValues(alpha: 0.18), AppColors.surface],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    SizedBox(
                      width: 78,
                      height: 78,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          SizedBox(
                            width: 78,
                            height: 78,
                            child: CircularProgressIndicator(
                              value: goal == 0 ? 0 : (waterMl / goal).clamp(0.0, 1.0),
                              strokeWidth: 8,
                              backgroundColor: AppColors.track,
                              color: AppColors.blue,
                            ),
                          ),
                          Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text('$hydration%', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
                              const Text('hydration', style: TextStyle(fontSize: 8.5, color: AppColors.faint)),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('$waterMl ml water',
                              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
                          Text('of $goal ml goal', style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Pill('${totalMl}ml total', color: AppColors.sky),
                              const SizedBox(width: 6),
                              Pill('${asInt(summary['count'])} drinks', color: AppColors.violet),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(child: StatBlock('$caffeine', 'mg caffeine', color: AppColors.amber)),
                    Expanded(child: StatBlock('$kcal', 'kcal from drinks', color: AppColors.violet)),
                    Expanded(child: StatBlock('${byType.length}', 'drink types', color: AppColors.sky)),
                  ],
                ),
              ],
            ),
          ),

          // ---------------- one-tap presets
          const SizedBox(height: 14),
          SectionLabel('Log a drink', icon: Icons.local_drink_outlined),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: presets.map((p) {
              final type = p['drink_type'].toString();
              final color = hexColor(p['color']?.toString(), AppColors.blue);
              return InkWell(
                onTap: _busy ? null : () => _log(type),
                borderRadius: BorderRadius.circular(14),
                child: Container(
                  width: 92,
                  padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: color.withValues(alpha: 0.4)),
                  ),
                  child: Column(
                    children: [
                      Text(p['emoji']?.toString() ?? '🥤', style: const TextStyle(fontSize: 26)),
                      const SizedBox(height: 5),
                      Text(p['label']?.toString() ?? type,
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                      Text('${asInt(p['ml'])} ml', style: const TextStyle(fontSize: 10, color: AppColors.faint)),
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 6),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: _busy ? null : () => _logCustom(context),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Custom amount'),
            ),
          ),

          // ---------------- by type
          if (byType.isNotEmpty) ...[
            const SizedBox(height: 8),
            SectionLabel('Today by type', icon: Icons.pie_chart_outline),
            AppCard(
              child: Column(
                children: [
                  for (final t in byType)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 5),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 90,
                            child: Text(_label(t['drink_type'].toString()),
                                style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
                          ),
                          Expanded(
                            child: ProgressBar(
                              value: totalMl == 0 ? 0 : asInt(t['volume_ml']) / totalMl,
                              color: _colorFor(t['drink_type'].toString()),
                              height: 7,
                            ),
                          ),
                          const SizedBox(width: 8),
                          SizedBox(width: 62, child: Text('${asInt(t['volume_ml'])} ml',
                              textAlign: TextAlign.right, style: const TextStyle(fontSize: 11.5))),
                          SizedBox(width: 34, child: Text('×${asInt(t['count'])}',
                              textAlign: TextAlign.right, style: const TextStyle(fontSize: 11, color: AppColors.faint))),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ],

          // ---------------- today's drinks
          const SizedBox(height: 14),
          SectionLabel('Today\'s log', icon: Icons.receipt_long_outlined),
          if (rows.isEmpty)
            const Text('Nothing logged today — tap a drink above.', style: TextStyle(color: AppColors.dim))
          else
            ...rows.map((raw) {
              final r = Map<String, dynamic>.from(raw as Map);
              final color = _colorFor(r['drink_type'].toString());
              final t = (r['time'] as String?) == null ? null : _clock(r['time'].toString());
              return AppCard(
                margin: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    Container(
                      width: 34,
                      height: 34,
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.16),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      alignment: Alignment.center,
                      child: Icon(Icons.local_drink, size: 17, color: color),
                    ),
                    const SizedBox(width: 11),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${_label(r['drink_type'].toString())} · ${asInt(r['volume_ml'])} ml',
                              style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800)),
                          if (asInt(r['caffeine_mg']) > 0 || asInt(r['calories']) > 0)
                            Text(
                              [
                                if (asInt(r['caffeine_mg']) > 0) '${asInt(r['caffeine_mg'])}mg caffeine',
                                if (asInt(r['calories']) > 0) '${asInt(r['calories'])} kcal',
                              ].join(' · '),
                              style: const TextStyle(fontSize: 11, color: AppColors.dim),
                            ),
                        ],
                      ),
                    ),
                    if (t != null) Text(t, style: const TextStyle(fontSize: 11, color: AppColors.faint)),
                    IconButton(
                      visualDensity: VisualDensity.compact,
                      icon: const Icon(Icons.delete_outline, size: 17, color: AppColors.faint),
                      onPressed: () => _remove(asInt(r['id'])),
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  /// Friendly name for a drink type, for Sync labels.
  String _drinkLabel(String type) {
    for (final p in widget.presets) {
      if (p['drink_type']?.toString() == type) {
        return p['label']?.toString() ?? type;
      }
    }
    return type;
  }

  Future<void> _log(String type, [int? ml]) async {    setState(() => _busy = true);
    try {
      final body = <String, dynamic>{
        'drink_type': type,
        'date': DateFormat('yyyy-MM-dd').format(DateTime.now()),
        'time': DateFormat('HH:mm:ss').format(DateTime.now()),
      };
      if (ml != null) body['volume_ml'] = ml;
      // Drinks are discrete events: each tap must survive as its own queued
      // op. The key includes a millisecond stamp so two taps in the same
      // second never collapse into one.
      await Api.send('POST', 'drinks/', body,
          label: '${_drinkLabel(type)}${ml == null ? '' : ' ${ml}ml'}',
          dedupeId: 'drink-${DateTime.now().microsecondsSinceEpoch}');
      await widget.onChanged();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _remove(int id) async {
    try {
      await Api.delete('drinks/$id/', null, true, 'Remove drink');
      await widget.onChanged();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  Future<void> _logCustom(BuildContext context) async {
    final type = ValueNotifier<String>(widget.presets.isEmpty ? 'water' : widget.presets.first['drink_type'].toString());
    final amt = TextEditingController(text: '250');
    await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (ctx) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom, top: 16, left: 16, right: 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Custom drink', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            const SizedBox(height: 12),
            ValueListenableBuilder<String>(
              valueListenable: type,
              builder: (_, v, child) => DropdownButtonFormField<String>(
                initialValue: v,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Type', isDense: true),
                dropdownColor: AppColors.surface2,
                items: [
                  for (final p in widget.presets)
                    DropdownMenuItem(value: p['drink_type'].toString(), child: Text(p['label'].toString())),
                ],
                onChanged: (nv) => type.value = nv ?? v,
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: amt,
              decoration: const InputDecoration(labelText: 'Volume (ml)', isDense: true),
              keyboardType: TextInputType.number,
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                const Spacer(),
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
                FilledButton(
                  onPressed: () async {
                    final ml = int.tryParse(amt.text.trim());
                    if (ml == null) return;
                    Navigator.pop(ctx, false); // _log refreshes the tab itself
                    await _log(type.value, ml);
                  },
                  child: const Text('Log'),
                ),
              ],
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    amt.dispose();
    type.dispose();
  }

  String _label(String type) {
    for (final p in widget.presets) {
      if (p['drink_type'] == type) return p['label'].toString();
    }
    return type.isEmpty ? type : type[0].toUpperCase() + type.substring(1);
  }

  Color _colorFor(String type) {
    for (final p in widget.presets) {
      if (p['drink_type'] == type) return hexColor(p['color']?.toString(), AppColors.blue);
    }
    return AppColors.blue;
  }

  static String _clock(String raw) {
    final p = raw.split(':');
    if (p.length < 2) return raw;
    final h = int.tryParse(p[0]) ?? 0;
    final ampm = h < 12 ? 'am' : 'pm';
    final hh = h % 12 == 0 ? 12 : h % 12;
    return '$hh:${p[1]}$ampm';
  }
}


// =====================================================================
// Library — the exercise catalog
// =====================================================================
class _LibraryTab extends StatefulWidget {
  final List<dynamic> exercises;
  const _LibraryTab({required this.exercises});

  @override
  State<_LibraryTab> createState() => _LibraryTabState();
}

class _LibraryTabState extends State<_LibraryTab> {
  String _q = '';
  String? _muscle;

  @override
  Widget build(BuildContext context) {
    final muscles = <String>{};
    for (final e in widget.exercises) {
      final m = e['muscle']?.toString();
      if (m != null && m.isNotEmpty) muscles.add(m);
    }
    final filtered = widget.exercises.where((e) {
      final n = (e['name'] as String).toLowerCase();
      final m = (e['muscle'] as String).toLowerCase();
      final okQ = _q.isEmpty || n.contains(_q) || m.contains(_q);
      final okM = _muscle == null || m == _muscle!.toLowerCase();
      return okQ && okM;
    }).toList();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              TextField(
                decoration: const InputDecoration(labelText: 'Search exercises…', isDense: true, prefixIcon: Icon(Icons.search, size: 18)),
                onChanged: (v) => setState(() => _q = v.toLowerCase()),
              ),
              const SizedBox(height: 8),
              SizedBox(
                height: 34,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: ChoiceChip(label: const Text('All'), selected: _muscle == null, onSelected: (_) => setState(() => _muscle = null)),
                    ),
                    for (final m in (muscles.toList()..sort()))
                      Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: ChoiceChip(label: Text(m), selected: _muscle == m, onSelected: (_) => setState(() => _muscle = m)),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: filtered.isEmpty
              ? const EmptyState(icon: Icons.search_off, title: 'No exercises match', subtitle: 'Try a different search or muscle group.')
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(12, 0, 12, 20),
                  itemCount: filtered.length,
                  itemBuilder: (_, i) {
                    final e = filtered[i];
                    return AppCard(
                      margin: const EdgeInsets.only(bottom: 8),
                      onTap: () => _showDetail(e),
                      child: Row(
                        children: [
                          Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              color: AppColors.violet.withValues(alpha: 0.14),
                              borderRadius: BorderRadius.circular(10),
                            ),
                            alignment: Alignment.center,
                            child: Icon(
                              e['is_cardio'] == true ? Icons.directions_run : Icons.fitness_center,
                              size: 18,
                              color: AppColors.violet,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(e['name'], style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
                                Text('${e['muscle']} • ${e['equipment']}', style: const TextStyle(fontSize: 11, color: AppColors.faint)),
                              ],
                            ),
                          ),
                          if (e['is_compound'] == true) Pill('compound', color: AppColors.sky),
                        ],
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  void _showDetail(Map e) {
    final secondary = (e['secondary'] as List? ?? []);
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (ctx) => Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(e['name'], style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
            const SizedBox(height: 8),
            Wrap(spacing: 6, runSpacing: 6, children: [
              Pill(e['muscle']?.toString() ?? '—', color: AppColors.violet, filled: true),
              Pill(e['equipment']?.toString() ?? '—', color: AppColors.dim),
              if (e['is_compound'] == true) const Pill('compound', color: AppColors.sky),
              if (e['is_cardio'] == true) const Pill('cardio', color: AppColors.amber),
            ]),
            if (secondary.isNotEmpty) ...[
              const SizedBox(height: 12),
              const Text('Secondary muscles', style: TextStyle(fontSize: 12, color: AppColors.faint, fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              Wrap(spacing: 6, runSpacing: 6, children: secondary.map((s) => Pill(s.toString(), color: AppColors.dim)).toList()),
            ],
            const SizedBox(height: 14),
            const Text('How to perform', style: TextStyle(fontSize: 12, color: AppColors.faint, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Text(
              (e['instructions'] ?? '').toString().isEmpty ? 'No cues recorded for this exercise yet.' : e['instructions'].toString(),
              style: const TextStyle(fontSize: 13, height: 1.5),
            ),
            const SizedBox(height: 18),
          ],
        ),
      ),
    );
  }
}
