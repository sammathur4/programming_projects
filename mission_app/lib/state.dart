import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'offline.dart';
import 'theme.dart';

class AppState extends ChangeNotifier {
  String today = AppState.iso(DateTime.now());

  Map<String, dynamic>? overview;
  List<dynamic> settings = [];
  Map<String, dynamic>? stats;
  Map<String, dynamic>? dashboard;
  Map<String, dynamic>? heatmap;
  String? visionBoardUrl; // local override; falls back to <base>/vision-board/index.html
  final Map<String, String> dayNotes = {}; // date → note, optimistic cache
  bool loading = true;

  String get dayNote => dayNotes[today] ?? '';
  String? error;

  static String iso(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  String get todayIso => iso(DateTime.parse(today));

  static String prettyDay(String date) {
    final d = DateTime.parse(date);
    return DateFormat('EEE, d MMM yyyy').format(d);
  }

  static String shortDay(String date) {
    final d = DateTime.parse(date);
    return DateFormat('d MMM').format(d);
  }

  /// Human word for a habit status, used in Sync labels.
  static String _statusWord(String status) => switch (status) {
        'done' => 'done',
        'skipped' => 'skipped',
        'in_progress' => 'in progress',
        'pending' => 'pending',
        _ => status,
      };

  static String titleCase(String s) {    if (s.trim().isEmpty) return s;
    return s
        .split(RegExp(r'\s+'))
        .map((w) => w.isEmpty ? w : w[0].toUpperCase() + w.substring(1).toLowerCase())
        .join(' ');
  }

  /// Effective vision board URL: explicit override, else the Django-hosted board.
  String get effectiveVisionBoardUrl {
    final o = visionBoardUrl?.trim();
    if (o != null && o.isNotEmpty) return o;
    return '${Api.base}/vision-board/index.html';
  }

  // ---------------------------------------------------------------- jaap
  /// The chant library.
  List<Map<String, dynamic>> jaapMantras = [];

  /// Today's counts, keyed by mantra id.
  final Map<int, int> jaapToday = {};

  /// Completed rounds today, keyed by mantra id.
  final Map<int, int> jaapMalasToday = {};

  /// The mantra the counter is currently on.
  int? jaapActiveId;

  /// Stats payload from /jaap/stats/.
  Map<String, dynamic> jaapStats = {};

  Map<String, dynamic>? get jaapActive {
    if (jaapMantras.isEmpty) return null;
    final id = jaapActiveId;
    if (id == null) return jaapMantras.first;
    for (final m in jaapMantras) {
      if (m['id'] == id) return m;
    }
    return jaapMantras.first;
  }

  int jaapCountOf(int mantraId) => jaapToday[mantraId] ?? 0;

  int jaapMalasOf(int mantraId) => jaapMalasToday[mantraId] ?? 0;

  int get jaapTodayTotal =>
      jaapToday.values.fold(0, (a, b) => a + b);

  /// Load the library, today's counts and the stats in one round trip.
  Future<void> loadJaap() async {
    try {
      final r = await Api.get('jaap/');
      final mantras = (r['mantras'] as List? ?? [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      jaapMantras = mantras;
      jaapToday.clear();
      jaapMalasToday.clear();
      for (final l in (r['logs'] as List? ?? [])) {
        final row = Map<String, dynamic>.from(l as Map);
        final id = asInt(row['mantra']);
        jaapToday[id] = asInt(row['count']);
        jaapMalasToday[id] = asInt(row['malas']);
      }
      if (jaapActiveId == null && mantras.isNotEmpty) {
        jaapActiveId = asInt(mantras.first['id']);
      }
      notifyListeners();
    } catch (e) {
      error = 'Could not load jaap';
      notifyListeners();
    }
    try {
      jaapStats = Map<String, dynamic>.from(
          await Api.get('jaap/stats/', {'days': '30'}) as Map);
      notifyListeners();
    } catch (_) {
      // stats are a nicety — the counter still works without them
    }
  }

  /// Count one bead.
  ///
  /// The count is bumped locally first so the ring moves instantly, then the
  /// tap is written to the server. Each tap is its own request, so the queue
  /// id is unique — otherwise the offline queue would collapse a hundred taps
  /// into one.
  ///
  /// Returns true when this tap completed a mala (the caller rings the bell).
  Future<bool> tapJaap(int mantraId, {int delta = 1}) async {
    final prev = jaapCountOf(mantraId);
    final beads = asInt(
      _mantraById(mantraId)?['beads'],
      asInt(_mantraById(mantraId)?['mala_size'], 108),
    );
    final next = (prev + delta).clamp(0, 1 << 30);

    jaapToday[mantraId] = next;
    jaapMalasToday[mantraId] = next ~/ beads;
    notifyListeners();

    try {
      final r = await Api.send('POST', 'jaap/tap/', {
        'mantra': mantraId,
        'date': today,
        'delta': delta,
      },
          label: 'Jaap $next',
          // unique per tap: a queued tap must never overwrite another
          dedupeId: 'jaap-$mantraId-$today-${DateTime.now().microsecondsSinceEpoch}');
      if (r is Map && r['count'] != null) {
        jaapToday[mantraId] = asInt(r['count']);
        jaapMalasToday[mantraId] = asInt(r['malas']);
        notifyListeners();
        return r['mala_completed'] == true;
      }
    } catch (e) {
      error = 'Could not save the count';
      notifyListeners();
    }
    // Fall back to the local calculation when the server could not be reached
    // (the write is queued, so it will land on the next Sync).
    final b = beads < 1 ? 1 : beads;
    return next % b == 0 && next > 0;
  }

  Map<String, dynamic>? _mantraById(int id) {
    for (final m in jaapMantras) {
      if (asInt(m['id']) == id) return m;
    }
    return null;
  }

  /// Restore the persisted Server URL, then do the first load.
  Future<void> init() async {
    await Api.init();
    await OfflineStore.load();
    await loadAll();
  }

  /// Push queued offline writes, then re-read server truth.
  ///
  /// This is what the Sync button calls. Order matters: the local queue is
  /// flushed *first* so the refresh afterwards reflects the user's own edits
  /// rather than overwriting them with stale server state.
  Future<SyncReport> sync({void Function(int, int, String)? onProgress}) async {
    syncing = true;
    syncLabel = 'Starting…';
    notifyListeners();
    SyncReport report;
    try {
      report = await SyncEngine.push(onProgress: (d, t, label) {
        syncLabel = t == 0 ? label : '${d + 1}/$t · $label';
        notifyListeners();
      });
    } catch (e) {
      report = SyncReport(pushed: 0, failed: 0, stillQueued: OfflineStore.length, error: '$e');
    }
    syncLabel = 'Refreshing…';
    notifyListeners();
    // Pull: re-read everything the UI shows, so both sides agree.
    await loadAll();
    await loadStats();
    await loadDashboard();
    syncing = false;
    lastSyncReport = report;
    syncLabel = '';
    notifyListeners();
    return report;
  }

  bool syncing = false;
  String syncLabel = '';
  SyncReport? lastSyncReport;

  /// Called by [OfflineStore] whenever the queue changes, so the header badge
  /// and any open Sync screen repaint immediately.
  void notifyQueueChanged() => notifyListeners();

  Future<void> loadAll() async {
    loading = true;
    error = null;
    notifyListeners();
    try {
      final o = await Api.get('overview/', {'date': today});
      final s = await Api.get('settings/');
      overview = o;
      settings = s;
      loading = false;
    } catch (e) {
      loading = false;
      error = e.toString();
    }
    notifyListeners();
    // secondary loads shouldn't block first paint
    loadStats();
    loadDashboard();
  }

  Future<void> loadStats() async {
    try {
      stats = await Api.get('stats/');
      notifyListeners();
    } catch (e) {
      error = e.toString();
      notifyListeners();
    }
  }

  Future<void> loadDashboard() async {
    try {
      dashboard = await Api.get('dashboard/');
      notifyListeners();
    } catch (_) {
      // dashboard is a bonus; ignore failures
    }
  }

  Future<void> loadHeatmap({int days = 120}) async {
    try {
      heatmap = await Api.get('habits/heatmap/', {'days': '$days'});
      notifyListeners();
    } catch (_) {}
  }

  Future<void> setDate(String iso) async {
    today = iso;
    loading = true;
    notifyListeners();
    try {
      overview = await Api.get('overview/', {'date': today});
    } catch (e) {
      error = e.toString();
    }
    loading = false;
    notifyListeners();
  }

  Future<void> shiftDay(int delta) async {
    final d = DateTime.parse(today).add(Duration(days: delta));
    await setDate(iso(d));
  }

  /// Cycle a habit's status for [today]: pending → done → skipped → pending.
  /// Optimistic: flips local state, reverts on failure.
  /// The four statuses a habit can carry for a day.
  static const List<String> habitStatuses = [
    'pending',
    'in_progress',
    'done',
    'skipped',
  ];

  /// Apply a status to today's overview optimistically.
  ///
  /// Returns a closure that restores the previous state, so a failed write can
  /// be rolled back. Recomputing the counters from the rows means the Today
  /// screen can never show a count that disagrees with the rows above it.
  ///
  /// Public so the behaviour can be tested without a network round trip.
  VoidCallback? applyStatusLocally(int habitId, String next) {
    if (overview == null) return null;
    final habits = List<Map<String, dynamic>>.from(
        (overview!['habits'] as List).map((h) => Map<String, dynamic>.from(h as Map)));
    final i = habits.indexWhere((h) => h['id'] == habitId);
    if (i == -1) return null;

    final prevStatus = (habits[i]['status_today'] ?? '').toString();
    final prevDone = habits[i]['done_today'] == true;
    final prevScore = overview!['daily_score'];
    final prevDoneCount = asInt(overview!['done_today']);
    final prevInProgress = asInt(overview!['in_progress_today']);
    final prevSkipped = asInt(overview!['skipped_today']);

    habits[i]['status_today'] = next;
    habits[i]['done_today'] = next == 'done';
    overview!['habits'] = habits;

    int countOf(String status) =>
        habits.where((h) => (h['status_today'] ?? '') == status).length;
    overview!['done_today'] = countOf('done');
    overview!['in_progress_today'] = countOf('in_progress');
    overview!['skipped_today'] = countOf('skipped');
    overview!['daily_score'] =
        (asDouble(overview!['done_today']) / asDouble(overview!['habit_total'], 1) * 100).round();
    notifyListeners();

    return () {
      habits[i]['status_today'] = prevStatus;
      habits[i]['done_today'] = prevDone;
      overview!['habits'] = habits;
      overview!['done_today'] = prevDoneCount;
      overview!['in_progress_today'] = prevInProgress;
      overview!['skipped_today'] = prevSkipped;
      overview!['daily_score'] = prevScore;
      notifyListeners();
    };
  }

  /// Set today's status for a habit to one of [habitStatuses].
  ///
  /// Used by the status picker (long-press the status button on Today).
  /// Sends the ABSOLUTE status, so a queued write replayed later lands on the
  /// value the user chose rather than advancing the server's state again.
  Future<void> setHabitStatusToday(int habitId, String status) async {
    if (!habitStatuses.contains(status)) return;
    final revert = applyStatusLocally(habitId, status);
    try {
      await Api.send('POST', 'habits/toggle/',
          {'habit': habitId, 'date': today, 'status': status},
          label: 'Habit · ${_statusWord(status)}',
          dedupeId: 'habit-$habitId-$today');
      loadDashboard();
    } catch (e) {
      revert?.call();
      error = 'Could not save habit';
      notifyListeners();
    }
  }

  Future<void> cycleHabitStatus(int habitId) async {
    if (overview == null) return;
    final habits = List<Map<String, dynamic>>.from(
        (overview!['habits'] as List).map((h) => Map<String, dynamic>.from(h)));
    final i = habits.indexWhere((h) => h['id'] == habitId);
    if (i == -1) return;
    final prevStatus = (habits[i]['status_today'] ?? '').toString();
    // Tap cycles the quick path only: pending → done → skipped → pending.
    // "In progress" is reachable from the status picker (long-press the
    // status button), so the common "I did it" action stays one tap.
    const order = {
      'pending': 'done',
      'in_progress': 'done',
      'done': 'skipped',
      'skipped': 'pending',
      '': 'done',
    };
    final next = order[prevStatus] ?? 'done';

    final revert = applyStatusLocally(habitId, next);
    try {
      // Send the ABSOLUTE target status, not `cycle: true`.
      // A queued write may be replayed much later, by which time the server row
      // could be in any state; a relative cycle would then land on the wrong
      // value. An explicit status makes the replay idempotent and gives true
      // last-write-wins behaviour.
      await Api.send('POST', 'habits/toggle/',
          {'habit': habitId, 'date': today, 'status': next},
          label: 'Habit · ${_statusWord(next)}',
          dedupeId: 'habit-$habitId-$today');
      loadDashboard();
    } catch (e) {
      revert?.call();
      error = 'Could not save habit';
      notifyListeners();
    }
  }

  /// Toggle a habit for [today]. Optimistic: flips local state, reverts on failure.
  Future<void> toggleHabit(int habitId) async {
    if (overview == null) return;
    final habits = List<Map<String, dynamic>>.from(
        (overview!['habits'] as List).map((h) => Map<String, dynamic>.from(h)));
    final i = habits.indexWhere((h) => h['id'] == habitId);
    if (i == -1) return;
    final prev = habits[i]['done_today'] as bool;
    final prevScore = overview!['daily_score'];
    habits[i]['done_today'] = !prev;
    habits[i]['status_today'] = !prev ? 'done' : 'pending';
    overview!['habits'] = habits;
    overview!['done_today'] = (overview!['done_today'] as int) + (prev ? -1 : 1);
    overview!['daily_score'] =
        (asDouble(overview!['done_today']) / asDouble(overview!['habit_total']) * 100).round();
    notifyListeners();
    try {
      // Absolute status (see cycleHabitStatus for why replay must not be relative).
      await Api.send('POST', 'habits/toggle/',
          {'habit': habitId, 'date': today, 'status': !prev ? 'done' : 'pending'},
          label: 'Habit · ${_statusWord(!prev ? 'done' : 'pending')}',
          dedupeId: 'habit-$habitId-$today');
      loadDashboard();
    } catch (e) {
      // revert
      habits[i]['done_today'] = prev;
      habits[i]['status_today'] = prev ? 'done' : 'pending';
      overview!['habits'] = habits;
      overview!['done_today'] = (overview!['done_today'] as int) + (prev ? 1 : -1);
      overview!['daily_score'] = prevScore;
      error = 'Could not save habit';
      notifyListeners();
    }
  }

  /// Set a habit's status explicitly (pending/done/skipped) for [date].
  Future<void> setHabitStatus(int habitId, String date, String status) async {
    try {
      await Api.send('POST', 'habits/toggle/', {'habit': habitId, 'date': date, 'status': status},
          label: 'Habit · ${_statusWord(status)}', dedupeId: 'habit-$habitId-$date');
      if (date == today) await setDate(today);
    } catch (e) {
      error = 'Could not save habit';
      notifyListeners();
    }
  }

  /// Fetch every note saved for one habit (newest first).
  Future<List<dynamic>> habitNotes(int habitId) async {
    final r = await Api.get('habits/$habitId/notes/');
    return (r is List ? r : []);
  }

  /// Append a new note to a habit. Returns the created note.
  Future<Map<String, dynamic>> addHabitNote(int habitId, String date, String text) async {
    final r = await Api.send('POST', 'habits/$habitId/notes/', {'date': date, 'text': text},
        label: 'Habit note · $date', dedupeId: 'habit-note-add-$habitId-$date');
    if (date == today) await setDate(today);
    return Map<String, dynamic>.from(r as Map);
  }

  /// Save a per-habit, per-day note (and optionally value/done).
  Future<void> saveHabitNote(int habitId, String date, String note, {num? value}) async {
    try {
      await Api.send('POST', 'habits/toggle/', {
        'habit': habitId,
        'date': date,
        'note': note,
        // the entry is only present when a value was provided
        // ignore: use_null_aware_elements
        if (value != null) 'value': value,
      }, label: 'Habit note', dedupeId: 'habit-note-$habitId-$date');
      if (date == today) await setDate(today);
    } catch (e) {
      error = 'Could not save note';
      notifyListeners();
    }
  }

  /// Set the numeric value of a count habit (e.g. water 3/5 L).
  ///
  /// There is no dedicated "value" column server-side, so a value >= 1 marks the
  /// habit done and 0 un-marks it; the number itself is kept locally for the
  /// session so the counter UI stays responsive.
  Future<void> saveHabitValue(int habitId, String date, double value) async {
    final v = value < 0 ? 0.0 : value;
    if (overview != null && date == today) {
      final habits = List<Map<String, dynamic>>.from(
          (overview!['habits'] as List).map((h) => Map<String, dynamic>.from(h as Map)));
      final i = habits.indexWhere((h) => h['id'] == habitId);
      if (i != -1) {
        habits[i]['today_value'] = v;
        habits[i]['done_today'] = v >= 1;
        overview!['habits'] = habits;
        final done = habits.where((h) => h['done_today'] == true).length;
        overview!['done_today'] = done;
        overview!['daily_score'] =
            (done / asDouble(overview!['habit_total'], 1) * 100).round();
        notifyListeners();
      }
    }
    await setHabitDone(habitId, date, v >= 1);
  }

  /// Save the free-text note for [date] (the "Note for today" card).
  Future<void> saveDayNote(String note) async {
    dayNotes[today] = note;
    notifyListeners();
    try {
      await Api.send('POST', 'day-note/', {'date': today, 'note': note},
          label: 'Day note', dedupeId: 'day-note-$today');
    } catch (_) {
      // keep the local copy; the next load will reconcile
    }
  }

  /// Mark done/undone explicitly (used by day-detail toggles).
  Future<void> setHabitDone(int habitId, String date, bool done) async {
    try {
      await Api.send('POST', 'habits/toggle/', {'habit': habitId, 'date': date, 'done': done},
          label: 'Habit · ${done ? 'done' : 'pending'}',
          dedupeId: 'habit-$habitId-$date');
    } catch (e) {
      error = 'Could not save habit';
      notifyListeners();
    }
  }

  Setting? setting(String key) {
    for (final s in settings) {
      if (s['key'] == key) return Setting(s['key'] as String, s['value'] as String);
    }
    return null;
  }

  String settingValue(String key, [String fallback = '']) =>
      setting(key)?.value ?? fallback;

  /// Patch the fitness record for [today] with [fields].
  Future<void> saveFitness(Map<String, dynamic> fields) async {
    return saveFitnessOn(today, fields);
  }

  Future<void> saveFitnessOn(String date, Map<String, dynamic> fields) async {
    try {
      final r = await Api.send('PATCH', 'fitness/$date/', fields,
          label: 'Fitness · $date', dedupeId: 'fitness-$date');
      if (r is Map && r['queued'] == true) {
        // Offline: the patch is queued, so don't clobber the local view with
        // the queue acknowledgement.
        return;
      }
      if (overview != null && date == today) {
        overview!['fitness'] = r;
        notifyListeners();
      }
    } catch (e) {
      error = 'Could not save fitness';
      notifyListeners();
    }
  }

  /// Patch the study record for [today] with [fields].
  Future<void> saveStudy(Map<String, dynamic> fields) async {
    return saveStudyOn(today, fields);
  }

  Future<void> saveStudyOn(String date, Map<String, dynamic> fields) async {
    final rawStudy = overview?['study'];
    final before = rawStudy is Map ? Map<String, dynamic>.from(rawStudy) : <String, dynamic>{};
    if (overview != null && date == today) {
      overview!['study'] = {...before, ...fields};
      notifyListeners();
    }
    try {
      final r = await Api.send('PATCH', 'study/$date/', fields,
          label: 'Study · $date', dedupeId: 'study-$date');
      if (r is Map && r['queued'] == true) {
        return; // queued offline — local optimistic value already stands
      }
      if (overview != null && date == today && r is Map) {
        overview!['study'] = Map<String, dynamic>.from(r);
        notifyListeners();
      }
    } catch (e) {
      if (overview != null && date == today) {
        overview!['study'] = before;
      }
      error = 'Could not save study';
      notifyListeners();
    }
  }

  void setVisionBoardUrl(String v) {
    visionBoardUrl = v;
    notifyListeners();
  }

  Future<void> loadVisionBoardOverride() async {
    final prefs = await SharedPreferences.getInstance();
    visionBoardUrl = prefs.getString('vision_board_url');
    notifyListeners();
  }

  Future<void> saveVisionBoardOverride(String v) async {
    final prefs = await SharedPreferences.getInstance();
    visionBoardUrl = v.trim();
    if (visionBoardUrl!.isEmpty) {
      await prefs.remove('vision_board_url');
    } else {
      await prefs.setString('vision_board_url', visionBoardUrl!);
    }
    notifyListeners();
  }

  void clearError() {
    error = null;
    notifyListeners();
  }

  // -------------------------------------------------------------------------
  // Rail aggregates — small snapshots pushed in by the screens that own them,
  // so the shared right rail can show Food / Notes / Fitness summaries without
  // re-fetching everything itself.
  // -------------------------------------------------------------------------

  /// kcal + macro totals for today's diary, and how many rows.
  DiaryTotals diaryTotals = DiaryTotals.empty;

  /// note count per tag, for the Notes rail.
  Map<String, int> noteCounts = {};

  /// the pinned note, if any, for the Notes rail.
  Map<String, dynamic>? pinnedNote;

  /// muscle → fatigue 0-100, for the Fitness rail.
  Map<String, dynamic> muscleFatigue = {};

  /// total kg lifted across every logged set, for the Fitness rail.
  double weeklyVolumeKg = 0;

  /// how many exercises exist in the library.
  int exerciseCount = 0;

  void setDiaryTotals(DiaryTotals t) {
    diaryTotals = t;
    notifyListeners();
  }

  /// Pull today's diary roll-up so the Food rail can show it.
  Future<void> loadDiaryTotals() async {
    try {
      final r = await Api.get('diary/', {'date': today});
      final t = (r['totals'] as Map? ?? {});
      setDiaryTotals(DiaryTotals(
        asDouble(t['kcal']),
        asDouble(t['protein_g']),
        asDouble(t['carbs_g']),
        asDouble(t['fat_g']),
        (r['entries'] as List? ?? []).length,
      ));
    } catch (_) {}
  }

  void setNoteSnapshot({required Map<String, int> counts, Map<String, dynamic>? pinned}) {
    noteCounts = counts;
    pinnedNote = pinned;
    notifyListeners();
  }

  void setFitnessSnapshot({
    required Map<String, dynamic> fatigue,
    required double volumeKg,
    required int exercises,
  }) {
    muscleFatigue = fatigue;
    weeklyVolumeKg = volumeKg;
    exerciseCount = exercises;
    notifyListeners();
  }

  Future<void> loadFitnessSnapshot() async {
    try {
      final fatigue = await Api.get('muscle-fatigue/');
      final history = await Api.get('workout-history/', {'limit': '7'});
      double vol = 0;
      for (final s in (history['results'] as List? ?? [])) {
        vol += asDouble((s as Map)['volume_kg']);
      }
      final ex = await Api.get('exercises/');
      setFitnessSnapshot(
        fatigue: _fatiguePct(fatigue),
        volumeKg: vol,
        exercises: asInt(ex['count'], (ex['results'] as List? ?? []).length),
      );
    } catch (_) {
      // rail extras are best-effort
    }
  }

  /// Convert `muscle-fatigue/` set counts into a 0-100 "how cooked is this
  /// muscle" percentage, where ~20 working sets in a week counts as fully
  /// fatigued. Monday-morning muscle-soreness math, nothing more.
  static Map<String, dynamic> _fatiguePct(dynamic payload) {
    final out = <String, dynamic>{};
    final muscles = (payload is Map ? payload['muscles'] : payload) as Map? ?? {};
    muscles.forEach((k, v) {
      final sets = asDouble((v as Map)['sets']);
      out[k.toString()] = (sets / 20 * 100).clamp(0, 100);
    });
    return out;
  }

  Future<void> loadNoteSnapshot() async {
    try {
      final r = await Api.get('notes/');
      final counts = <String, int>{};
      (r['counts'] as Map? ?? {}).forEach((k, v) => counts[k.toString()] = asInt(v));
      Map<String, dynamic>? pinned;
      for (final n in (r['results'] as List? ?? [])) {
        final m = Map<String, dynamic>.from(n as Map);
        if (m['pinned'] == true) {
          pinned = m;
          break;
        }
      }
      setNoteSnapshot(counts: counts, pinned: pinned);
    } catch (_) {}
  }
}

class DiaryTotals {
  final double kcal;
  final double protein;
  final double carbs;
  final double fat;
  final int items;
  const DiaryTotals(this.kcal, this.protein, this.carbs, this.fat, this.items);

  static const empty = DiaryTotals(0, 0, 0, 0, 0);
}

class Setting {
  final String key;
  final String value;
  Setting(this.key, this.value);
}

Future<String> readSavedBase() async {
  final prefs = await SharedPreferences.getInstance();
  return prefs.getString('api_base') ?? '';
}

Future<void> writeSavedBase(String v) => Api.setOverride(v);

String encodeJson(Object? o) => const JsonEncoder.withIndent('  ').convert(o);
