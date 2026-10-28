import 'package:flutter/material.dart';

import '../api.dart';
import '../theme.dart';

/// Food — a MyFitnessPal-style diary.
///
/// Ring shows calories **remaining** (not eaten), four meal slots, and a
/// searchable dish database. Macros are snapshotted per entry by the backend,
/// so editing a dish later never rewrites what was already eaten.
class FoodScreen extends StatefulWidget {
  const FoodScreen({super.key});

  @override
  State<FoodScreen> createState() => _FoodScreenState();
}

class _FoodScreenState extends State<FoodScreen> {
  Map<String, dynamic>? _day;
  List<dynamic> _dishes = [];
  bool _loading = true;
  String? _error;
  String _query = '';
  String _mealFilter = 'Breakfast';

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
      final results = await Future.wait([
        Api.get('diary/'),
        Api.get('food/', {'limit': '60'}),
      ]);
      if (!mounted) return;
      setState(() {
        _day = results[0] as Map<String, dynamic>;
        _dishes = (results[1] as Map<String, dynamic>)['results'] as List<dynamic>;
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

  Future<void> _search(String q) async {
    setState(() => _query = q);
    try {
      final res = await Api.get('food/', {'q': q, 'limit': '60'});
      if (!mounted) return;
      setState(() => _dishes = (res as Map<String, dynamic>)['results'] as List<dynamic>);
    } catch (_) {/* keep the previous list on a failed search */}
  }

  Future<void> _logDish(Map<String, dynamic> dish) async {
    final qty = await showDialog<double>(
      context: context,
      builder: (_) => _QuantityDialog(dish: dish, meal: _mealFilter),
    );
    if (qty == null) return;
    try {
      await Api.send('POST', 'diary/', {
        'date': _day?['date'],
        'meal': _mealFilter,
        'food_id': dish['id'],
        'quantity': qty,
      }, label: '${dish['name']} ×$qty · $_mealFilter',
          dedupeId: 'diary-${DateTime.now().microsecondsSinceEpoch}');
      await _load();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${dish['name']} × $qty added to $_mealFilter')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not log: $e')));
    }
  }

  Future<void> _removeEntry(int id, String name) async {
    // optimistic: drop the row, reload from server
    try {
      await Api.delete('diary/$id/', null, true, 'Remove $name');
      await _load();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not remove: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) return ErrorPane(message: _error!, onRetry: _load);
    final day = _day!;
    final totals = day['totals'] as Map<String, dynamic>;
    final targets = day['targets'] as Map<String, dynamic>;
    final mealsRaw = day['meals'];
    final meals = mealsRaw is List ? mealsRaw : [];
    final eaten = asInt(totals['kcal']);
    final goal = asInt(targets['calorie_goal']);
    final remaining = goal - eaten;
    final pct = goal == 0 ? 0.0 : (eaten / goal).clamp(0.0, 1.0).toDouble();
    final over = remaining < 0;
    final ringColor = over
        ? AppColors.rose
        : pct > 0.85
            ? AppColors.amber
            : AppColors.emerald;

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(14, 14, 14, 28),
        children: [
          _ringCard(eaten, goal, remaining, pct, ringColor, over, totals, targets),
          const SizedBox(height: 14),
          SectionLabel('Today\'s diary', icon: Icons.restaurant_menu),
          ...meals.map((m) => _mealCard(m as Map<String, dynamic>)),
          const SizedBox(height: 12),
          SectionLabel(
            'Dish database',
            icon: Icons.search,
            trailing: Pill('${_dishes.length} shown', color: AppColors.sky),
          ),
          _searchCard(),
          ..._dishes.map((d) => _dishRow(d as Map<String, dynamic>)),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------- ring
  Widget _ringCard(int eaten, int goal, int remaining, double pct, Color ringColor, bool over,
      Map<String, dynamic> totals, Map<String, dynamic> targets) {
    final macros = [
      ('Protein', asDouble(totals['protein_g']), asInt(targets['protein_goal']), AppColors.blue),
      ('Carbs', asDouble(totals['carbs_g']), asInt(targets['carbs_goal']), AppColors.amber),
      ('Fat', asDouble(totals['fat_g']), asInt(targets['fat_goal']), AppColors.violet),
    ];
    return AppCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 108,
            height: 108,
            child: Stack(
              alignment: Alignment.center,
              children: [
                CustomPaint(
                  size: const Size(108, 108),
                  painter: _RingPainter(progress: pct, color: ringColor),
                ),
                Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('${remaining.abs()}',
                        style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: ringColor)),
                    Text(over ? 'OVER' : 'LEFT',
                        style: const TextStyle(
                            fontSize: 9, letterSpacing: .8, color: AppColors.faint, fontWeight: FontWeight.w800)),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                for (final m in macros) ...[
                  Row(
                    children: [
                      Expanded(
                          child: Text(m.$1,
                              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700))),
                      Text('${m.$2.round()} / ${m.$3}g',
                          style: const TextStyle(fontSize: 11, color: AppColors.dim)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  ProgressBar(value: m.$3 == 0 ? 0 : (m.$2 / m.$3).clamp(0.0, 1.0), color: m.$4, height: 5),
                  const SizedBox(height: 10),
                ],
                const Divider(height: 1, color: AppColors.border),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Eaten $eaten', style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                    Text('Goal $goal kcal',
                        style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------- meals
  Widget _mealCard(Map<String, dynamic> meal) {
    final entriesRaw = meal['entries'];
    final entries = entriesRaw is List ? entriesRaw : [];
    const icons = {
      'Breakfast': Icons.wb_twilight,
      'Lunch': Icons.lunch_dining,
      'Dinner': Icons.nightlight_round,
      'Snack': Icons.apple,
    };
    final name = meal['meal'] as String;
    final selected = _mealFilter == name;
    return AppCard(
      margin: const EdgeInsets.only(bottom: 9),
      borderColor: selected ? AppColors.emerald.withValues(alpha: .5) : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icons[name] ?? Icons.restaurant, size: 17, color: AppColors.dim),
              const SizedBox(width: 8),
              Expanded(
                child: Text(name,
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800)),
              ),
              Text('${asInt(meal['kcal'])}',
                  style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900)),
              const SizedBox(width: 3),
              const Text('kcal', style: TextStyle(fontSize: 9.5, color: AppColors.faint)),
              const SizedBox(width: 8),
              // tapping the meal selects where the next dish goes
              GestureDetector(
                onTap: () => setState(() => _mealFilter = name),
                child: Pill(
                  selected ? '✓ target' : 'log here',
                  color: selected ? AppColors.emerald : AppColors.dim,
                ),
              ),
            ],
          ),
          if (entries.isEmpty)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: Text('Nothing logged yet.',
                  style: TextStyle(fontSize: 11.5, color: AppColors.faint)),
            )
          else
            ...entries.map((e) {
              final en = e as Map<String, dynamic>;
              return Padding(
                padding: const EdgeInsets.only(top: 7),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(en['food_name'] as String,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
                    ),
                    Text('×${_trimQty(en['quantity'])}',
                        style: const TextStyle(fontSize: 10.5, color: AppColors.faint)),
                    const SizedBox(width: 10),
                    Text('${asInt(en['kcal'])}',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800)),
                    const SizedBox(width: 6),
                    GestureDetector(
                      onTap: () => _removeEntry(en['id'] as int, en['food_name'] as String),
                      child: const Icon(Icons.close, size: 15, color: AppColors.dim),
                    ),
                  ],
                ),
              );
            }),
        ],
      ),
    );
  }

  static String _trimQty(dynamic q) => fmtNum(q);

  // ---------------------------------------------------------------- dishes
  Widget _searchCard() {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 9),
      child: TextField(
        onChanged: _search,
        style: const TextStyle(fontSize: 13),
        decoration: InputDecoration(
          hintText: 'Search a dish — roti, paneer, dosa…',
          hintStyle: const TextStyle(fontSize: 13, color: AppColors.faint),
          prefixIcon: const Icon(Icons.search, size: 18, color: AppColors.dim),
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(vertical: 12),
          border: InputBorder.none,
          suffixIcon: _query.isEmpty
              ? null
              : IconButton(
                  icon: const Icon(Icons.clear, size: 16),
                  onPressed: () {
                    _search('');
                  },
                ),
        ),
      ),
    );
  }

  Widget _dishRow(Map<String, dynamic> dish) {
    return AppCard(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 10),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(dish['name'] as String,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(
                  '${dish['serving']}  ·  P${_n(dish['protein_g'])} C${_n(dish['carbs_g'])} F${_n(dish['fat_g'])}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 10, color: AppColors.faint),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text('${asInt(dish['kcal'])}',
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w900)),
          const SizedBox(width: 2),
          const Text('kcal', style: TextStyle(fontSize: 9, color: AppColors.faint)),
          const SizedBox(width: 8),
          FilledButton(
            onPressed: () => _logDish(dish),
            style: FilledButton.styleFrom(
              minimumSize: const Size(38, 32),
              padding: EdgeInsets.zero,
              backgroundColor: AppColors.emerald,
              foregroundColor: Colors.black,
            ),
            child: const Icon(Icons.add, size: 17),
          ),
        ],
      ),
    );
  }

  /// 14.0 -> "14", 4.5 -> "4.5"
  static String _n(dynamic v) => fmtNum(v);
}

