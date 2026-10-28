import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../responsive.dart';
import '../state.dart';
import '../theme.dart';

/// Stats — an analytics dashboard driven by `/habit-analytics/`.
///
///   * a shared date-range selector (7 / 14 / 30 / 90 days)
///   * summary metric cards with previous-period comparison
///   * performance-over-time bar chart
///   * a sortable habit-by-habit table
///   * a consistency calendar with a legend
///   * concise, data-backed insights
///
/// Every number is derived from stored habit logs — nothing is fabricated.
class StatsScreen extends StatefulWidget {
  const StatsScreen({super.key});

  @override
  State<StatsScreen> createState() => _StatsScreenState();
}

class _StatsScreenState extends State<StatsScreen> {
  int _range = 30;
  String _sort = 'completion';
  Map<String, dynamic>? _data;
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
      final r = await Api.get('habit-analytics/', {'days': '$_range'});
      if (!mounted) return;
      setState(() {
        _data = r is Map ? Map<String, dynamic>.from(r) : null;
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

  void _setRange(int r) {
    setState(() => _range = r);
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return RefreshIndicator(
      onRefresh: () async {
        await _load();
        await state.loadStats();
      },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 40),
        children: [
          _RangeBar(range: _range, onChanged: _setRange, loading: _loading),
          const SizedBox(height: 14),
          if (_loading && _data == null)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 60),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_error != null)
            ErrorPane(message: _error!, onRetry: _load)
          else if (_data == null)
            const EmptyState(
              icon: Icons.insights_outlined,
              title: 'No analytics yet',
              subtitle: 'Log a few habits and your dashboard will fill in.',
            )
          else ...[
            _Summary(data: _data!, range: _range),
            const SizedBox(height: 14),
            _Performance(data: _data!),
            const SizedBox(height: 12),
            _HabitTable(
              habits: List<Map<String, dynamic>>.from(
                (_data!['habits'] as List? ?? [])
                    .map((h) => Map<String, dynamic>.from(h as Map)),
              ),
              sort: _sort,
              onSort: (s) => setState(() => _sort = s),
            ),
            const SizedBox(height: 12),
            _Consistency(data: _data!),
            if ((_data!['insights'] as List? ?? []).isNotEmpty) ...[
              const SizedBox(height: 12),
              _Insights(insights: List<dynamic>.from(_data!['insights'] as List)),
            ],
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------- range bar

class _RangeBar extends StatelessWidget {
  final int range;
  final void Function(int) onChanged;
  final bool loading;
  const _RangeBar({required this.range, required this.onChanged, required this.loading});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Text('Range',
            style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800)),
        const SizedBox(width: 10),
        for (final d in const [7, 14, 30, 90]) ...[
          ChoiceChip(
            label: Text('${d}d', style: const TextStyle(fontSize: 12)),
            selected: range == d,
            onSelected: (_) => onChanged(d),
          ),
          const SizedBox(width: 6),
        ],
        const Spacer(),
        if (loading)
          const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)),
      ],
    );
  }
}

// ---------------------------------------------------------------- summary

class _Summary extends StatelessWidget {
  final Map<String, dynamic> data;
  final int range;
  const _Summary({required this.data, required this.range});

  @override
  Widget build(BuildContext context) {
    final s = data['summary'] as Map<String, dynamic>? ?? {};
    final prev7 = asInt(s['previous_7']);
    final last7 = asInt(s['last_7']);
    final delta = last7 - prev7;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Summary',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800)),
        const SizedBox(height: 10),
        LayoutBuilder(
          builder: (context, c) {
            final cols = c.maxWidth >= 900 ? 4 : (c.maxWidth >= 560 ? 3 : 2);
            final cards = <Widget>[
              _Metric('Overall (${range}d)', '${asInt(s['overall'])}%',
                  sub: '${asInt(s['habit_count'])} habits tracked'),
              _Metric('Last 7 days', '$last7%',
                  sub: delta == 0 ? 'no change' : '${delta > 0 ? '+' : ''}$delta vs prev',
                  color: delta >= 0 ? AppColors.greenText : AppColors.rose),
              _Metric('Last 30 days', '${asInt(s['last_30'])}%', sub: 'rolling 30'),
              _Metric('Best streak', '🔥 ${asInt(s['best_streak'])}', sub: 'in range'),
              _Metric('Done today', '${asInt(s['done_today'])}', sub: 'completed',
                  color: AppColors.greenText),
              _Metric('Pending today', '${asInt(s['pending_today'])}', sub: 'still actionable',
                  color: AppColors.amber),
              _Metric('Skipped today', '${asInt(s['skipped_today'])}', sub: 'explicit skips',
                  color: AppColors.faint),
            ];
            return Wrap(
              spacing: 10,
              runSpacing: 10,
              children: cards
                  .map((w) => SizedBox(width: (c.maxWidth - (cols - 1) * 10) / cols, child: w))
                  .toList(),
            );
          },
        ),
      ],
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String big;
  final String sub;
  final Color? color;
  const _Metric(this.label, this.big, {required this.sub, this.color});

