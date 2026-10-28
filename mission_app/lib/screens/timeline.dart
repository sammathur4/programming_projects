import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api.dart';
import '../theme.dart';

/// Timeline — a unified, date-sorted feed of everything you've logged.
///
/// This is the phone's window into history: the web app has dedicated Habits,
/// Fitness, Food and Stats tabs, but the APK only ships Today + Fitness, so
/// this screen merges habits, workouts, weigh-ins, measurements and drinks
/// into one scrollable story.
class TimelineScreen extends StatefulWidget {
  const TimelineScreen({super.key});

  @override
  State<TimelineScreen> createState() => _TimelineScreenState();
}

class _TimelineScreenState extends State<TimelineScreen> {
  static const _kinds = <String, _KindSpec>{
    'habits': _KindSpec('Habits', Icons.check_circle_outline, AppColors.emerald),
    'fitness': _KindSpec('Fitness', Icons.fitness_center, AppColors.violet),
    'weight': _KindSpec('Weight', Icons.monitor_weight_outlined, AppColors.sky),
    'measurements': _KindSpec('Measures', Icons.straighten, AppColors.amber),
    'drinks': _KindSpec('Drinks', Icons.local_drink_outlined, AppColors.blue),
    'jaap': _KindSpec('Jaap', Icons.spa_outlined, AppColors.gold),
  };

  int _days = 30;
  final Set<String> _active = {..._kinds.keys};
  bool _loading = true;
  String? _error;
  List<dynamic> _events = [];
  Map<String, dynamic> _counts = {};

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
      final to = DateTime.now();
      final from = to.subtract(Duration(days: _days - 1));
      final r = await Api.get('journal/', {
        'from': DateFormat('yyyy-MM-dd').format(from),
        'to': DateFormat('yyyy-MM-dd').format(to),
        'types': _active.join(','),
      });
      if (!mounted) return;
      setState(() {
        _events = (r['events'] as List? ?? []);
        _counts = (r['counts'] as Map?)?.cast<String, dynamic>() ?? {};
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  void _toggle(String kind) {
    setState(() {
      if (_active.contains(kind)) {
        if (_active.length > 1) _active.remove(kind);
      } else {
        _active.add(kind);
      }
    });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Timeline'),
        actions: [
          PopupMenuButton<int>(
            tooltip: 'Range',
            initialValue: _days,
            onSelected: (d) {
              setState(() => _days = d);
              _load();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 7, child: Text('Last 7 days')),
              PopupMenuItem(value: 30, child: Text('Last 30 days')),
              PopupMenuItem(value: 90, child: Text('Last 90 days')),
              PopupMenuItem(value: 365, child: Text('Last year')),
            ],
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Row(children: [
                const Icon(Icons.date_range_outlined, size: 18),
                const SizedBox(width: 5),
                Text('${_days}d', style: const TextStyle(fontWeight: FontWeight.w700)),
              ]),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          _filterBar(),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? ErrorPane(message: _error!, onRetry: _load)
                    : _events.isEmpty
                        ? const EmptyState(
                            icon: Icons.history_toggle_off,
                            title: 'Nothing in this range',
                            subtitle: 'Log habits, workouts, weights or drinks — they all show up here.',
                          )
                        : RefreshIndicator(onRefresh: _load, child: _feed()),
          ),
        ],
      ),
    );
  }

  Widget _filterBar() {
    return SizedBox(
      height: 46,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        children: [
          for (final e in _kinds.entries)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: FilterChip(
                avatar: Icon(e.value.icon,
                    size: 15,
                    color: _active.contains(e.key) ? e.value.color : AppColors.faint),
                label: Text('${e.value.label}${_counts[e.key] != null ? ' ${_counts[e.key]}' : ''}'),
                selected: _active.contains(e.key),
                onSelected: (_) => _toggle(e.key),
              ),
            ),
        ],
      ),
    );
  }

  Widget _feed() {
    // group consecutive events by date for sticky-ish day headers
    final rows = <Widget>[];
    String? lastDate;
    for (final raw in _events) {
      final e = Map<String, dynamic>.from(raw as Map);
      final date = e['date'] as String;
      if (date != lastDate) {
        rows.add(_DayHeader(date: date));
        lastDate = date;
      }
      rows.add(_EventTile(event: e, spec: _kinds[e['kind']]));
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
      children: rows,
    );
  }
}

class _KindSpec {
  final String label;
  final IconData icon;
  final Color color;
  const _KindSpec(this.label, this.icon, this.color);
}

class _DayHeader extends StatelessWidget {
  final String date;
  const _DayHeader({required this.date});

  @override
  Widget build(BuildContext context) {
    final d = DateTime.parse(date);
    final today = DateFormat('yyyy-MM-dd').format(DateTime.now()) == date;
    final yesterday =
        DateFormat('yyyy-MM-dd').format(DateTime.now().subtract(const Duration(days: 1))) == date;
    final label = today ? 'Today' : yesterday ? 'Yesterday' : DateFormat('EEEE').format(d);
    return Padding(
      padding: const EdgeInsets.fromLTRB(2, 16, 2, 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.baseline,
        textBaseline: TextBaseline.alphabetic,
        children: [
          Text(label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900)),
          const SizedBox(width: 8),
          Text(DateFormat('dd MMM yyyy').format(d),
              style: const TextStyle(fontSize: 11, color: AppColors.faint)),
        ],
      ),
    );
  }
}

class _EventTile extends StatelessWidget {
  final Map<String, dynamic> event;
  final _KindSpec? spec;
  const _EventTile({required this.event, this.spec});

  @override
  Widget build(BuildContext context) {
    final color = spec?.color ?? AppColors.violet;
    final at = event['at'] as String?;
    final time = at == null ? null : _shortTime(at);
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
              border: Border.all(color: color.withValues(alpha: 0.35)),
            ),
            alignment: Alignment.center,
            child: Icon(spec?.icon ?? Icons.circle, size: 17, color: color),
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(event['title']?.toString() ?? '',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800)),
                if ((event['subtitle']?.toString() ?? '').isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(event['subtitle'].toString(),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                ],
              ],
            ),
          ),
          if (time != null) ...[
            const SizedBox(width: 8),
            Text(time, style: const TextStyle(fontSize: 11, color: AppColors.faint)),
          ],
        ],
      ),
    );
  }

  static String _shortTime(String iso) {
    final t = DateTime.tryParse(iso);
    if (t == null) return '';
    final h = t.hour % 12 == 0 ? 12 : t.hour % 12;
    final ampm = t.hour < 12 ? 'am' : 'pm';
    return '$h:${t.minute.toString().padLeft(2, '0')}$ampm';
  }
}
