import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../theme.dart';
import 'habit_detail.dart';

class HabitsScreen extends StatefulWidget {
  const HabitsScreen({super.key});

  @override
  State<HabitsScreen> createState() => _HabitsScreenState();
}

class _HabitsScreenState extends State<HabitsScreen> {
  List<dynamic> _logs = [];
  bool _loading = true;
  String? _error;
  bool _showPaused = false;

  @override
  void initState() {
    super.initState();
    _load();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AppState>().loadHeatmap();
    });
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final to = DateTime.now();
      final from = to.subtract(const Duration(days: 29));
      final r = await Api.get('habit-logs/', {'from': AppState.iso(from), 'to': AppState.iso(to)});
      setState(() {
        _logs = r is List ? r : [];
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _refresh() async {
    final state = context.read<AppState>();
    await _load();
    await state.loadAll();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    if (_loading && state.overview == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.overview == null) {
      return ErrorPane(message: state.error ?? 'No data', onRetry: _refresh);
    }

    final habits = (state.overview!['habits'] as List).cast<Map<String, dynamic>>();
    final doneByDay = <String, Set<int>>{};
    // full status map: "habitId:date" -> done|skipped|pending
    final statusByKey = <String, String>{};
    for (final l in _logs) {
      final hid = l['habit'] as int;
      final date = l['date'] as String;
      final st = (l['status'] as String?)?.isNotEmpty == true
          ? l['status'] as String
          : (l['done'] == true ? 'done' : 'pending');
      statusByKey['$hid:$date'] = st;
      if (st == 'done') {
        doneByDay.putIfAbsent(date, () => <int>{}).add(hid);
      }
    }
    final days = List.generate(30, (i) => AppState.iso(DateTime.now().subtract(Duration(days: 29 - i))));

    final active = habits.where((h) => h['is_paused'] != true).toList();
    final paused = habits.where((h) => h['is_paused'] == true).toList();

    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 24),
        children: [
          if (_error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Text(_error!, style: const TextStyle(color: AppColors.rose, fontSize: 12)),
            ),
          _HeatmapCard(habits: active, days: days, doneByDay: doneByDay),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: SectionLabel('Habits  ${active.length} active', icon: Icons.grid_view)),
              TextButton.icon(
                onPressed: () => _editHabit(context, null),
                icon: const Icon(Icons.add, size: 17),
                label: const Text('Add'),
              ),
            ],
          ),
          ...active.map((h) => _HabitManageCard(
                habit: h,
                doneCount: days.where((d) => (doneByDay[d] ?? {}).contains(h['id'])).length,
                days: days,
                statusByKey: statusByKey,
                onCorrect: (date, status) => _correct(context, h, date, status),
                onToggle: () => state.cycleHabitStatus(h['id'] as int),
                onEdit: () => _editHabit(context, h),
                onOpen: () => _openDetail(context, h, state.today),
                onAction: (a) => _action(h, a),
                onDelete: () => _delete(h),
              )),
          if (paused.isNotEmpty) ...[
            const SizedBox(height: 16),
            InkWell(
              onTap: () => setState(() => _showPaused = !_showPaused),
              child: Row(
                children: [
                  const Icon(Icons.pause_circle_outline, size: 15, color: AppColors.amber),
                  const SizedBox(width: 6),
                  Text('Paused (${paused.length})',
                      style: const TextStyle(fontSize: 13, color: AppColors.amber)),
                  Icon(_showPaused ? Icons.expand_less : Icons.expand_more,
                      size: 18, color: AppColors.amber),
                ],
              ),
            ),
            if (_showPaused) ...[
              const SizedBox(height: 8),
              ...paused.map((h) => _HabitManageCard(
                    habit: h,
                    doneCount: days.where((d) => (doneByDay[d] ?? {}).contains(h['id'])).length,
                    days: days,
                    statusByKey: statusByKey,
                    onCorrect: (date, status) => _correct(context, h, date, status),
                    onToggle: () => state.cycleHabitStatus(h['id'] as int),
                    onEdit: () => _editHabit(context, h),
                    onOpen: () => _openDetail(context, h, state.today),
                    onAction: (a) => _action(h, a),
                    onDelete: () => _delete(h),
                  )),
            ],
          ],
        ],
      ),
    );
  }

  /// Correct a past day's status from the 30-day calendar.
  Future<void> _correct(BuildContext context, Map<String, dynamic> h, String date,
      String? current) async {
    if (date == AppState.iso(DateTime.now())) {
      // today is handled by the row toggle elsewhere; still allow correction here
    }
    final chosen = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text('${h['name']} · $date'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Set the status for this day.',
                style: TextStyle(fontSize: 12, color: AppColors.dim)),
            const SizedBox(height: 10),
            _correctionTile(context, 'Done', 'done',
                Icons.check_circle, AppColors.greenText, current),
            _correctionTile(context, 'In progress', 'in_progress',
                Icons.timelapse_rounded, AppColors.sky, current),
            _correctionTile(context, 'Skipped', 'skipped',
                Icons.redo, AppColors.amber, current),
            _correctionTile(context, 'Clear (pending)', 'pending',
                Icons.remove_circle_outline, AppColors.faint, current),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel')),
        ],
      ),
    );
    if (chosen == null) return;
    try {
      await Api.send('POST', 'habits/toggle/', {
        'habit': h['id'],
        'date': date,
        'status': chosen,
        'done': chosen == 'done',
      }, label: 'Habit · $chosen', dedupeId: 'habit-${h['id']}-$date');
      await _refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('$date set to $chosen'),
          duration: const Duration(seconds: 2),
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  Widget _correctionTile(BuildContext context, String label, String value,
      IconData icon, Color color, String? current) {
    final sel = current == value;
    return ListTile(
      dense: true,
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon, color: color, size: 20),
      title: Text(label, style: const TextStyle(fontSize: 13)),
      trailing: sel
          ? const Icon(Icons.check, size: 18, color: AppColors.greenText)
          : null,
      onTap: () => Navigator.pop(context, value),
    );
  }

  void _openDetail(BuildContext context, Map<String, dynamic> h, String date) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(22)),
      ),
      builder: (_) => HabitDetailSheet(habit: h, date: date),
    ).then((_) => _load());
  }

  Future<void> _editHabit(BuildContext context, Map<String, dynamic>? habit) async {
    final state = context.read<AppState>();
    final changed = await showDialog<bool>(
      context: context,
      builder: (_) => _HabitEditDialog(habit: habit),
    );
    if (changed == true) {
      await state.loadAll();
      await _load();
    }
  }

  Future<void> _action(Map<String, dynamic> h, String action) async {
    final state = context.read<AppState>();
    try {
      if (action == 'delete') {
        await Api.delete('habits/${h['id']}/', null, true, 'Delete habit');
      } else {
        await Api.post('habits/${h['id']}/$action/');
      }
      await state.loadAll();
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(action == 'delete' ? '${h['name']} deleted' : '${h['name']}: $action'),
          duration: const Duration(seconds: 2),
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  Future<void> _delete(Map<String, dynamic> h) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Delete habit?'),
        content: Text(
            '“${h['name']}” will be hidden and its stats removed from the app. '
            'Its history is kept, so this can be undone later (soft delete).'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppColors.rose),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    await _action(h, 'delete');
  }
}

