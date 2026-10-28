import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import '../responsive.dart';
import '../theme.dart';

class StudyScreen extends StatefulWidget {
  const StudyScreen({super.key});

  @override
  State<StudyScreen> createState() => _StudyScreenState();
}

class _StudyScreenState extends State<StudyScreen> with SingleTickerProviderStateMixin {
  late final TabController _tab;
  List<dynamic> _pending = [];
  List<dynamic> _inProgress = [];
  List<dynamic> _completed = [];
  List<dynamic> _activity = [];
  Map<String, dynamic>? _analytics;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tab = TabController(length: 3, vsync: this);
    _load();
  }

  @override
  void dispose() {
    _tab.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        Api.get('resources/', {'track': 'pending'}),
        Api.get('resources/', {'track': 'in_progress'}),
        Api.get('resources/', {'track': 'completed'}),
        Api.get('study/analytics/', {'days': '60'}),
        Api.get('study/activity/', {'limit': '50'}),
      ]);
      setState(() {
        _pending = results[0] is List ? results[0] as List : [];
        _inProgress = results[1] is List ? results[1] as List : [];
        _completed = results[2] is List ? results[2] as List : [];
        _analytics = results[3] as Map<String, dynamic>;
        _activity = results[4] is List ? results[4] as List : [];
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _logActivity([Map<String, dynamic>? existing]) async {
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => StudyActivityDialog(
        activity: existing,
        resources: [..._pending, ..._inProgress, ..._completed]
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList(),
      ),
    );
    if (saved == true) await _load();
  }

  Future<void> _deleteActivity(Map<String, dynamic> a) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Delete activity?'),
        content: Text('Remove this ${a['activity_type']} record from '
            '${a['date']}? Totals will be recalculated.'),
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
    try {
      await Api.delete('study/activity/${a['id']}/', null, true, 'Delete study activity');
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  Future<void> _move(Map<String, dynamic> item, String track) async {
    try {
      await Api.send('POST', 'resources/${item['id']}/move/', {'track': track},
          label: 'Move resource → $track', dedupeId: 'resource-move-${item['id']}');
      await _load();
      if (!mounted) return;
      final label = track == 'in_progress'
          ? 'In Progress'
          : track == 'completed'
              ? 'Completed'
              : 'Pending';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Moved to $label'), duration: const Duration(seconds: 2)),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  /// Persist how many videos of a resource have been watched so far.
  Future<void> _updateVideosDone(Map<String, dynamic> item, int done) async {
    final total = asInt(item['videos'], -1);
    if (done < 0 || (total >= 0 && done > total)) return;
    try {
      await Api.send('PATCH', 'resources/${item['id']}/', {'videos_done': done},
          label: 'Videos watched · $done', dedupeId: 'resource-videos-${item['id']}');
      await _load();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        if (_analytics != null) _AnalyticsStrip(a: _analytics!),
        Container(
          padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: AppColors.border)),
          ),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  '${_activity.length} activity record${_activity.length == 1 ? '' : 's'} · '
                  'MCQ ${_analytics?['total_mcq'] ?? 0} · AW ${_analytics?['total_aw'] ?? 0}',
                  style: const TextStyle(fontSize: 11.5, color: AppColors.dim),
                ),
              ),
              SmBtn('＋ Log Study Activity', primary: true, onTap: () => _logActivity()),
            ],
          ),
        ),
        Material(
          color: AppColors.bg,
          child: TabBar(
            controller: _tab,
            isScrollable: false,
            tabs: [
              Tab(text: 'Pending ${_pending.length}'),
              Tab(text: 'In Progress ${_inProgress.length}'),
              Tab(text: 'Done ${_completed.length}'),
            ],
          ),
        ),
        Expanded(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? ErrorPane(message: _error!, onRetry: _load)
                  : TabBarView(
                      controller: _tab,
                      children: [
                        _ResourceList(items: _pending, onMove: _move, onReload: _load),
                        _ResourceList(
                          items: _inProgress,
                          onMove: _move,
                          onReload: _load,
                          onUpdateVideos: _updateVideosDone,
                        ),
                        _ResourceList(items: _completed, onMove: _move, onReload: _load),
                      ],
                    ),
        ),
        if (!_loading && _error == null)
          _ActivityPanel(
            items: _activity,
            onEdit: _logActivity,
            onDelete: _deleteActivity,
          ),
      ],
    );
  }
}