  @override
  Widget build(BuildContext context) {
    return MockCard(
      padding: const EdgeInsets.fromLTRB(12, 13, 12, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Cap(label),
          const SizedBox(height: 6),
          Text(big,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, height: 1, color: color)),
          const SizedBox(height: 5),
          Text(sub,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------- performance

class _Performance extends StatelessWidget {
  final Map<String, dynamic> data;
  const _Performance({required this.data});

  @override
  Widget build(BuildContext context) {
    final series = List<Map<String, dynamic>>.from(
      (data['series'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)),
    );
    if (series.isEmpty) return const SizedBox.shrink();
    return MockCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('Performance over time',
                  style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800)),
              const SizedBox(width: 6),
              Text('${data['from']} → ${data['to']}',
                  style: const TextStyle(fontSize: 11, color: AppColors.dim)),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            height: 140,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (final p in series)
                  Expanded(
                    child: Tooltip(
                      message: '${p['date']} (${p['weekday']})\n'
                          '${p['done']}/${p['scheduled']} done'
                          '${p['rate'] == null ? ' · nothing scheduled' : ' · ${p['rate']}%'}',
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 1),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            Text(
                              p['rate'] == null ? '–' : '${p['rate']}',
                              style: const TextStyle(fontSize: 8.5, color: AppColors.dim),
                            ),
                            const SizedBox(height: 3),
                            Container(
                              height: p['rate'] == null
                                  ? 2
                                  : (asDouble(p['rate']) / 100 * 86).clamp(4.0, 86.0),
                              decoration: BoxDecoration(
                                color: p['rate'] == null
                                    ? AppColors.track
                                    : asInt(p['rate']) == 0
                                        ? AppColors.surface3
                                        : AppColors.emerald,
                                borderRadius: BorderRadius.circular(3),
                              ),
                            ),
                            const SizedBox(height: 5),
                            Text(
                              _short(p['date']?.toString() ?? ''),
                              style: const TextStyle(fontSize: 8, color: AppColors.faint),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Days with nothing scheduled show a thin marker instead of a 0% bar.',
            style: TextStyle(fontSize: 10.5, color: AppColors.faint),
          ),
        ],
      ),
    );
  }

  static String _short(String iso) {
    final d = DateTime.tryParse(iso);
    if (d == null) return '';
    return '${d.day}';
  }
}

// ---------------------------------------------------------------- habit table

class _HabitTable extends StatelessWidget {
  final List<Map<String, dynamic>> habits;
  final String sort;
  final void Function(String) onSort;
  const _HabitTable({required this.habits, required this.sort, required this.onSort});

  List<Map<String, dynamic>> get _sorted {
    final list = [...habits];
    switch (sort) {
      case 'streak':
        list.sort((a, b) => asInt(b['current_streak']).compareTo(asInt(a['current_streak'])));
        break;
      case 'change':
        list.sort((a, b) => asInt(b['change']).compareTo(asInt(a['change'])));
        break;
      default:
        list.sort((a, b) => asInt(b['completion']).compareTo(asInt(a['completion'])));
    }
    return list;
  }

  @override
  Widget build(BuildContext context) {
    if (habits.isEmpty) {
      return const MockCard(
        child: Text('No habits tracked yet.',
            style: TextStyle(fontSize: 12, color: AppColors.dim)),
      );
    }
    return MockCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('Habit-by-habit',
                  style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800)),
              const Spacer(),
              _sortChip('completion', 'Rate'),
              const SizedBox(width: 6),
              _sortChip('streak', 'Streak'),
              const SizedBox(width: 6),
              _sortChip('change', 'Change'),
            ],
          ),
          const SizedBox(height: 12),
          const _HeaderRow(),
          const Divider(height: 12, color: AppColors.border),
          for (final h in _sorted) _HabitRow(h: h),
        ],
      ),
    );
  }

  Widget _sortChip(String key, String label) {
    final sel = sort == key;
    return GestureDetector(
      onTap: () => onSort(key),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
        decoration: BoxDecoration(
          color: sel ? AppColors.surface3 : AppColors.surface2,
          borderRadius: BorderRadius.circular(7),
          border: Border.all(color: AppColors.border),
        ),
        child: Text(label,
            style: TextStyle(
                fontSize: 10.5,
                fontWeight: sel ? FontWeight.w800 : FontWeight.w500,
                color: sel ? AppColors.text : AppColors.dim)),
      ),
    );
  }
}

class _HeaderRow extends StatelessWidget {
  const _HeaderRow();