// ------------------------------------------------------------------ heatmap

class _HeatmapCard extends StatelessWidget {
  final List<Map<String, dynamic>> habits;
  final List<String> days;
  final Map<String, Set<int>> doneByDay;
  const _HeatmapCard({required this.habits, required this.days, required this.doneByDay});

  @override
  Widget build(BuildContext context) {
    final ids = habits.map((h) => h['id'] as int).toList();
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionLabel('Last 30 days', icon: Icons.local_fire_department),
          Row(
            children: days.map((d) {
              final done = doneByDay[d] ?? {};
              final hit = ids.where(done.contains).length;
              final frac = ids.isEmpty ? 0.0 : hit / ids.length;
              return Expanded(
                child: Tooltip(
                  message: '$d · $hit/${ids.length}',
                  child: Container(
                    height: 30,
                    margin: const EdgeInsets.symmetric(horizontal: 1),
                    decoration: BoxDecoration(
                      color: frac == 0
                          ? Colors.white.withValues(alpha: 0.06)
                          : Color.lerp(AppColors.emerald.withValues(alpha: 0.3),
                              AppColors.mint, frac),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(days.first.substring(5),
                  style: const TextStyle(fontSize: 10, color: AppColors.faint)),
              Text(days.last.substring(5),
                  style: const TextStyle(fontSize: 10, color: AppColors.faint)),
            ],
          ),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ habit card

class _HabitManageCard extends StatelessWidget {
  final Map<String, dynamic> habit;
  final int doneCount;
  final List<String> days;
  final Map<String, String> statusByKey;
  final void Function(String date, String? current) onCorrect;
  final VoidCallback onToggle;
  final VoidCallback onEdit;
  final VoidCallback onOpen;
  final void Function(String action) onAction;
  final VoidCallback onDelete;

  const _HabitManageCard({
    required this.habit,
    required this.doneCount,
    required this.days,
    required this.statusByKey,
    required this.onCorrect,
    required this.onToggle,
    required this.onEdit,
    required this.onOpen,
    required this.onAction,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final color = hexColor(habit['color'] as String?);
    final pct = (doneCount / 30 * 100).round();
    final paused = habit['is_paused'] == true;
    final streak = (habit['streak'] ?? 0) as int;
    final best = (habit['best_streak'] ?? 0) as int;
    final status = (habit['status_today'] ?? '').toString();
    final toggleLabel = switch (status) {
      'done' => 'Done ✓ — tap to clear',
      'skipped' => 'Skipped — tap for done',
      'in_progress' => 'In progress — tap for done',
      _ => 'Mark done',
    };

    return AppCard(
      margin: const EdgeInsets.only(bottom: 10),
      onTap: onOpen,
      child: Column(
        children: [
          Row(
            children: [
              Text(habit['emoji'] as String? ?? '✅', style: const TextStyle(fontSize: 22)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(habit['name'] as String? ?? '',
                        style: TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 13.5,
                          decoration: paused ? TextDecoration.lineThrough : null,
                          color: paused ? AppColors.dim : AppColors.text,
                        )),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        if (paused)
                          const Pill('paused', color: AppColors.amber, icon: Icons.pause)
                        else if (streak > 0)
                          Pill('🔥 $streak d', color: AppColors.orange)
                        else
                          const Pill('no streak', color: AppColors.faint),
                        if (best > 0) ...[
                          const SizedBox(width: 6),
                          Pill('best $best', color: AppColors.violet),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('$pct%',
                      style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: color)),
                  const Text('30d', style: TextStyle(fontSize: 9.5, color: AppColors.faint)),
                ],
              ),
              PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert, size: 20, color: AppColors.dim),
                color: AppColors.surface2,
                onSelected: (v) {
                  switch (v) {
                    case 'edit':
                      onEdit();
                      break;
                    case 'pause':
                    case 'resume':
                    case 'restart':
                    case 'restore':
                      onAction(v);
                      break;
                    case 'delete':
                      onDelete();
                      break;
                  }
                },
                itemBuilder: (_) => [
                  if (paused) ...[
                    const PopupMenuItem(
                        value: 'resume',
                        child: _MenuRow(Icons.play_arrow, 'Resume', AppColors.emerald)),
                    const PopupMenuItem(
                        value: 'restart',
                        child: _MenuRow(Icons.restart_alt, 'Restart streak', AppColors.sky)),
                  ] else ...[
                    const PopupMenuItem(
                        value: 'pause', child: _MenuRow(Icons.pause, 'Pause', AppColors.amber)),
                    const PopupMenuItem(
                        value: 'restart',
                        child: _MenuRow(Icons.restart_alt, 'Restart streak', AppColors.sky)),
                  ],
                  const PopupMenuItem(
                      value: 'edit', child: _MenuRow(Icons.edit, 'Edit', AppColors.violet)),
                  const PopupMenuItem(
                      value: 'delete',
                      child: _MenuRow(Icons.delete_outline, 'Delete (soft)', AppColors.rose)),
                ],
              ),
            ],
          ),
          const SizedBox(height: 10),
          _HabitCalendar(
            habit: habit,
            days: days,
            statusByKey: statusByKey,
            onCorrect: onCorrect,
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    foregroundColor: color,
                    side: BorderSide(color: color.withValues(alpha: 0.4)),
                  ),
                  onPressed: onToggle,
                  icon: const Icon(Icons.today, size: 15),
                  label: Text(toggleLabel, style: const TextStyle(fontSize: 11.5)),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    foregroundColor: AppColors.sky,
                    side: BorderSide(color: AppColors.sky.withValues(alpha: 0.4)),
                  ),
                  onPressed: onOpen,
                  icon: const Icon(Icons.sticky_note_2_outlined, size: 15),
                  label: const Text('Note / day', style: TextStyle(fontSize: 11.5)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MenuRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;
  const _MenuRow(this.icon, this.label, this.color);

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 17, color: color),
        const SizedBox(width: 10),
        Text(label, style: const TextStyle(fontSize: 13)),
      ],
    );
  }
}

// ------------------------------------------------------------------ edit dialog

class HabitEditDialog extends StatefulWidget {
  final Map<String, dynamic>? habit;
  const HabitEditDialog({required this.habit});

  @override
  State<HabitEditDialog> createState() => _HabitEditDialogState();
}

class _HabitEditDialog extends HabitEditDialog {
  final Map<String, dynamic>? habit;
  _HabitEditDialog({required this.habit}) : super(habit: habit);
}

class _HabitEditDialogState extends State<HabitEditDialog> {
  late final TextEditingController _name;
  late final TextEditingController _emoji;
  late final TextEditingController _desc;
  late final TextEditingController _target;
  late final TextEditingController _unit;
  String _colorHex = '#22c55e';
  bool _saving = false;

  static const _palette = [
    '#22c55e', '#10b981', '#38bdf8', '#3b82f6', '#a855f7',
    '#f43f5e', '#f59e0b', '#f97316', '#ec4899', '#14b8a6',
  ];

  bool get isNew => widget.habit == null;

  @override
  void initState() {
    super.initState();
    final h = widget.habit;
    _name = TextEditingController(text: h?['name'] as String? ?? '');
    _emoji = TextEditingController(text: h?['emoji'] as String? ?? '✅');
    _desc = TextEditingController(text: h?['description'] as String? ?? '');
    _target = TextEditingController(text: h?['target_value']?.toString() ?? '');
    _unit = TextEditingController(text: h?['target_unit'] as String? ?? '');
    _colorHex = (h?['color'] as String?) ?? '#22c55e';
  }

  @override
  void dispose() {
    _name.dispose();
    _emoji.dispose();
    _desc.dispose();
    _target.dispose();
    _unit.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty) return;
    setState(() => _saving = true);
    final body = {
      'name': _name.text.trim(),
      'emoji': _emoji.text.trim().isEmpty ? '✅' : _emoji.text.trim(),
      'color': _colorHex,
      'description': _desc.text.trim(),
      'target_value': _target.text.trim().isEmpty ? null : num.tryParse(_target.text.trim()),
      'target_unit': _unit.text.trim(),
    };
    try {
      if (isNew) {
        await Api.send('POST', 'habits/', body,
            label: 'New habit · ${body['name']}',
            dedupeId: 'habit-create-${body['name']}');
      } else {
        await Api.send('PATCH', 'habits/${widget.habit!['id']}/', body,
            label: 'Edit habit · ${body['name']}',
            dedupeId: 'habit-edit-${widget.habit!['id']}');
      }
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) {
        setState(() => _saving = false);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: Text(isNew ? 'New habit' : 'Edit habit'),
      content: SizedBox(
        width: 380,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  SizedBox(
                    width: 70,
                    child: TextField(
                      controller: _emoji,
                      textAlign: TextAlign.center,
                      decoration: const InputDecoration(labelText: 'Icon'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: TextField(
                      controller: _name,
                      decoration: const InputDecoration(labelText: 'Name'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _desc,
                maxLines: 2,
                decoration: const InputDecoration(labelText: 'Why this matters (optional)'),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _target,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(labelText: 'Target (optional)'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: TextField(
                      controller: _unit,
                      decoration: const InputDecoration(labelText: 'Unit'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              const Text('Colour', style: TextStyle(fontSize: 12, color: AppColors.dim)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _palette.map((hex) {
                  final sel = hex == _colorHex;
                  return InkWell(
                    onTap: () => setState(() => _colorHex = hex),
                    borderRadius: BorderRadius.circular(20),
                    child: Container(
                      width: 30,
                      height: 30,
                      decoration: BoxDecoration(
                        color: hexColor(hex),
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: sel ? Colors.white : Colors.transparent,
                          width: 2.5,
                        ),
                      ),
                      child: sel
                          ? const Icon(Icons.check, size: 16, color: Colors.black87)
                          : null,
                    ),
                  );
                }).toList(),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
        FilledButton(
          onPressed: _saving ? null : _save,
          child: _saving
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : Text(isNew ? 'Create' : 'Save'),
        ),
      ],
    );
  }
}


class _HabitCalendar extends StatelessWidget {
  final Map<String, dynamic> habit;
  final List<String> days;
  final Map<String, String> statusByKey;
  final void Function(String date, String? current) onCorrect;
  const _HabitCalendar({
    required this.habit,
    required this.days,
    required this.statusByKey,
    required this.onCorrect,
  });

  @override
  Widget build(BuildContext context) {
    final color = hexColor(habit['color'] as String?);
    final hid = habit['id'] as int;
    final paused = habit['is_paused'] == true;
    final todayIso = AppState.iso(DateTime.now());
    final startDate = DateTime.tryParse((habit['created_at'] as String?) ?? '');
    final startIso = startDate == null ? null : AppState.iso(startDate);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: 34,
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (final d in days) _cell(context, d, hid, color, todayIso, startIso, paused),
              ],
            ),
          ),
        ),
        const SizedBox(height: 6),
        Row(
          children: [
            Text(days.first.substring(5),
                style: const TextStyle(fontSize: 9.5, color: AppColors.faint)),
            const Spacer(),
            _legendDot(color, 'Done'),
            const SizedBox(width: 8),
            _legendDot(AppColors.amber.withValues(alpha: 0.55), 'Skipped'),
            const SizedBox(width: 8),
            _legendDot(AppColors.track, 'Missed'),
            const SizedBox(width: 8),
            _legendDot(Colors.white.withValues(alpha: 0.05), 'No data'),
            const Spacer(),
            Text(days.last.substring(5),
                style: const TextStyle(fontSize: 9.5, color: AppColors.faint)),
          ],
        ),
      ],
    );
  }

  Widget _cell(BuildContext context, String date, int hid, Color color,
      String todayIso, String? startIso, bool paused) {
    final status = statusByKey['$hid:$date'];
    final isFuture = date.compareTo(todayIso) > 0;
    final beforeStart = startIso != null && date.compareTo(startIso) < 0;
    final scheduled = !isFuture && !beforeStart && !paused;

    Color bg;
    Color border = Colors.white.withValues(alpha: 0.08);
    String state;
    if (status == 'done') {
      bg = color;
      state = 'Done';
    } else if (status == 'skipped') {
      bg = AppColors.amber.withValues(alpha: 0.55);
      state = 'Skipped';
    } else if (status == 'in_progress') {
      bg = AppColors.sky.withValues(alpha: 0.45);
      state = 'In progress';
    } else if (isFuture) {
      bg = Colors.white.withValues(alpha: 0.04);
      state = 'Pending (future)';
    } else if (beforeStart || paused) {
      bg = Colors.white.withValues(alpha: 0.04);
      state = paused ? 'Not scheduled (paused)' : 'Not scheduled';
    } else if (scheduled) {
      bg = AppColors.track;
      state = 'Missed';
    } else {
      bg = Colors.white.withValues(alpha: 0.04);
      state = 'Not scheduled';
    }
    if (date == todayIso) {
      border = AppColors.mint;
    }

    final dt = DateTime.tryParse(date);
    final label = dt == null
        ? date
        : '${_wd[dt.weekday - 1]} ${dt.day} ${_mo[dt.month - 1]}';

    return Tooltip(
      message: '$label · $state${date == todayIso ? ' (today)' : ''}\n'
          'Tap to correct',
      child: GestureDetector(
        onTap: isFuture ? null : () => onCorrect(date, status),
        child: Container(
          width: 16,
          height: 16,
          margin: const EdgeInsets.only(right: 3),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(3),
            border: Border.all(color: border, width: date == todayIso ? 1.4 : 1),
          ),
        ),
      ),
    );
  }

  Widget _legendDot(Color c, String label) => Row(
        children: [
          Container(
            width: 9,
            height: 9,
            decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(2)),
          ),
          const SizedBox(width: 3),
          Text(label, style: const TextStyle(fontSize: 9, color: AppColors.faint)),
        ],
      );

  static const _wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  static const _mo = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
  ];
}
