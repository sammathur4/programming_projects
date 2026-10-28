import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../theme.dart';

class GoalsScreen extends StatefulWidget {
  const GoalsScreen({super.key});

  @override
  State<GoalsScreen> createState() => _GoalsScreenState();
}

class _GoalsScreenState extends State<GoalsScreen> {
  List<dynamic> _objectives = [];
  bool _loading = true;
  String? _error;
  bool _showDone = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final r = await Api.get('objectives/');
      setState(() {
        _objectives = r is List ? r : [];
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _action(Map<String, dynamic> o, String action) async {
    try {
      if (action == 'delete') {
        await Api.delete('objectives/${o['id']}/', null, true, 'Delete goal');
      } else {
        await Api.post('objectives/${o['id']}/$action/');
      }
      await _load();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(action == 'delete' ? 'Goal deleted' : 'Goal: $action'),
          duration: const Duration(seconds: 2),
        ));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  Future<void> _edit([Map<String, dynamic>? o]) async {
    final changed = await showDialog<bool>(
      context: context,
      builder: (_) => _GoalEditDialog(objective: o),
    );
    if (changed == true) await _load();
  }

  Future<void> _checkpoint(Map<String, dynamic> o) async {
    final r = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => _CheckpointDialog(objective: o),
    );
    if (r == null) return;
    try {
      await Api.send('POST', 'objectives/${o['id']}/checkpoint/', r,
          label: 'Goal checkpoint', dedupeId: 'goal-cp-${o['id']}-${r['date']}');
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  Future<void> _delete(Map<String, dynamic> o) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Delete goal?'),
        content: Text('“${o['area']}” will be hidden (soft delete). You can restore it later.'),
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
    if (confirm == true) await _action(o, 'delete');
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    if (_loading && _objectives.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null && _objectives.isEmpty) {
      return ErrorPane(message: _error!, onRetry: _load);
    }

    final active = _objectives.where((o) => o['status'] == 'active' || o['status'] == 'paused').toList();
    final done = _objectives.where((o) => o['status'] == 'done').toList();
    final dropped = _objectives
        .where((o) => o['status'] != 'active' && o['status'] != 'paused' && o['status'] != 'done')
        .toList();

    return RefreshIndicator(
      onRefresh: () async {
        await _load();
        await state.loadStats();
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 24),
        children: [
          if (state.stats != null) _MomentumCard(stats: state.stats!),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: SectionLabel('Mission Objectives', icon: Icons.flag_outlined)),
              TextButton.icon(
                onPressed: () => _edit(),
                icon: const Icon(Icons.add, size: 17),
                label: const Text('Add'),
              ),
            ],
          ),
          ...active.map((o) => _GoalCard(
                item: Map<String, dynamic>.from(o as Map),
                onEdit: () => _edit(o as Map<String, dynamic>),
                onAction: (a) => _action(o as Map<String, dynamic>, a),
                onDelete: () => _delete(o as Map<String, dynamic>),
                onCheckpoint: () => _checkpoint(o as Map<String, dynamic>),
              )),
          if (done.isNotEmpty || dropped.isNotEmpty) ...[
            const SizedBox(height: 14),
            InkWell(
              onTap: () => setState(() => _showDone = !_showDone),
              child: Row(
                children: [
                  const Icon(Icons.archive_outlined, size: 15, color: AppColors.dim),
                  const SizedBox(width: 6),
                  Text('Archived (${done.length + dropped.length})',
                      style: const TextStyle(fontSize: 13, color: AppColors.dim)),
                  Icon(_showDone ? Icons.expand_less : Icons.expand_more,
                      size: 18, color: AppColors.dim),
                ],
              ),
            ),
            if (_showDone) ...[
              const SizedBox(height: 8),
              ...done.map((o) => _GoalCard(
                    item: Map<String, dynamic>.from(o as Map),
                    dimmed: true,
                    onEdit: () => _edit(o as Map<String, dynamic>),
                    onAction: (a) => _action(o as Map<String, dynamic>, a),
                    onDelete: () => _delete(o as Map<String, dynamic>),
                    onCheckpoint: () => _checkpoint(o as Map<String, dynamic>),
                  )),
              ...dropped.map((o) => _GoalCard(
                    item: Map<String, dynamic>.from(o as Map),
                    dimmed: true,
                    onEdit: () => _edit(o as Map<String, dynamic>),
                    onAction: (a) => _action(o as Map<String, dynamic>, a),
                    onDelete: () => _delete(o as Map<String, dynamic>),
                    onCheckpoint: () => _checkpoint(o as Map<String, dynamic>),
                  )),
            ],
          ],
        ],
      ),
    );
  }
}