class _AnalyticsStrip extends StatelessWidget {
  final Map<String, dynamic> a;
  const _AnalyticsStrip({required this.a});

  @override
  Widget build(BuildContext context) {
    final hours = asDouble(a['total_hours']);
    final aw = a['total_aw'] ?? 0;
    final mcq = a['total_mcq'] ?? 0;
    final adherence = a['target_adherence_pct'];
    final res = a['resources'] as Map<String, dynamic>? ?? {};
    final inProg = res['in_progress'] as Map<String, dynamic>? ?? {};
    final act = a['activity'] as Map<String, dynamic>? ?? {};
    final accuracy = act['accuracy'];

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            SizedBox(width: 130, child: StatBlock(hours.toStringAsFixed(1), 'hours / 60d', color: AppColors.sky, icon: Icons.schedule)),
            SizedBox(width: 130, child: StatBlock('$aw', 'answer writings', color: AppColors.violet, icon: Icons.edit_note)),
            SizedBox(width: 130, child: StatBlock('$mcq', 'MCQs done', color: AppColors.emerald, icon: Icons.quiz_outlined)),
            SizedBox(width: 130, child: StatBlock('${act['attempted'] ?? 0}', 'attempted', color: AppColors.sky, icon: Icons.list_alt)),
            SizedBox(
              width: 130,
              child: StatBlock(
                accuracy == null ? '—' : '$accuracy%',
                'accuracy',
                color: accuracy == null ? AppColors.faint : AppColors.greenText,
                icon: Icons.percent,
              ),
            ),
            SizedBox(
              width: 130,
              child: StatBlock(
                adherence == null ? '—' : '$adherence%',
                'target hit',
                color: adherence == null ? AppColors.faint : AppColors.amber,
                icon: Icons.flag_outlined,
              ),
            ),
            SizedBox(
              width: 130,
              child: StatBlock(
                '${inProg['items'] ?? 0}',
                'in progress',
                color: AppColors.orange,
                icon: Icons.hourglass_bottom,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResourceList extends StatelessWidget {
  final List<dynamic> items;
  final Future<void> Function(Map<String, dynamic>, String) onMove;
  final Future<void> Function() onReload;
  final Future<void> Function(Map<String, dynamic>, int)? onUpdateVideos;

  const _ResourceList({
    required this.items,
    required this.onMove,
    required this.onReload,
    this.onUpdateVideos,
  });

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const EmptyState(
        icon: Icons.menu_book_outlined,
        title: 'Nothing here yet',
        subtitle: 'Items you move will show up in this column.',
      );
    }
    return RefreshIndicator(
      onRefresh: onReload,
      child: ListView.builder(
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
        itemCount: items.length,
        itemBuilder: (context, i) => _ResourceTile(
          item: Map<String, dynamic>.from(items[i] as Map),
          onMove: onMove,
          onUpdateVideos: onUpdateVideos,
        ),
      ),
    );
  }
}

class _ResourceTile extends StatelessWidget {
  final Map<String, dynamic> item;
  final Future<void> Function(Map<String, dynamic>, String) onMove;
  final Future<void> Function(Map<String, dynamic>, int)? onUpdateVideos;
  const _ResourceTile({required this.item, required this.onMove, this.onUpdateVideos});

  Future<void> _open() async {
    final url = (item['playlist_url'] as String? ?? '').trim();
    if (url.isEmpty || url.toLowerCase() == 'telegram') return;
    final uri = Uri.tryParse(url.startsWith('http') ? url : 'https://$url');
    if (uri != null) await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  @override
  Widget build(BuildContext context) {
    final url = (item['playlist_url'] as String? ?? '').trim();
    final hasLink = url.isNotEmpty && url.toLowerCase() != 'telegram';
    final prio = (item['priority'] as String? ?? '').trim();
    final track = (item['track'] as String? ?? 'pending');
    final prioColor = prio == 'P1'
        ? AppColors.rose
        : prio == 'P2'
            ? AppColors.amber
            : AppColors.faint;
    final pct = asInt(item['progress_pct']);

    return AppCard(
      margin: const EdgeInsets.only(bottom: 9),
      onTap: hasLink ? _open : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (prio.isNotEmpty) ...[
                Pill(prio, color: prioColor),
                const SizedBox(width: 8),
              ],
              Expanded(
                child: Text(
                  '${item['subject'] ?? ''}${(item['exam'] as String? ?? '').isNotEmpty ? ' · ${item['exam']}' : ''}',
                  style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5),
                ),
              ),
              if (hasLink)
                const Icon(Icons.play_circle_outline, size: 19, color: AppColors.sky),
            ],
          ),
          if ((item['playlist_name'] as String? ?? '').isNotEmpty) ...[
            const SizedBox(height: 5),
            Text(item['playlist_name'],
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12, color: AppColors.dim, height: 1.3)),
          ],
          const SizedBox(height: 8),
          Row(
            children: [
              if (item['videos'] != null) ...[
                Pill('${item['videos']} videos', color: AppColors.faint),
                const SizedBox(width: 6),
              ],
              if ((item['duration_hms'] as String? ?? '').isNotEmpty) ...[
                Pill(item['duration_hms'], color: AppColors.faint),
                const SizedBox(width: 6),
              ],
              if ((item['paper'] as String? ?? '').isNotEmpty)
                Flexible(
                  child: Text(item['paper'],
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 11, color: AppColors.faint)),
                ),
            ],
          ),
          if (track == 'in_progress' && item['videos'] != null) ...[
            const SizedBox(height: 9),
            _VideosWatched(
              done: asInt(item['videos_done']),
              total: asInt(item['videos']),
              pct: pct,
              onChanged: onUpdateVideos == null
                  ? null
                  : (v) => onUpdateVideos!(item, v),
            ),
          ] else if (item['videos'] != null) ...[
            const SizedBox(height: 9),
            ProgressBar(value: pct / 100, color: AppColors.emerald, height: 5),
            const SizedBox(height: 4),
            Text('$pct% complete',
                style: const TextStyle(fontSize: 10.5, color: AppColors.faint)),
          ],
          const SizedBox(height: 10),
          Row(
            children: [
              if (track != 'pending')
                _moveBtn('To Pending', Icons.undo, AppColors.faint,
                    () => onMove(item, 'pending')),
              if (track != 'in_progress')
                _moveBtn('Start', Icons.play_arrow, AppColors.orange,
                    () => onMove(item, 'in_progress')),
              if (track != 'completed')
                _moveBtn('Complete', Icons.check, AppColors.emerald,
                    () => onMove(item, 'completed')),
            ],
          ),
        ],
      ),
    );
  }

  Widget _moveBtn(String label, IconData icon, Color color, VoidCallback onTap) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: OutlinedButton.icon(
        style: OutlinedButton.styleFrom(
          visualDensity: VisualDensity.compact,
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
          minimumSize: const Size(0, 30),
          foregroundColor: color,
          side: BorderSide(color: color.withValues(alpha: 0.4)),
        ),
        onPressed: onTap,
        icon: Icon(icon, size: 14),
        label: Text(label, style: const TextStyle(fontSize: 11)),
      ),
    );
  }
}

