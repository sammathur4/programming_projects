import 'package:flutter/material.dart';

import '../api.dart';
import '../theme.dart';

/// Notes — one feed for every note in the system.
///
/// Category chips with live counts, a date-grouped feed, and pinned notes
/// pulled to the top. Backed by `/api/notes/`, which owns the notes that are
/// not attached to a single record (day notes, ideas, roll-ups).
class NotesScreen extends StatefulWidget {
  const NotesScreen({super.key});

  @override
  State<NotesScreen> createState() => _NotesScreenState();
}

class _NotesScreenState extends State<NotesScreen> {
  static const _tags = ['all', 'day', 'habit', 'fitness', 'food', 'goal', 'idea'];

  static const _tagMeta = <String, (String, IconData, Color)>{
    'all': ('All', Icons.auto_awesome, AppColors.text),
    'day': ('Day', Icons.today, AppColors.sky),
    'habit': ('Habit', Icons.check_circle_outline, AppColors.emerald),
    'fitness': ('Fitness', Icons.fitness_center, AppColors.blue),
    'food': ('Food', Icons.restaurant, AppColors.amber),
    'goal': ('Goal', Icons.flag, AppColors.violet),
    'idea': ('Idea', Icons.lightbulb_outline, AppColors.gold),
  };

  List<dynamic> _notes = [];
  Map<String, dynamic> _counts = {};
  String _tag = 'all';
  bool _loading = true;
  String? _error;

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
      final res = await Api.get('notes/', _tag == 'all' ? null : {'tag': _tag});
      if (!mounted) return;
      final map = res as Map<String, dynamic>;
      setState(() {
        final res = map['results'];
        _notes = res is List ? res : [];
        _counts = map['counts'] as Map<String, dynamic>;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _loading = false;
      });
    }
  }

  Future<void> _openEditor({Map<String, dynamic>? note}) async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => _NoteEditor(note: note, defaultTag: _tag == 'all' ? 'day' : _tag),
    );
    if (saved == true) await _load();
  }

  Future<void> _togglePin(Map<String, dynamic> note) async {
    try {
      await Api.send('PATCH', 'notes/${note['id']}/', {'pinned': !(note['pinned'] as bool)},
          label: 'Pin note', dedupeId: 'note-pin-${note['id']}');
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not pin: $e')));
    }
  }

  Future<void> _delete(Map<String, dynamic> note) async {
    try {
      await Api.delete('notes/${note['id']}/', null, true, 'Delete note');
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not delete: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorPane(message: _error!, onRetry: _load);

    final pinned = _notes.where((n) => (n as Map)['pinned'] == true).toList();
    final rest = _notes.where((n) => (n as Map)['pinned'] != true).toList();

    // group the unpinned notes by date, newest first
    final byDate = <String, List<dynamic>>{};
    for (final n in rest) {
      byDate.putIfAbsent((n as Map)['date'] as String, () => []).add(n);
    }
    final dates = byDate.keys.toList()..sort((a, b) => b.compareTo(a));

    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openEditor(),
        backgroundColor: AppColors.emerald,
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add, size: 20),
        label: const Text('Note', style: TextStyle(fontWeight: FontWeight.w800)),
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 90),
          children: [
            _chipRow(),
            if (pinned.isNotEmpty) ...[
              const SizedBox(height: 12),
              SectionLabel('Pinned', icon: Icons.push_pin),
              ...pinned.map((n) => _noteCard(n as Map<String, dynamic>, pinned: true)),
              const SizedBox(height: 6),
            ],
            if (dates.isNotEmpty) ...[
              const SizedBox(height: 8),
              SectionLabel(
                'Feed',
                icon: Icons.notes,
                trailing: Pill('${rest.length}', color: AppColors.sky),
              ),
              for (final date in dates) ...[
                _dateHeader(date),
                ...byDate[date]!.map((n) => _noteCard(n as Map<String, dynamic>)),
                const SizedBox(height: 6),
              ],
            ],
            if (_notes.isEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 60),
                child: EmptyState(
                  icon: Icons.notes,
                  title: 'No notes here yet',
                  subtitle: _tag == 'all'
                      ? 'Write down what happened today — wins, slips, lessons.'
                      : 'Nothing tagged "${_tagMeta[_tag]?.$1 ?? _tag}" yet.',
                  action: FilledButton.icon(
                    onPressed: () => _openEditor(),
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Write a note'),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _chipRow() {
    return SizedBox(
      height: 34,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _tags.length,
        separatorBuilder: (_, _) => const SizedBox(width: 7),
        itemBuilder: (_, i) {
          final tag = _tags[i];
          final meta = _tagMeta[tag]!;
          final selected = _tag == tag;
          final count = asInt(_counts[tag]);
          return GestureDetector(
            onTap: () {
              setState(() => _tag = tag);
              _load();
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 11),
              decoration: BoxDecoration(
                color: selected ? meta.$3.withValues(alpha: .2) : AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: selected ? meta.$3.withValues(alpha: .55) : AppColors.border,
                ),
              ),
              child: Row(
                children: [
                  Icon(meta.$2, size: 13, color: selected ? meta.$3 : AppColors.dim),
                  const SizedBox(width: 5),
                  Text(meta.$1,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: selected ? meta.$3 : AppColors.dim,
                      )),
                  const SizedBox(width: 5),
                  Text('$count',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                        color: selected ? meta.$3 : AppColors.faint,
                      )),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _dateHeader(String date) {
    return Padding(
      padding: const EdgeInsets.only(top: 10, bottom: 6),
      child: Row(
        children: [
          Text(_prettyDate(date),
              style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: AppColors.text)),
          const SizedBox(width: 8),
          Expanded(child: Container(height: 1, color: AppColors.border)),
        ],
      ),
    );
  }

  Widget _noteCard(Map<String, dynamic> note, {bool pinned = false}) {
    final tag = note['tag'] as String;
    final meta = _tagMeta[tag] ?? _tagMeta['day']!;
    return AppCard(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.fromLTRB(13, 11, 6, 11),
      borderColor: pinned ? AppColors.gold.withValues(alpha: .4) : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Pill(meta.$1, color: meta.$3, icon: meta.$2),
              if ((note['ref'] as String).isNotEmpty) ...[
                const SizedBox(width: 7),
                Expanded(
                  child: Text(note['ref'] as String,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.text)),
                ),
              ] else
                const Spacer(),
              IconButton(
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 30, minHeight: 30),
                icon: Icon(
                  pinned ? Icons.push_pin : Icons.push_pin_outlined,
                  size: 16,
                  color: pinned ? AppColors.gold : AppColors.faint,
                ),
                onPressed: () => _togglePin(note),
              ),
              IconButton(
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 30, minHeight: 30),
                icon: const Icon(Icons.delete_outline, size: 16, color: AppColors.faint),
                onPressed: () => _delete(note),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(note['text'] as String,
              style: const TextStyle(fontSize: 12.8, height: 1.5, color: AppColors.text)),
        ],
      ),
    );
  }

  /// "2026-10-20" -> "Today" / "Yesterday" / "Mon, 18 Oct"
  static String _prettyDate(String iso) {
    try {
      final d = DateTime.parse(iso);
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final that = DateTime(d.year, d.month, d.day);
      final diff = today.difference(that).inDays;
      if (diff == 0) return 'Today';
      if (diff == 1) return 'Yesterday';
      const names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
      const months = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
      ];
      return '${names[d.weekday - 1]}, ${d.day} ${months[d.month - 1]}';
    } catch (_) {
      return iso;
    }
  }
}

