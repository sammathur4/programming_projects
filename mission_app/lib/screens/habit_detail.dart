import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../state.dart';
import '../theme.dart';

/// Bottom sheet for one habit on one day: status cycle, notes list, value,
/// and a short history strip so you can see how this habit has been going.
class HabitDetailSheet extends StatefulWidget {
  final Map<String, dynamic> habit;
  final String date;

  const HabitDetailSheet({super.key, required this.habit, required this.date});

  @override
  State<HabitDetailSheet> createState() => _HabitDetailSheetState();
}

class _HabitDetailSheetState extends State<HabitDetailSheet> {
  late final TextEditingController _note;
  late final TextEditingController _value;
  String _status = 'pending';
  List<dynamic> _history = [];
  List<dynamic> _notes = [];
  bool _saving = false;
  bool _savingNote = false;

  @override
  void initState() {
    super.initState();
    final h = widget.habit;
    _status = (h['status_today'] ?? (h['done_today'] == true ? 'done' : 'pending')).toString();
    _note = TextEditingController();
    _value = TextEditingController(text: h['target_value']?.toString() ?? '');
    _loadHistory();
    _loadNotes();
  }

  @override
  void dispose() {
    _note.dispose();
    _value.dispose();
    super.dispose();
  }

  Future<void> _loadHistory() async {
    try {
      final to = widget.date;
      final from = DateTime.parse(widget.date)
          .subtract(const Duration(days: 29))
          .toIso8601String()
          .substring(0, 10);
      final r = await Api.get('habit-logs/',
          {'habit': '${widget.habit['id']}', 'from': from, 'to': to});
      if (mounted) setState(() => _history = r is List ? r : []);
    } catch (_) {}
  }

  Future<void> _loadNotes() async {
    try {
      final r = await context.read<AppState>().habitNotes(widget.habit['id'] as int);
      if (mounted) setState(() => _notes = r);
    } catch (_) {}
  }

  Future<void> _setStatus(String status) async {
    setState(() => _status = status);
    await context
        .read<AppState>()
        .setHabitStatus(widget.habit['id'] as int, widget.date, status);
    _loadHistory();
  }

  Future<void> _saveValue() async {
    setState(() => _saving = true);
    await context.read<AppState>().saveHabitNote(
          widget.habit['id'] as int,
          widget.date,
          '',
          value: _value.text.trim().isEmpty ? null : num.tryParse(_value.text.trim()),
        );
    if (mounted) setState(() => _saving = false);
  }