/// Interactive "videos watched" tracker for an in-progress resource.
///
/// Shows a progress bar plus -/+ steppers and an inline "set" field so the
/// count can be corrected in one tap without opening the full edit dialog.
class _VideosWatched extends StatefulWidget {
  final int done;
  final int total;
  final int pct;
  final Future<void> Function(int)? onChanged;
  const _VideosWatched({
    required this.done,
    required this.total,
    required this.pct,
    this.onChanged,
  });

  @override
  State<_VideosWatched> createState() => _VideosWatchedState();
}

class _VideosWatchedState extends State<_VideosWatched> {
  bool _busy = false;
  final _ctrl = TextEditingController();
  bool _editing = false;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  Future<void> _apply(int value) async {
    if (widget.onChanged == null || _busy) return;
    final v = value.clamp(0, widget.total);
    if (v == widget.done) {
      setState(() => _editing = false);
      return;
    }
    setState(() => _busy = true);
    await widget.onChanged!(v);
    if (mounted) {
      setState(() {
        _busy = false;
        _editing = false;
      });
    }
  }

  void _startEditing() {
    _ctrl.text = widget.done.toString();
    setState(() => _editing = true);
  }

  @override
  Widget build(BuildContext context) {
    final pctColor = widget.pct >= 100
        ? AppColors.greenText
        : widget.pct >= 50
            ? AppColors.orange
            : AppColors.sky;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ProgressBar(value: widget.pct / 100, color: pctColor, height: 6),
        const SizedBox(height: 6),
        Row(
          children: [
            if (widget.pct >= 100)
              const Icon(Icons.check_circle, size: 14, color: AppColors.greenText)
            else
              const Icon(Icons.smart_display_outlined, size: 14, color: AppColors.faint),
            const SizedBox(width: 5),
            Expanded(
              child: _editing
                  ? SizedBox(
                      height: 28,
                      width: 70,
                      child: TextField(
                        controller: _ctrl,
                        autofocus: true,
                        keyboardType: TextInputType.number,
                        style: const TextStyle(fontSize: 12),
                        decoration: InputDecoration(
                          isDense: true,
                          contentPadding:
                              const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                          suffixText: '/ ${widget.total}',
                          suffixStyle:
                              const TextStyle(fontSize: 10, color: AppColors.faint),
                        ),
                        onSubmitted: (t) => _apply(int.tryParse(t.trim()) ?? widget.done),
                      ),
                    )
                  : GestureDetector(
                      onTap: widget.onChanged == null ? null : _startEditing,
                      child: Text(
                        '${widget.done} / ${widget.total} videos · ${widget.pct}%',
                        style: TextStyle(
                          fontSize: 11,
                          color: widget.pct >= 100 ? AppColors.greenText : AppColors.dim,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
            ),
            if (_editing) ...[
              _iconBtn(Icons.close, AppColors.faint,
                  () => setState(() => _editing = false)),
              _iconBtn(Icons.check, AppColors.greenText, () {
                final v = int.tryParse(_ctrl.text.trim());
                if (v != null) _apply(v);
              }),
            ] else if (widget.onChanged != null) ...[
              if (_busy)
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              else ...[
                _iconBtn(Icons.remove, AppColors.dim,
                    widget.done > 0 ? () => _apply(widget.done - 1) : null),
                _iconBtn(Icons.add, AppColors.orange,
                    widget.done < widget.total ? () => _apply(widget.done + 1) : null),
                _iconBtn(Icons.edit_outlined, AppColors.violet, _startEditing),
              ],
            ],
          ],
        ),
      ],
    );
  }

  Widget _iconBtn(IconData icon, Color color, VoidCallback? onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
        child: Icon(icon,
            size: 17, color: onTap == null ? AppColors.faint.withValues(alpha: 0.4) : color),
      ),
    );
  }
}