/// Bottom sheet for writing or editing one note.
class NoteEditor extends StatefulWidget {
  final Map<String, dynamic>? note;
  final String defaultTag;
  const NoteEditor({this.note, required this.defaultTag});

  @override
  State<NoteEditor> createState() => _NoteEditorState();
}

class _NoteEditor extends NoteEditor {
  final Map<String, dynamic>? note;
  final String defaultTag;
  _NoteEditor({this.note, required this.defaultTag}) : super(note: note, defaultTag: defaultTag);
}

class _NoteEditorState extends State<NoteEditor> {
  late final TextEditingController _text;
  late final TextEditingController _ref;
  late String _tag;
  bool _saving = false;

  static const _tags = ['day', 'habit', 'fitness', 'food', 'goal', 'idea'];

  @override
  void initState() {
    super.initState();
    _text = TextEditingController(text: (widget.note?['text'] as String?) ?? '');
    _ref = TextEditingController(text: (widget.note?['ref'] as String?) ?? '');
    _tag = (widget.note?['tag'] as String?) ?? widget.defaultTag;
  }

  @override
  void dispose() {
    _text.dispose();
    _ref.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_text.text.trim().isEmpty) return;
    setState(() => _saving = true);
    final body = {
      'date': widget.note?['date'] ??
          DateTime.now().toIso8601String().substring(0, 10),
      'tag': _tag,
      'ref': _ref.text.trim(),
      'text': _text.text.trim(),
    };
    try {
      if (widget.note == null) {
        await Api.send('POST', 'notes/', body,
            label: 'New note', dedupeId: 'note-new-${DateTime.now().microsecondsSinceEpoch}');
      } else {
        await Api.send('PATCH', 'notes/${widget.note!['id']}/', body,
            label: 'Edit note', dedupeId: 'note-edit-${widget.note!['id']}');
      }
      if (!mounted) return;
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not save: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + bottom),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(widget.note == null ? 'New note' : 'Edit note',
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800)),
          const SizedBox(height: 14),
          Wrap(
            spacing: 7,
            children: _tags.map((t) {
              final selected = _tag == t;
              return ChoiceChip(
                label: Text(t[0].toUpperCase() + t.substring(1)),
                selected: selected,
                onSelected: (_) => setState(() => _tag = t),
              );
            }).toList(),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _ref,
            style: const TextStyle(fontSize: 13),
            decoration: const InputDecoration(hintText: 'About what? (e.g. Diet, Squat)'),
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _text,
            maxLines: 5,
            autofocus: widget.note == null,
            style: const TextStyle(fontSize: 13.5),
            decoration: const InputDecoration(hintText: 'What happened? What did you learn?'),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _saving ? null : () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton(
                  onPressed: _saving ? null : _save,
                  child: Text(_saving ? 'Saving…' : 'Save'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