/// Habit-intelligence card at the top of Goals.
class _MomentumCard extends StatelessWidget {
  final Map<String, dynamic> stats;
  const _MomentumCard({required this.stats});

  @override
  Widget build(BuildContext context) {
    final consistency = stats['consistency_30d'] ?? 0;
    final recovery = stats['recovery'] as Map<String, dynamic>?;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.insights, size: 18, color: AppColors.sky),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Pace overview',
                  style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800, color: AppColors.text),
                ),
              ),
              Pill('$consistency% 30d', color: AppColors.sky),
            ],
          ),
          if (recovery != null && (recovery['label'] != null || recovery['rate'] != null)) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.replay, size: 13, color: AppColors.violet),
                const SizedBox(width: 6),
                Text('Recovery: ${recovery['label']} (${recovery['rate']}%)',
                    style: const TextStyle(fontSize: 11.5, color: AppColors.violet)),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _GoalCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final bool dimmed;
  final VoidCallback onEdit;
  final void Function(String action) onAction;
  final VoidCallback onDelete;
  final VoidCallback onCheckpoint;

  const _GoalCard({
    required this.item,
    this.dimmed = false,
    required this.onEdit,
    required this.onAction,
    required this.onDelete,
    required this.onCheckpoint,
  });

  @override
  Widget build(BuildContext context) {
    final status = (item['status'] as String? ?? 'active');
    final analysis = item['habit_analysis'] as Map<String, dynamic>? ?? {};
    final progress = asInt(item['progress']);
    final elapsed = item['days_elapsed'];
    final left = item['days_left'];
    final target = (item['target_date'] as String? ?? '');
    final expected = analysis['expected_pace_pct'];
    final linked = (analysis['linked'] as List? ?? []);
    final checkpoints = (item['checkpoints'] as List? ?? []);
    final color = progress >= 70
        ? AppColors.emerald
        : progress >= 40
            ? AppColors.amber
            : AppColors.rose;

    final statusColor = status == 'paused'
        ? AppColors.amber
        : status == 'done'
            ? AppColors.emerald
            : status == 'active'
                ? AppColors.greenText
                : AppColors.faint;

    return Opacity(
      opacity: dimmed ? 0.62 : 1,
      child: AppCard(
        margin: const EdgeInsets.only(bottom: 11),
        onTap: onEdit,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(item['area'] ?? '',
                      style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800)),
                ),
                Pill(status, color: statusColor, filled: true),
                PopupMenuButton<String>(
                  icon: const Icon(Icons.more_vert, size: 19, color: AppColors.dim),
                  color: AppColors.surface2,
                  onSelected: (v) {
                    switch (v) {
                      case 'edit':
                        onEdit();
                        break;
                      case 'checkpoint':
                        onCheckpoint();
                        break;
                      case 'delete':
                        onDelete();
                        break;
                      default:
                        onAction(v);
                    }
                  },
                  itemBuilder: (_) => [
                    if (status == 'active')
                      const PopupMenuItem(
                          value: 'pause', child: _MenuRow(Icons.pause, 'Pause', AppColors.amber))
                    else if (status == 'paused')
                      const PopupMenuItem(
                          value: 'resume',
                          child: _MenuRow(Icons.play_arrow, 'Resume', AppColors.emerald)),
                    const PopupMenuItem(
                        value: 'restart',
                        child: _MenuRow(Icons.restart_alt, 'Restart', AppColors.sky)),
                    if (status != 'done')
                      const PopupMenuItem(
                          value: 'complete',
                          child: _MenuRow(Icons.check_circle, 'Mark complete', AppColors.emerald)),
                    const PopupMenuItem(
                        value: 'checkpoint',
                        child: _MenuRow(Icons.timeline, 'Log progress', AppColors.violet)),
                    const PopupMenuItem(
                        value: 'edit', child: _MenuRow(Icons.edit, 'Edit', AppColors.violet)),
                    const PopupMenuItem(
                        value: 'delete',
                        child: _MenuRow(Icons.delete_outline, 'Delete (soft)', AppColors.rose)),
                  ],
                ),
              ],
            ),
            if ((item['objective'] as String? ?? '').isNotEmpty) ...[
              const SizedBox(height: 5),
              Text(item['objective'],
                  style: const TextStyle(fontSize: 13, height: 1.35)),
            ],
            if ((item['target'] as String? ?? '').isNotEmpty) ...[
              const SizedBox(height: 7),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.flag, size: 13, color: AppColors.amber),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(item['target'],
                        style: const TextStyle(fontSize: 12, color: AppColors.dim, height: 1.35)),
                  ),
                ],
              ),
            ],

            const SizedBox(height: 12),
            // progress bar with expected-pace marker
            Row(
              children: [
                Text('$progress%',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: color)),
                const SizedBox(width: 8),
                Expanded(child: ProgressBar(value: progress / 100, color: color, height: 7)),
                if (expected != null) ...[
                  const SizedBox(width: 8),
                  Pill('pace $expected%', color: AppColors.faint),
                ],
              ],
            ),

            if (elapsed != null || left != null) ...[
              const SizedBox(height: 10),
              _TimeBar(elapsed: elapsed, left: left, target: target),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  if (elapsed != null) Pill('$elapsed days in', color: AppColors.sky, icon: Icons.hourglass_top),
                  if (left != null)
                    Pill(
                      left < 0 ? '${-left} days over' : '$left days left',
                      color: left < 0 ? AppColors.rose : AppColors.mint,
                      icon: Icons.hourglass_bottom,
                    ),
                  if (target.isNotEmpty) Pill('by $target', color: AppColors.faint),
                ],
              ),
            ],

            if (linked.isNotEmpty) ...[
              const SizedBox(height: 10),
              Row(
                children: [
                  const Icon(Icons.link, size: 13, color: AppColors.violet),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Driven by ${linked.length} habit${linked.length == 1 ? '' : 's'}'
                      '${analysis['tracked_days'] != null ? ' · ${analysis['hit_days']}/${analysis['tracked_days']} done' : ''}',
                      style: const TextStyle(fontSize: 11.5, color: AppColors.violet, height: 1.3),
                    ),
                  ),
                ],
              ),
            ],

            if (checkpoints.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Divider(height: 16),
              const Text('Recent progress',
                  style: TextStyle(fontSize: 11, color: AppColors.faint, fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              ...checkpoints.take(2).map((c) => Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Pill('${c['progress_pct']}%', color: AppColors.violet),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            '${c['note']?.toString().isNotEmpty == true ? c['note'] : 'progress logged'}'
                            '  ·  ${c['date']}',
                            style: const TextStyle(fontSize: 11.5, color: AppColors.dim, height: 1.35),
                          ),
                        ),
                      ],
                    ),
                  )),
            ],
          ],
        ),
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