// ------------------------------------------------------------------ activity

const _activityTypes = <String, String>{
  'study_session': 'Study session',
  'mcq': 'MCQs',
  'answer_writing': 'Answer writing',
  'revision': 'Revision',
  'mock_test': 'Mock test',
};

String _activityLabel(String type) => _activityTypes[type] ?? type;

class _ActivityPanel extends StatelessWidget {
  final List<dynamic> items;
  final Future<void> Function([Map<String, dynamic>?]) onEdit;
  final Future<void> Function(Map<String, dynamic>) onDelete;
  const _ActivityPanel({required this.items, required this.onEdit, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Container(
      height: 150,
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: AppColors.border)),
        color: AppColors.surface,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: Text('Recent activity',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
          ),
          Expanded(
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              itemCount: items.length,
              itemBuilder: (context, i) {
                final a = Map<String, dynamic>.from(items[i] as Map);
                final bits = <String>[];
                if (asInt(a['time_spent_minutes']) > 0) bits.add('${asInt(a['time_spent_minutes'])} min');
                if (asInt(a['questions_attempted']) > 0) bits.add('att ${asInt(a['questions_attempted'])}');
                if (asInt(a['questions_completed']) > 0) bits.add('done ${asInt(a['questions_completed'])}');
                if (asInt(a['answers_written']) > 0) bits.add('AW ${asInt(a['answers_written'])}');
                final acc = (asInt(a['correct_answers']) + asInt(a['incorrect_answers'])) > 0
                    ? 'acc ${(asInt(a['correct_answers']) / (asInt(a['correct_answers']) + asInt(a['incorrect_answers'])) * 100).round()}%'
                    : null;
                if (acc != null) bits.add(acc);
                return Container(
                  width: 220,
                  margin: const EdgeInsets.only(right: 10, bottom: 10),
                  padding: const EdgeInsets.all(10),
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
                          Expanded(
                            child: Text(_activityLabel(a['activity_type'] as String? ?? ''),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                          ),
                          InkWell(
                            onTap: () => onEdit(a),
                            child: const Icon(Icons.edit, size: 15, color: AppColors.violet),
                          ),
                          const SizedBox(width: 6),
                          InkWell(
                            onTap: () => onDelete(a),
                            child: const Icon(Icons.delete_outline, size: 15, color: AppColors.rose),
                          ),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(a['date']?.toString() ?? '',
                          style: const TextStyle(fontSize: 10.5, color: AppColors.faint)),
                      const SizedBox(height: 6),
                      Text(bits.isEmpty ? 'no counts' : bits.join(' · '),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 11, color: AppColors.dim, height: 1.3)),
                      if ((a['subject'] as String? ?? '').isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 3),
                          child: Text(a['subject'],
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 10.5, color: AppColors.faint)),
                        ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class StudyActivityDialog extends StatefulWidget {
  final Map<String, dynamic>? activity;
  final List<Map<String, dynamic>> resources;
  const StudyActivityDialog({super.key, this.activity, required this.resources});

  @override
  State<StudyActivityDialog> createState() => _StudyActivityDialogState();
}

class _StudyActivityDialogState extends State<StudyActivityDialog> {
  late String _type;
  late TextEditingController _date;
  late TextEditingController _subject;
  late TextEditingController _minutes;
  late TextEditingController _attempted;
  late TextEditingController _completed;
  late TextEditingController _correct;
  late TextEditingController _incorrect;
  late TextEditingController _answers;
  late TextEditingController _words;
  late TextEditingController _notes;
  int? _resourceId;
  bool _saving = false;
  String? _validation;

  @override
  void initState() {
    super.initState();
    final a = widget.activity ?? <String, dynamic>{};
    _type = (a['activity_type'] as String?) ?? 'study_session';
    _date = TextEditingController(
      text: (a['date'] as String?) ?? DateTime.now().toIso8601String().substring(0, 10));
    _subject = TextEditingController(text: (a['subject'] as String?) ?? '');
    _minutes = TextEditingController(text: _s(a['time_spent_minutes']));
    _attempted = TextEditingController(text: _s(a['questions_attempted']));
    _completed = TextEditingController(text: _s(a['questions_completed']));
    _correct = TextEditingController(text: _s(a['correct_answers']));
    _incorrect = TextEditingController(text: _s(a['incorrect_answers']));
    _answers = TextEditingController(text: _s(a['answers_written']));
    _words = TextEditingController(text: _s(a['word_count']));
    _notes = TextEditingController(text: (a['notes'] as String?) ?? '');
    _resourceId = a['resource'] as int?;
  }

  static String _s(dynamic v) => v == null ? '' : v.toString();

  @override
  void dispose() {
    for (final c in [_date, _subject, _minutes, _attempted, _completed, _correct,
      _incorrect, _answers, _words, _notes]) {
      c.dispose();
    }
    super.dispose();
  }

  int? _int(TextEditingController c) {
    final t = c.text.trim();
    if (t.isEmpty) return null;
    return int.tryParse(t);
  }

  bool get _isMcq => _type == 'mcq' || _type == 'mock_test';
  bool get _isAnswer => _type == 'answer_writing';

  String? _validate() {
    for (final c in [_attempted, _completed, _correct, _incorrect, _answers, _words, _minutes]) {
      final t = c.text.trim();
      if (t.isEmpty) continue;
      final v = int.tryParse(t);
      if (v == null || v < 0) return 'Counts must be non-negative whole numbers.';
    }
    final att = _int(_attempted);
    final comp = _int(_completed);
    final cor = _int(_correct) ?? 0;
    final inc = _int(_incorrect) ?? 0;
    if (att != null && comp != null && comp > att) {
      return 'Completed cannot exceed attempted.';
    }
    if (att != null && cor + inc > att) {
      return 'Correct + incorrect cannot exceed attempted.';
    }
    return null;
  }

  Future<void> _save() async {
    final err = _validate();
    if (err != null) {
      setState(() => _validation = err);
      return;
    }
    setState(() {
      _saving = true;
      _validation = null;
    });
    final body = <String, dynamic>{
      'date': _date.text.trim(),
      'activity_type': _type,
      'subject': _subject.text.trim(),
      'resource': _resourceId,
      'time_spent_minutes': _int(_minutes),
      'questions_attempted': _int(_attempted),
      'questions_completed': _int(_completed),
      'correct_answers': _int(_correct),
      'incorrect_answers': _int(_incorrect),
      'answers_written': _int(_answers),
      'word_count': _int(_words),
      'notes': _notes.text.trim(),
    };
    try {
      if (widget.activity == null) {
        await Api.send('POST', 'study/activity/', body,
            label: 'New study activity',
            dedupeId: 'study-act-${DateTime.now().microsecondsSinceEpoch}');
      } else {
        await Api.send('PATCH', 'study/activity/${widget.activity!['id']}/', body,
            label: 'Edit study activity',
            dedupeId: 'study-act-edit-${widget.activity!['id']}');
      }
      if (!mounted) return;
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _validation = 'Could not save: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: Text(widget.activity == null ? 'Log study activity' : 'Edit activity'),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          padding: EdgeInsets.only(bottom: bottom),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 7,
                runSpacing: 7,
                children: _activityTypes.entries.map((e) {
                  return ChoiceChip(
                    label: Text(e.value, style: const TextStyle(fontSize: 12)),
                    selected: _type == e.key,
                    onSelected: (_) => setState(() => _type = e.key),
                  );
                }).toList(),
              ),
              const SizedBox(height: 12),
              _field('Date', _date),
              _field('Subject / paper', _subject),
              if (widget.resources.isNotEmpty) ...[
                const SizedBox(height: 6),
                DropdownButtonFormField<int?>(
                  initialValue: _resourceId,
                  decoration: const InputDecoration(labelText: 'Linked resource (optional)'),
                  items: [
                    const DropdownMenuItem<int?>(value: null, child: Text('— none —')),
                    ...widget.resources.map((r) => DropdownMenuItem<int?>(
                          value: r['id'] as int,
                          child: Text(
                            '${r['subject'] ?? ''} · ${r['playlist_name'] ?? ''}',
                            overflow: TextOverflow.ellipsis,
                          ),
                        )),
                  ],
                  onChanged: (v) => setState(() => _resourceId = v),
                ),
              ],
              _field('Time spent (minutes)', _minutes),
              if (_isMcq) ...[
                _field('Questions attempted', _attempted),
                _field('Questions completed', _completed),
                _field('Correct answers', _correct),
                _field('Incorrect answers', _incorrect),
              ],
              if (_isAnswer) ...[
                _field('Answers written', _answers),
                _field('Word count (optional)', _words),
              ],
              _field('Notes', _notes, lines: 2),
              if (_validation != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(_validation!,
                      style: const TextStyle(color: AppColors.rose, fontSize: 12)),
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
              : Text(widget.activity == null ? 'Save' : 'Update'),
        ),
      ],
    );
  }

  Widget _field(String label, TextEditingController c, {int lines = 1}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: TextField(
        controller: c,
        maxLines: lines,
        keyboardType: lines == 1 ? TextInputType.text : null,
        decoration: InputDecoration(labelText: label),
      ),
    );
  }
}

// ------------------------------------------------------------------ resource

/// Create / edit a study resource (playlist, book, paper…).
class StudyResourceDialog extends StatefulWidget {
  final Map<String, dynamic>? resource;
  const StudyResourceDialog({super.key, this.resource});