  Future<void> _saveNote() async {
    final text = _note.text.trim();
    if (text.isEmpty) return;
    setState(() => _savingNote = true);
    try {
      final created = await context
          .read<AppState>()
          .addHabitNote(widget.habit['id'] as int, widget.date, text);
      if (mounted) {
        setState(() {
          _notes.insert(0, created);
          _note.clear(); // ready for the next note
        });
      }
    } finally {
      if (mounted) setState(() => _savingNote = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = hexColor(widget.habit['color'] as String?);
    final doneDates = _history.where((l) => l['done'] == true).map((l) => l['date'] as String).toSet();
    final skippedDates = _history
        .where((l) => (l['status'] ?? '') == 'skipped')
        .map((l) => l['date'] as String)
        .toSet();
    final inProgressDates = _history
        .where((l) => (l['status'] ?? '') == 'in_progress')
        .map((l) => l['date'] as String)
        .toSet();
    final days = List.generate(30, (i) {
      final d = DateTime.parse(widget.date).subtract(Duration(days: 29 - i));
      return AppState.iso(d);
    });

    return Padding(
      padding: EdgeInsets.only(
        left: 18,
        right: 18,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.faint,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Text(widget.habit['emoji'] as String? ?? '✅',
                    style: const TextStyle(fontSize: 26)),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(widget.habit['name'] as String? ?? '',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
                      Text(AppState.prettyDay(widget.date),
                          style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            // Two rows of two, so all four statuses fit on a phone without
            // the labels getting squeezed.
            Row(
              children: [
                Expanded(
                  child: _statusBtn('Done', Icons.check_circle, AppColors.emerald, 'done', color),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _statusBtn('In progress', Icons.timelapse_rounded, AppColors.sky, 'in_progress', color),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: _statusBtn('Pending', Icons.radio_button_unchecked, AppColors.faint, 'pending', color),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: _statusBtn('Skipped', Icons.remove_circle_outline, AppColors.amber, 'skipped', color),
                ),
              ],
            ),
            const SizedBox(height: 6),
            const Text(
              'Skipped days don\'t break your streak — they count as rest.',
              style: TextStyle(fontSize: 10.5, color: AppColors.faint),
            ),
            const SizedBox(height: 16),
            SectionLabel('Notes', icon: Icons.sticky_note_2_outlined),
            if (_notes.isNotEmpty) ...[
              for (final n in _notes)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                    decoration: BoxDecoration(
                      color: AppColors.surface2,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Text((n['text'] ?? '').toString(),
                        style: const TextStyle(fontSize: 12.5)),
                  ),
                ),
            ],
            TextField(
              controller: _note,
              maxLines: 3,
              minLines: 2,
              decoration: const InputDecoration(
                hintText: 'What happened? How did it feel?',
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: _savingNote || _note.text.trim().isEmpty ? null : _saveNote,
                    icon: const Icon(Icons.add, size: 16),
                    label: Text(_savingNote ? 'Saving…' : 'Save note'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SectionLabel('Value (optional)'),
                      TextField(
                        controller: _value,
                        keyboardType: const TextInputType.numberWithOptions(decimal: true),
                        decoration: InputDecoration(
                          hintText: 'e.g. litres, pages, minutes',
                          suffixText: widget.habit['target_unit'] as String? ?? '',
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                FilledButton(
                  onPressed: _saving ? null : _saveValue,
                  child: _saving
                      ? const SizedBox(
                          width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Save'),
                ),
              ],
            ),
            const SizedBox(height: 20),
            SectionLabel('Last 30 days', icon: Icons.calendar_month_outlined),
            _HistoryStrip(
              days: days,
              doneDates: doneDates,
              skippedDates: skippedDates,
              inProgressDates: inProgressDates,
              color: color,
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                _LegendDot(color: color, label: 'done'),
                const SizedBox(width: 10),
                _LegendDot(color: AppColors.amber, label: 'skipped', hollow: true),
                const SizedBox(width: 10),
                _LegendDot(color: Colors.white.withValues(alpha: .08), label: 'missed'),
              ],
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _statusBtn(String label, IconData icon, Color c, String value, Color habitColor) {
    final selected = _status == value || (value == 'pending' && _status.isEmpty);
    return InkWell(
      onTap: () => _setStatus(value),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: selected ? c.withValues(alpha: 0.2) : AppColors.surface2,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
              color: selected ? c : AppColors.border, width: selected ? 1.5 : 1),
        ),
        child: Column(
          children: [
            Icon(icon, color: selected ? c : AppColors.faint, size: 22),
            const SizedBox(height: 4),
            Text(label,
                style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: selected ? c : AppColors.dim)),
          ],
        ),
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  final bool hollow;
  const _LegendDot({required this.color, required this.label, this.hollow = false});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: hollow ? Colors.transparent : color,
            borderRadius: BorderRadius.circular(3),
            border: hollow ? Border.all(color: color, width: 1.5) : null,
          ),
        ),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 10.5, color: AppColors.dim)),
      ],
    );
  }
}

class _HistoryStrip extends StatelessWidget {
  final List<String> days;
  final Set<String> doneDates;
  final Set<String> skippedDates;
  final Set<String> inProgressDates;
  final Color color;
  const _HistoryStrip({
    required this.days,
    required this.doneDates,
    required this.skippedDates,
    required this.inProgressDates,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 4,
      runSpacing: 4,
      children: days.map((d) {
        final hit = doneDates.contains(d);
        final skipped = skippedDates.contains(d);
        final inProgress = inProgressDates.contains(d);
        return Tooltip(
          message: hit
              ? '$d · done'
              : skipped
                  ? '$d · skipped'
                  : inProgress
                      ? '$d · in progress'
                      : d,
          child: Container(
            width: 18,
            height: 18,
            decoration: BoxDecoration(
              color: hit
                  ? color.withValues(alpha: 0.85)
                  : inProgress
                      ? AppColors.sky.withValues(alpha: 0.45)
                      : Colors.white.withValues(alpha: 0.06),
              borderRadius: BorderRadius.circular(5),
              border: skipped
                  ? Border.all(color: AppColors.amber, width: 1.5)
                  : inProgress
                      ? Border.all(color: AppColors.sky, width: 1.5)
                      : null,
            ),
          ),
        );
      }).toList(),
    );
  }
}