// ------------------------------------------------------------------ dialogs

class GoalEditDialog extends StatefulWidget {
  final Map<String, dynamic>? objective;
  const GoalEditDialog({required this.objective});

  @override
  State<GoalEditDialog> createState() => _GoalEditDialogState();
}

class _GoalEditDialog extends GoalEditDialog {
  final Map<String, dynamic>? objective;
  _GoalEditDialog({required this.objective}) : super(objective: objective);
}

class _GoalEditDialogState extends State<GoalEditDialog> {
  late final TextEditingController _area;
  late final TextEditingController _objective;
  late final TextEditingController _target;
  late final TextEditingController _notes;
  late final TextEditingController _timeline;
  bool _saving = false;
  final Set<String> _linked = {};
  String? _startDate;
  String? _targetDate;

  bool get isNew => widget.objective == null;

  @override
  void initState() {
    super.initState();
    final o = widget.objective;
    _area = TextEditingController(text: o?['area'] as String? ?? '');
    _objective = TextEditingController(text: o?['objective'] as String? ?? '');
    _target = TextEditingController(text: o?['target'] as String? ?? '');
    _notes = TextEditingController(text: o?['notes'] as String? ?? '');
    _timeline = TextEditingController(text: o?['timeline'] as String? ?? '');
    _startDate = o?['start_date'] as String?;
    _targetDate = o?['target_date'] as String?;
    for (final l in (o?['linked_habits'] as List? ?? [])) {
      _linked.add(l.toString());
    }
  }