  @override
  State<StudyResourceDialog> createState() => _StudyResourceDialogState();
}

class _StudyResourceDialogState extends State<StudyResourceDialog> {
  final _subject = TextEditingController();
  final _exam = TextEditingController();
  final _paper = TextEditingController();
  final _playlist = TextEditingController();
  final _url = TextEditingController();
  final _videos = TextEditingController();
  final _videosDone = TextEditingController();
  final _start = TextEditingController();
  final _end = TextEditingController();
  final _notes = TextEditingController();
  String _track = 'pending';
  String _priority = '';
  String _status = 'Pending';
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final r = widget.resource ?? <String, dynamic>{};
    _subject.text = (r['subject'] as String?) ?? '';
    _exam.text = (r['exam'] as String?) ?? '';
    _paper.text = (r['paper'] as String?) ?? '';
    _playlist.text = (r['playlist_name'] as String?) ?? '';
    _url.text = (r['playlist_url'] as String?) ?? '';
    _videos.text = r['videos'] == null ? '' : r['videos'].toString();
    _videosDone.text = r['videos_done'] == null ? '' : r['videos_done'].toString();
    _start.text = (r['start_date'] as String?) ?? '';
    _end.text = (r['end_date'] as String?) ?? '';
    _notes.text = (r['notes'] as String?) ?? '';
    _track = (r['track'] as String?) ?? 'pending';
    _priority = (r['priority'] as String?) ?? '';
    _status = (r['status'] as String?) ?? 'Pending';
  }