  @override
  Widget build(BuildContext context) {
    const style = TextStyle(fontSize: 10, color: AppColors.faint, fontWeight: FontWeight.w700);
    return const Row(
      children: [
        Expanded(flex: 4, child: Text('HABIT', style: style)),
        Expanded(flex: 2, child: Text('RATE', style: style, textAlign: TextAlign.right)),
        Expanded(flex: 2, child: Text('DONE', style: style, textAlign: TextAlign.right)),
        Expanded(flex: 2, child: Text('SKIP', style: style, textAlign: TextAlign.right)),
        Expanded(flex: 2, child: Text('MISS', style: style, textAlign: TextAlign.right)),
        Expanded(flex: 2, child: Text('STREAK', style: style, textAlign: TextAlign.right)),
        Expanded(flex: 2, child: Text('BEST', style: style, textAlign: TextAlign.right)),
        Expanded(flex: 2, child: Text('±', style: style, textAlign: TextAlign.right)),
      ],
    );
  }
}

class _HabitRow extends StatelessWidget {
  final Map<String, dynamic> h;
  const _HabitRow({required this.h});

  @override
  Widget build(BuildContext context) {
    const style = TextStyle(fontSize: 11.5);
    final change = asInt(h['change']);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Expanded(
            flex: 4,
            child: Row(
              children: [
                Text(h['emoji']?.toString() ?? '',
                    style: const TextStyle(fontSize: 13)),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(h['name']?.toString() ?? '',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                ),
              ],
            ),
          ),
          Expanded(
            flex: 2,
            child: Text('${asInt(h['completion'])}%',
                textAlign: TextAlign.right,
                style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    color: hexColor(h['color'] as String?))),
          ),
          Expanded(flex: 2, child: Text('${asInt(h['completed_days'])}', textAlign: TextAlign.right, style: style)),
          Expanded(flex: 2, child: Text('${asInt(h['skipped_days'])}', textAlign: TextAlign.right, style: style)),
          Expanded(flex: 2, child: Text('${asInt(h['missed_days'])}', textAlign: TextAlign.right, style: style)),
          Expanded(flex: 2, child: Text('🔥 ${asInt(h['current_streak'])}', textAlign: TextAlign.right, style: style)),
          Expanded(flex: 2, child: Text('${asInt(h['best_streak'])}', textAlign: TextAlign.right, style: style)),
          Expanded(
            flex: 2,
            child: Text(
              change == 0 ? '—' : '${change > 0 ? '+' : ''}$change',
              textAlign: TextAlign.right,
              style: TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w700,
                  color: change > 0
                      ? AppColors.greenText
                      : change < 0
                          ? AppColors.rose
                          : AppColors.faint),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------- consistency

class _Consistency extends StatelessWidget {
  final Map<String, dynamic> data;
  const _Consistency({required this.data});

  @override
  Widget build(BuildContext context) {
    final series = List<Map<String, dynamic>>.from(
      (data['series'] as List? ?? []).map((e) => Map<String, dynamic>.from(e as Map)),
    );
    return MockCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('Consistency calendar',
                  style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800)),
              const SizedBox(width: 6),
              Text('${data['from']} → ${data['to']}',
                  style: const TextStyle(fontSize: 11, color: AppColors.dim)),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 3,
            runSpacing: 3,
            children: [
              for (final s in series)
                Tooltip(
                  message: '${s['date']} (${s['weekday']})\n'
                      '${s['done']}/${s['scheduled']} done'
                      '${s['rate'] == null ? ' · nothing scheduled' : ' · ${s['rate']}%'}',
                  child: Container(
                    width: 13,
                    height: 13,
                    decoration: BoxDecoration(
                      color: _cell(s),
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              const Text('less', style: TextStyle(fontSize: 10.5, color: AppColors.dim)),
              const SizedBox(width: 4),
              for (final c in [
                AppColors.track,
                AppColors.emerald.withValues(alpha: .25),
                AppColors.emerald.withValues(alpha: .45),
                AppColors.emerald.withValues(alpha: .72),
                AppColors.emerald,
              ])
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 2),
                  child: Container(
                    width: 13,
                    height: 13,
                    decoration: BoxDecoration(
                      color: c,
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                ),
              const SizedBox(width: 4),
              const Text('more', style: TextStyle(fontSize: 10.5, color: AppColors.dim)),
            ],
          ),
        ],
      ),
    );
  }

  static Color _cell(Map<String, dynamic> s) {
    final rate = s['rate'];
    if (rate == null) return AppColors.track;
    final v = asDouble(rate) / 100;
    if (v <= 0) return AppColors.surface3;
    if (v < .34) return AppColors.emerald.withValues(alpha: .25);
    if (v < .67) return AppColors.emerald.withValues(alpha: .45);
    if (v < .99) return AppColors.emerald.withValues(alpha: .72);
    return AppColors.emerald;
  }
}

// ---------------------------------------------------------------- insights

class _Insights extends StatelessWidget {
  final List<dynamic> insights;
  const _Insights({required this.insights});

  @override
  Widget build(BuildContext context) {
    return MockCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Insights',
              style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800)),
          const SizedBox(height: 10),
          for (final i in insights)
            Padding(
              padding: const EdgeInsets.only(bottom: 7),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.auto_awesome, size: 14, color: AppColors.violet),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      (i is Map ? i['text'] : i).toString(),
                      style: const TextStyle(fontSize: 12, height: 1.35),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