  @override
  void dispose() {
    _area.dispose();
    _objective.dispose();
    _target.dispose();
    _notes.dispose();
    _timeline.dispose();
    super.dispose();
  }

  Future<void> _pickDate(bool isStart) async {
    final now = DateTime.now();
    final initial = DateTime.tryParse((isStart ? _startDate : _targetDate) ?? '') ?? now;
    final picked = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(2026),
      lastDate: DateTime(2035),
      builder: (ctx, child) => Theme(
        data: Theme.of(ctx).copyWith(
          colorScheme: const ColorScheme.dark(primary: AppColors.emerald),
        ),
        child: child!,
      ),
    );
    if (picked != null) {
      setState(() {
        final iso = AppState.iso(picked);
        if (isStart) {
          _startDate = iso;
        } else {
          _targetDate = iso;
        }
      });
    }
  }

  Future<void> _save() async {
    if (_area.text.trim().isEmpty) return;
    setState(() => _saving = true);
    final body = {
      'area': _area.text.trim(),
      'objective': _objective.text.trim(),
      'target': _target.text.trim(),
      'notes': _notes.text.trim(),
      'timeline': _timeline.text.trim(),
      'linked_habits': _linked.toList(),
      'start_date': _startDate,
      'target_date': _targetDate,
    };
    try {
      if (isNew) {
        await Api.send('POST', 'objectives/', body,
            label: 'New goal', dedupeId: 'goal-new-${DateTime.now().microsecondsSinceEpoch}');
      } else {
        await Api.send('PATCH', 'objectives/${widget.objective!['id']}/', body,
            label: 'Edit goal', dedupeId: 'goal-edit-${widget.objective!['id']}');
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
    final state = context.watch<AppState>();
    final habits = (state.overview?['habits'] as List? ?? []).cast<Map<String, dynamic>>();

    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: Text(isNew ? 'New goal' : 'Edit goal'),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              TextField(
                controller: _area,
                decoration: const InputDecoration(labelText: 'Area', hintText: 'UPSC CSE 2027'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _objective,
                maxLines: 2,
                decoration: const InputDecoration(labelText: 'Objective'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _target,
                maxLines: 2,
                decoration: const InputDecoration(labelText: 'Target (what done looks like)'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _timeline,
                decoration: const InputDecoration(labelText: 'Timeline (free text)', hintText: 'May 2027'),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(child: _dateBtn('Start date', _startDate, () => _pickDate(true))),
                  const SizedBox(width: 10),
                  Expanded(child: _dateBtn('Target date', _targetDate, () => _pickDate(false))),
                ],
              ),
              const SizedBox(height: 14),
              const Text('Driven by which habits?',
                  style: TextStyle(fontSize: 12, color: AppColors.dim)),
              const SizedBox(height: 4),
              const Text(
                'Effort on these habits becomes this goal\'s progress.',
                style: TextStyle(fontSize: 10.5, color: AppColors.faint),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: habits.map((h) {
                  final key = _slug(h['name'] as String? ?? '');
                  final sel = _linked.contains(key);
                  return FilterChip(
                    label: Text('${h['emoji']} ${h['name']}',
                        style: const TextStyle(fontSize: 11)),
                    selected: sel,
                    visualDensity: VisualDensity.compact,
                    onSelected: (v) => setState(() {
                      if (v) {
                        _linked.add(key);
                      } else {
                        _linked.remove(key);
                      }
                    }),
                  );
                }).toList(),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _notes,
                maxLines: 2,
                decoration: const InputDecoration(labelText: 'Notes'),
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

  Widget _dateBtn(String label, String? value, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.surface2,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          children: [
            const Icon(Icons.event, size: 15, color: AppColors.dim),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label, style: const TextStyle(fontSize: 10, color: AppColors.faint)),
                  Text(value ?? 'not set',
                      style: TextStyle(
                          fontSize: 12,
                          color: value == null ? AppColors.faint : AppColors.text)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CheckpointDialog extends StatefulWidget {
  final Map<String, dynamic> objective;
  const _CheckpointDialog({required this.objective});

  @override
  State<_CheckpointDialog> createState() => _CheckpointDialogState();
}

class _CheckpointDialogState extends State<_CheckpointDialog> {
  late double _pct;
  final _note = TextEditingController();

  @override
  void initState() {
    super.initState();
    _pct = asDouble(widget.objective['progress']).clamp(0, 100);
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: Text('Log progress · ${widget.objective['area']}'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('${_pct.round()}%',
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
              Expanded(
                child: Slider(
                  value: _pct,
                  min: 0,
                  max: 100,
                  divisions: 20,
                  label: '${_pct.round()}%',
                  onChanged: (v) => setState(() => _pct = v),
                ),
              ),
            ],
          ),
          TextField(
            controller: _note,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'What moved?',
              hintText: 'Finished Polity Laxmikanth',
            ),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          onPressed: () => Navigator.pop(context, {
            'progress_pct': _pct.round(),
            'note': _note.text.trim(),
          }),
          child: const Text('Log'),
        ),
      ],
    );
  }
}

/// Must match the backend's habit key derivation ("5L Water" -> "5l_water").
String _slug(String name) {
  var key = name.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]+'), '_');
  key = key.replaceAll(RegExp(r'_+'), '_');
  return key.replaceAll(RegExp(r'^_|_$'), '');
}

// ---------------------------------------------------------------------------
// Time bar — elapsed vs remaining, with the target date labelled.
// ---------------------------------------------------------------------------
class _TimeBar extends StatelessWidget {
  final dynamic elapsed;
  final dynamic left;
  final String target;
  const _TimeBar({required this.elapsed, required this.left, required this.target});

  @override
  Widget build(BuildContext context) {
    final e = elapsed is int ? elapsed as int : int.tryParse('$elapsed') ?? 0;
    final l = left is int ? left as int : int.tryParse('$left') ?? 0;
    final total = (e + l).clamp(1, 1 << 30);
    final frac = (e / total).clamp(0.0, 1.0);
    final over = l < 0;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Text('time',
                style: TextStyle(fontSize: 10.5, color: AppColors.faint)),
            const Spacer(),
            Text(
              over ? 'past target by ${-l} d' : '$e d elapsed · $l d left',
              style: TextStyle(
                fontSize: 10.5,
                color: over ? AppColors.rose : AppColors.dim,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: SizedBox(
            height: 8,
            child: Row(
              children: [
                Expanded(
                  flex: (frac * 1000).round().clamp(1, 1000),
                  child: Container(color: over ? AppColors.rose : AppColors.blue),
                ),
                Expanded(
                  flex: ((1 - frac) * 1000).round().clamp(1, 1000),
                  child: Container(color: AppColors.track),
                ),
              ],
            ),
          ),
        ),
        if (target.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 3),
            child: Text('target $target',
                style: const TextStyle(fontSize: 10, color: AppColors.faint)),
          ),
      ],
    );
  }
}