  @override
  void dispose() {
    for (final c in [_subject, _exam, _paper, _playlist, _url, _videos,
      _videosDone, _start, _end, _notes]) {
      c.dispose();
    }
    super.dispose();
  }

  int? _int(TextEditingController c) {
    final t = c.text.trim();
    if (t.isEmpty) return null;
    return int.tryParse(t);
  }

  Future<void> _save() async {
    if (_subject.text.trim().isEmpty) {
      setState(() => _error = 'Subject is required.');
      return;
    }
    final v = _int(_videos);
    final vd = _int(_videosDone);
    if (vd != null && v != null && vd > v) {
      setState(() => _error = 'Videos done cannot exceed total videos.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    final body = <String, dynamic>{
      'subject': _subject.text.trim(),
      'exam': _exam.text.trim(),
      'paper': _paper.text.trim(),
      'playlist_name': _playlist.text.trim(),
      'playlist_url': _url.text.trim(),
      'videos': v,
      'videos_done': vd ?? 0,
      'start_date': _start.text.trim(),
      'end_date': _end.text.trim(),
      'notes': _notes.text.trim(),
      'track': _track,
      'priority': _priority,
      'status': _status,
    };
    try {
      if (widget.resource == null) {
        await Api.send('POST', 'resources/', body,
            label: 'New resource',
            dedupeId: 'resource-new-${DateTime.now().microsecondsSinceEpoch}');
      } else {
        await Api.send('PATCH', 'resources/${widget.resource!['id']}/', body,
            label: 'Edit resource',
            dedupeId: 'resource-edit-${widget.resource!['id']}');
      }
      if (!mounted) return;
      Navigator.pop(context, true);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = 'Could not save: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: Text(widget.resource == null ? 'Add study resource' : 'Edit resource'),
      content: SizedBox(
        width: 440,
        child: SingleChildScrollView(
          padding: EdgeInsets.only(bottom: bottom),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _field('Subject', _subject),
              Row(children: [
                Expanded(child: _field('Exam', _exam)),
                const SizedBox(width: 10),
                Expanded(child: _field('Paper', _paper)),
              ]),
              _field('Playlist / book name', _playlist),
              _field('Link (optional)', _url),
              Row(children: [
                Expanded(child: _field('Videos', _videos)),
                const SizedBox(width: 10),
                Expanded(child: _field('Videos done', _videosDone)),
              ]),
              Row(children: [
                Expanded(child: _field('Start date', _start)),
                const SizedBox(width: 10),
                Expanded(child: _field('End date', _end)),
              ]),
              const SizedBox(height: 4),
              DropdownButtonFormField<String>(
                initialValue: _track,
                decoration: const InputDecoration(labelText: 'Status'),
                items: const [
                  DropdownMenuItem(value: 'pending', child: Text('Pending')),
                  DropdownMenuItem(value: 'in_progress', child: Text('In Progress')),
                  DropdownMenuItem(value: 'completed', child: Text('Done')),
                ],
                onChanged: (v) => setState(() {
                  _track = v ?? 'pending';
                  _status = switch (_track) {
                    'completed' => 'Completed',
                    'in_progress' => 'In-Progress',
                    _ => 'Pending',
                  };
                }),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                initialValue: _priority,
                decoration: const InputDecoration(labelText: 'Priority (optional)'),
                items: const [
                  DropdownMenuItem(value: '', child: Text('—')),
                  DropdownMenuItem(value: 'P1', child: Text('P1')),
                  DropdownMenuItem(value: 'P2', child: Text('P2')),
                  DropdownMenuItem(value: 'P3', child: Text('P3')),
                ],
                onChanged: (v) => setState(() => _priority = v ?? ''),
              ),
              const SizedBox(height: 8),
              _field('Notes', _notes, lines: 2),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(_error!,
                      style: const TextStyle(color: AppColors.rose, fontSize: 12)),
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
              : Text(widget.resource == null ? 'Add' : 'Save'),
        ),
      ],
    );
  }

  Widget _field(String label, TextEditingController c, {int lines = 1}) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: TextField(
          controller: c,
          maxLines: lines,
          decoration: InputDecoration(labelText: label),
        ),
      );
}