/// Donut showing the fraction of the daily calorie goal used.
class _RingPainter extends CustomPainter {
  final double progress;
  final Color color;
  _RingPainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 7;
    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 9
      ..color = AppColors.surface2;
    final arc = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 9
      ..strokeCap = StrokeCap.round
      ..color = color;
    canvas.drawCircle(center, radius, track);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -1.5708, // start at 12 o'clock
      6.2832 * progress,
      false,
      arc,
    );
  }

  @override
  bool shouldRepaint(_RingPainter old) => old.progress != progress || old.color != color;
}

/// Asks how many servings, showing the resulting calories live.
class _QuantityDialog extends StatefulWidget {
  final Map<String, dynamic> dish;
  final String meal;
  const _QuantityDialog({required this.dish, required this.meal});

  @override
  State<_QuantityDialog> createState() => _QuantityDialogState();
}

class _QuantityDialogState extends State<_QuantityDialog> {
  double _qty = 1;

  @override
  Widget build(BuildContext context) {
    final per = asInt(widget.dish['kcal']);
    final total = (per * _qty).round();
    return AlertDialog(
      title: Text(widget.dish['name'] as String, style: const TextStyle(fontSize: 16)),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('${widget.dish['serving']} · $per kcal each',
              style: const TextStyle(fontSize: 12, color: AppColors.dim)),
          const SizedBox(height: 16),
          Row(
            children: [
              IconButton(
                onPressed: _qty <= 0.5 ? null : () => setState(() => _qty -= 0.5),
                icon: const Icon(Icons.remove_circle_outline),
              ),
              Expanded(
                child: Text('$_qty',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
              ),
              IconButton(
                onPressed: () => setState(() => _qty += 0.5),
                icon: const Icon(Icons.add_circle_outline),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Center(
            child: Text('$total kcal → ${widget.meal}',
                style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: AppColors.emerald)),
          ),
        ],
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(
          onPressed: () => Navigator.pop(context, _qty),
          child: const Text('Add'),
        ),
      ],
    );
  }
}
