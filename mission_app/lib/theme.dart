import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Mission 2026 design system.
/// Dark "mission control" palette with gradient accents.
class AppColors {
  AppColors._();

  // Calm minimalist palette
  static const bg = Color(0xFF0F1026);        // softer deep background
  static const surface = Color(0xFF17182C);   // card/panel
  static const surface2 = Color(0xFF1F2138);  // inputs/secondary
  static const surface3 = Color(0xFF26273F);  // elevated
  static const border = Color(0xFF2F3158);    // subtle border
  static const track = Color(0xFF25274A);     // progress track
  static const text = Color(0xFFF5F7FF);      // primary text
  static const dim = Color(0xFFB7BCE6);       // secondary text
  static const faint = Color(0xFF8F93C9);     // tertiary text

  // Accents
  static const emerald = Color(0xFF4F9BFF);   // calmer accent (blue)
  static const blue = Color(0xFF7AA2FF);
  static const danger = Color(0xFFEF6B6B);
  static const rose = Color(0xFFEF6B6B);
  static const amber = Color(0xFFF5A623);
  static const orange = Color(0xFFF5A623);
  static const violet = Color(0xFFB9A6FF);
  static const gold = Color(0xFFF5C96E);
  static const sky = Color(0xFFB9D6FF);
  static const mint = Color(0xFF9BE7FF);

  // Text tints
  static const greenText = Color(0xFF9BE7FF);
  static const blueText = Color(0xFFB9D6FF);
  static const amberText = Color(0xFFF5C96E);
  static const roseText = Color(0xFFF5A3A3);
  static const violetText = Color(0xFFD6CCFF);

  // Gradients
  static const gradEmerald = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF9BE7FF), Color(0xFF4F9BFF)],
  );
  static const gradSky = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFDCEBFF), Color(0xFF7AA2FF)],
  );
  static const gradAmber = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFF7D9A3), Color(0xFFF5A623)],
  );
  static const gradRose = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFF7B9B9), Color(0xFFEF6B6B)],
  );
  static const gradViolet = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFFE7DEFF), Color(0xFFB9A6FF)],
  );

  /// Card surface gradient - calmer, subtler
  static const cardGrad = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [Color(0xFF1C1E33), Color(0xFF17182C)],
  );

  /// Score colors - calmer palette
  static Color forScore(int pct) {
    if (pct >= 90) return emerald;
    if (pct >= 70) return blue;
    if (pct >= 50) return amber;
    return violet;
  }

  static LinearGradient gradForScore(int pct) {
    if (pct >= 90) return gradEmerald;
    if (pct >= 70) return gradSky;
    if (pct >= 50) return gradAmber;
    return gradViolet;
  }
}

/// Parse a `#RRGGBB` (or bare hex) string into a Color.
Color hexColor(String? s, [Color fallback = AppColors.emerald]) {
  var hex = (s ?? '').replaceAll('#', '').trim();
  if (hex.length == 6) hex = 'FF$hex';
  final v = int.tryParse(hex, radix: 16);
  return v == null ? fallback : Color(v);
}

/// Coerce a JSON value to a double.
///
/// Django REST Framework serialises `DecimalField` as a **string** ("1.00"),
/// while computed values arrive as real numbers. Anything that reads a numeric
/// field from the API must go through here — a plain `as num` cast throws
/// `type 'String' is not a subtype of type 'num'`.
double asDouble(dynamic v, [double fallback = 0]) {
  if (v == null) return fallback;
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v.trim()) ?? fallback;
  return fallback;
}

/// Same coercion, rounded to an int (counts, calories, goals).
int asInt(dynamic v, [int fallback = 0]) {
  if (v == null) return fallback;
  if (v is int) return v;
  if (v is num) return v.round();
  if (v is String) return int.tryParse(v.trim()) ?? double.tryParse(v.trim())?.round() ?? fallback;
  return fallback;
}

/// Format a number without a trailing `.0` — 14.0 -> "14", 4.5 -> "4.5".
/// Values are rounded to at most 2 decimal places so floating-point noise
/// (104.80000000000001) never reaches the UI.
String fmtNum(dynamic v) {
  final d = asDouble(v);
  if (d == d.roundToDouble()) return d.round().toString();
  final rounded = double.parse(d.toStringAsFixed(2));
  if (rounded == rounded.roundToDouble()) return rounded.round().toString();
  return rounded.toStringAsFixed(2).replaceFirst(RegExp(r'0+$'), '').replaceFirst(RegExp(r'\.$'), '');
}

/// Always show exactly two decimals — used for weights and other measurements.
String fmt2(dynamic v) => asDouble(v).toStringAsFixed(2);

/// Global dark theme wired to [AppColors].
ThemeData buildTheme() {
  final base = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    colorScheme: ColorScheme.fromSeed(
      seedColor: AppColors.emerald,
      brightness: Brightness.dark,
    ).copyWith(
      surface: AppColors.surface,
      primary: AppColors.emerald,
    ),
  );
  return base.copyWith(
    scaffoldBackgroundColor: AppColors.bg,
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.bg,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        color: AppColors.text,
        fontSize: 20,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.3,
      ),
    ),
    cardTheme: CardThemeData(
      color: AppColors.surface,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: AppColors.border),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: AppColors.surface,
      indicatorColor: AppColors.emerald.withValues(alpha: 0.18),
      elevation: 0,
      height: 64,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (s) => TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: s.contains(WidgetState.selected) ? AppColors.mint : AppColors.faint,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (s) => IconThemeData(
          color: s.contains(WidgetState.selected) ? AppColors.mint : AppColors.faint,
        ),
      ),
    ),
    tabBarTheme: const TabBarThemeData(
      labelColor: AppColors.text,
      unselectedLabelColor: AppColors.faint,
      indicatorColor: AppColors.emerald,
      dividerColor: Colors.transparent,
      labelStyle: TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
      unselectedLabelStyle: TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
    ),
    inputDecorationTheme: InputDecorationTheme(
      isDense: true,
      filled: true,
      fillColor: AppColors.surface2,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      hintStyle: const TextStyle(color: AppColors.faint, fontSize: 13),
      labelStyle: const TextStyle(color: AppColors.dim, fontSize: 13),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: AppColors.emerald, width: 1.4),
      ),
    ),
    snackBarTheme: const SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.surface2,
      contentTextStyle: TextStyle(color: AppColors.text),
    ),
    chipTheme: ChipThemeData(
      backgroundColor: AppColors.surface2,
      selectedColor: AppColors.emerald.withValues(alpha: 0.22),
      side: const BorderSide(color: AppColors.border),
      labelStyle: const TextStyle(fontSize: 12, color: AppColors.text),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      showCheckmark: false,
    ),
    dividerTheme: const DividerThemeData(color: AppColors.border, thickness: 1, space: 1),
    textTheme: base.textTheme.apply(
      bodyColor: AppColors.text,
      displayColor: AppColors.text,
    ),
  );
}

// ---------------------------------------------------------------- shared widgets

/// A surface card with the design-system padding + border.
class AppCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;
  final Gradient? gradient;
  final Color? color;
  final VoidCallback? onTap;
  final Color? borderColor;

  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(14),
    this.margin,
    this.gradient,
    this.color,
    this.onTap,
    this.borderColor,
  });

  @override
  Widget build(BuildContext context) {
    final content = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: gradient == null ? (color ?? AppColors.surface) : null,
        gradient: gradient,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: borderColor ?? AppColors.border),
      ),
      child: child,
    );
    if (onTap == null) return Padding(padding: margin ?? EdgeInsets.zero, child: content);
    return Padding(
      padding: margin ?? EdgeInsets.zero,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: content,
        ),
      ),
    );
  }
}

/// Small uppercase section label.
class SectionLabel extends StatelessWidget {
  final String text;
  final IconData? icon;
  final Widget? trailing;
  const SectionLabel(this.text, {super.key, this.icon, this.trailing});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8, top: 2),
      child: Row(
        children: [
          if (icon != null) ...[
            Icon(icon, size: 15, color: AppColors.dim),
            const SizedBox(width: 6),
          ],
          Expanded(
            child: Text(
              text.toUpperCase(),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.1,
                color: AppColors.dim,
              ),
            ),
          ),
          // trailing pills can be long; keep them from overflowing the row
          if (trailing != null)
            Flexible(
              child: Align(
                alignment: Alignment.centerRight,
                child: trailing,
              ),
            ),
        ],
      ),
    );
  }
}

/// Rounded tag/pill.
class Pill extends StatelessWidget {
  final String text;
  final Color color;
  final IconData? icon;
  final bool filled;
  const Pill(this.text, {super.key, this.color = AppColors.dim, this.icon, this.filled = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: filled ? 0.22 : 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 11, color: color),
            const SizedBox(width: 4),
          ],
          Text(
            text,
            style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

/// Slim progress bar with optional gradient.
class ProgressBar extends StatelessWidget {
  final double value; // 0..1
  final Color color;
  final double height;
  final Gradient? gradient;
  const ProgressBar({
    super.key,
    required this.value,
    this.color = AppColors.emerald,
    this.height = 6,
    this.gradient,
  });

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(height),
      child: Container(
        height: height,
        color: Colors.white.withValues(alpha: 0.07),
        child: FractionallySizedBox(
          alignment: Alignment.centerLeft,
          widthFactor: value.clamp(0.0, 1.0),
          child: Container(
            decoration: BoxDecoration(
              gradient: gradient,
              color: gradient == null ? color : null,
            ),
          ),
        ),
      ),
    );
  }
}

/// A labelled stat number.
class StatBlock extends StatelessWidget {
  final String value;
  final String label;
  final Color color;
  final IconData? icon;
  const StatBlock(this.value, this.label, {super.key, this.color = AppColors.text, this.icon});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (icon != null) ...[
          Icon(icon, size: 14, color: color.withValues(alpha: 0.8)),
          const SizedBox(height: 3),
        ],
        Text(value,
            style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: color, height: 1.1)),
        const SizedBox(height: 2),
        Text(label,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 10.5, color: AppColors.faint, height: 1.2)),
      ],
    );
  }
}

/// Consistent empty-state pane.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget? action;
  const EmptyState({
    super.key,
    this.icon = Icons.inbox_outlined,
    required this.title,
    this.subtitle,
    this.action,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 46, color: AppColors.faint),
            const SizedBox(height: 14),
            Text(title,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
            if (subtitle != null) ...[
              const SizedBox(height: 6),
              Text(subtitle!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 12.5, color: AppColors.dim, height: 1.4)),
            ],
            if (action != null) ...[const SizedBox(height: 18), action!],
          ],
        ),
      ),
    );
  }
}

/// Consistent error pane with retry.
class ErrorPane extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const ErrorPane({super.key, required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off, size: 52, color: AppColors.faint),
            const SizedBox(height: 16),
            const Text('Server unreachable',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text(message,
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.dim, fontSize: 12.5)),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}

/// A point on a [LineChart]: an x label (usually a date) and a value.
class ChartPoint {
  final String label;
  final double value;
  const ChartPoint(this.label, this.value);
}

/// A lightweight line chart drawn with [CustomPaint] — no chart dependency.
///
/// Scales to its own min/max, draws a soft gradient fill under the line,
/// highlights the last point, and optionally renders horizontal guide lines
/// for reference values (a goal weight, a healthy-range bound…).
class LineChart extends StatelessWidget {
  final List<ChartPoint> points;
  final Color color;
  final double height;
  final List<ChartGuide> guides;
  final String? unit;
  /// Force the y range (e.g. BMI bands). null = fit to the data.
  final double? minY;
  final double? maxY;

  const LineChart({
    super.key,
    required this.points,
    this.color = AppColors.violet,
    this.height = 160,
    this.guides = const [],
    this.unit,
    this.minY,
    this.maxY,
  });

  @override
  Widget build(BuildContext context) {
    if (points.length < 2) {
      return SizedBox(
        height: height,
        child: Center(
          child: Text(
            points.isEmpty ? 'No data yet.' : 'One entry — log another to see a trend.',
            style: const TextStyle(color: AppColors.faint, fontSize: 12),
          ),
        ),
      );
    }
    return SizedBox(
      height: height,
      child: CustomPaint(
        size: Size.infinite,
        painter: _LinePainter(
          points: points,
          color: color,
          guides: guides,
          unit: unit,
          minY: minY,
          maxY: maxY,
        ),
      ),
    );
  }
}

/// A horizontal reference line on a [LineChart] (goal, healthy bound…).
class ChartGuide {
  final double value;
  final String label;
  final Color color;
  const ChartGuide(this.value, this.label, {this.color = AppColors.faint});
}

class _LinePainter extends CustomPainter {
  final List<ChartPoint> points;
  final Color color;
  final List<ChartGuide> guides;
  final String? unit;
  final double? minY;
  final double? maxY;

  _LinePainter({
    required this.points,
    required this.color,
    required this.guides,
    this.unit,
    this.minY,
    this.maxY,
  });

  @override
  void paint(Canvas canvas, Size size) {
    const padL = 42.0; // space for y labels
    const padR = 8.0;
    const padT = 10.0;
    const padB = 20.0; // space for x labels
    final w = size.width - padL - padR;
    final h = size.height - padT - padB;
    if (w <= 0 || h <= 0) return;

    final values = points.map((p) => p.value).toList();
    var lo = minY ?? values.reduce((a, b) => a < b ? a : b);
    var hi = maxY ?? values.reduce((a, b) => a > b ? a : b);
    // fold guides into the range so their lines stay on-canvas
    for (final g in guides) {
      if (minY == null && g.value < lo) lo = g.value;
      if (maxY == null && g.value > hi) hi = g.value;
    }
    if ((hi - lo).abs() < 1e-9) {
      lo -= 1;
      hi += 1;
    } else {
      final pad = (hi - lo) * 0.08;
      if (minY == null) lo -= pad;
      if (maxY == null) hi += pad;
    }
    final span = hi - lo;

    double yFor(double v) => padT + h - ((v - lo) / span) * h;
    double xFor(int i) => padL + (points.length == 1 ? w / 2 : i / (points.length - 1) * w);

    // ---- horizontal guide lines + y axis labels
    final labelStyle = TextStyle(color: AppColors.faint, fontSize: 9.5);
    for (var i = 0; i <= 3; i++) {
      final v = lo + span * i / 3;
      final y = yFor(v);
      canvas.drawLine(
        Offset(padL, y),
        Offset(padL + w, y),
        Paint()..color = AppColors.border.withValues(alpha: 0.5)..strokeWidth = 1,
      );
      _text(canvas, fmtNum(v), Offset(padL - 5, y), labelStyle, alignRight: true);
    }
    for (final g in guides) {
      final y = yFor(g.value);
      final p = Paint()
        ..color = g.color.withValues(alpha: 0.7)
        ..strokeWidth = 1.2;
      // dashed line
      for (double x = padL; x < padL + w; x += 6) {
        canvas.drawLine(Offset(x, y), Offset(x + 3, y), p);
      }
      _text(canvas, g.label, Offset(padL + 3, y - 11), TextStyle(color: g.color, fontSize: 9.5));
    }

    // ---- gradient fill under the line
    final linePath = Path()..moveTo(xFor(0), yFor(values[0]));
    for (var i = 1; i < values.length; i++) {
      linePath.lineTo(xFor(i), yFor(values[i]));
    }
    final fill = Path.from(linePath)
      ..lineTo(xFor(values.length - 1), padT + h)
      ..lineTo(xFor(0), padT + h)
      ..close();
    canvas.drawPath(
      fill,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [color.withValues(alpha: 0.28), color.withValues(alpha: 0.0)],
        ).createShader(Rect.fromLTWH(padL, padT, w, h)),
    );

    // ---- the line
    canvas.drawPath(
      linePath,
      Paint()
        ..color = color
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke
        ..strokeJoin = StrokeJoin.round
        ..strokeCap = StrokeCap.round,
    );

    // ---- points (small dots; last one highlighted)
    for (var i = 0; i < values.length; i++) {
      final last = i == values.length - 1;
      canvas.drawCircle(
        Offset(xFor(i), yFor(values[i])),
        last ? 3.6 : 1.8,
        Paint()..color = last ? color : color.withValues(alpha: 0.55),
      );
    }

    // ---- x axis: first + last date labels
    _text(canvas, points.first.label, Offset(padL, padT + h + 5), labelStyle);
    _text(canvas, points.last.label, Offset(padL + w, padT + h + 5), labelStyle, alignRight: true);

    // ---- last value callout
    final lastVal = values.last;
    final callout = unit == null ? fmtNum(lastVal) : '${fmtNum(lastVal)} $unit';
    _text(
      canvas,
      callout,
      Offset(xFor(values.length - 1), yFor(lastVal) - 16),
      TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w800),
      alignRight: true,
    );
  }

  void _text(Canvas canvas, String s, Offset at, TextStyle style, {bool alignRight = false}) {
    final tp = TextPainter(
      text: TextSpan(text: s, style: style),
      textDirection: TextDirection.ltr,
    )..layout();
    tp.paint(canvas, alignRight ? Offset(at.dx - tp.width, at.dy) : at);
  }

  @override
  bool shouldRepaint(_LinePainter old) =>
      old.points != points || old.color != color || old.guides != guides;
}

/// A tiny inline bar-sparkline for a 0-100 score series.
class Sparkline extends StatelessWidget {
  final List<int> values; // 0..100
  final Color color;
  final double height;
  const Sparkline({super.key, required this.values, this.color = AppColors.emerald, this.height = 34});

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return SizedBox(height: height);
    return SizedBox(
      height: height,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: values.map((v) {
          final frac = (v / 100).clamp(0.06, 1.0);
          final last = values.last == v;
          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 1.2),
              child: Container(
                height: height * frac,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: last ? 1.0 : 0.35 + frac * 0.4),
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// The mala — a ring of beads, one lit per count.
//
// The bead count is the user's choice (108 is the tradition, not a rule), so
// the ring is drawn from `beads` and the lit beads follow the count modulo
// that size. Completed rounds show as an outer halo.
// ---------------------------------------------------------------------------
class MalaRing extends StatelessWidget {
  final int count; // total jaaps so far
  final int beads; // beads in one round — the user's choice
  final Color color;
  final double size;
  final VoidCallback? onTap;
  final int completedMalas; // finished rounds, for the halo

  const MalaRing({
    super.key,
    required this.count,
    required this.beads,
    required this.color,
    this.size = 240,
    this.onTap,
    this.completedMalas = 0,
  });

  @override
  Widget build(BuildContext context) {
    final n = beads < 1 ? 1 : beads;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: SizedBox(
        width: size,
        height: size,
        child: CustomPaint(
          painter: _MalaPainter(
            count: count,
            beads: n,
            color: color,
            completedMalas: completedMalas,
          ),
        ),
      ),
    );
  }
}

class _MalaPainter extends CustomPainter {
  final int count;
  final int beads;
  final Color color;
  final int completedMalas;

  _MalaPainter({
    required this.count,
    required this.beads,
    required this.color,
    required this.completedMalas,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.width / 2 - 14;
    if (radius <= 0) return;

    // Outer halo — one faint arc per completed round (capped so a
    // thousand-mala day does not turn into a solid disc).
    if (completedMalas > 0) {
      final halo = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..color = color.withValues(alpha: 0.30);
      final turns = completedMalas > 12 ? 12 : completedMalas;
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius + 8),
        -1.5707963,
        6.2831853 * (turns / 12),
        false,
        halo,
      );
    }

    // The thread the beads sit on.
    final thread = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4
      ..color = AppColors.border;
    canvas.drawCircle(center, radius, thread);

    // Beads. Above ~150 the ring turns visually solid, so the beads shrink and
    // only the lit ones stay bright.
    final lit = count % beads;
    final dense = beads > 150;
    final beadR = dense ? 1.6 : (beads > 60 ? 3.0 : 5.0);

    final unlit = Paint()..color = AppColors.surface3;
    final litPaint = Paint()..color = color;
    final litGlow = Paint()..color = color.withValues(alpha: 0.22);

    for (var i = 0; i < beads; i++) {
      final angle = -1.5707963 + (6.2831853 * i / beads);
      final p = Offset(
        center.dx + radius * math.cos(angle),
        center.dy + radius * math.sin(angle),
      );
      if (i < lit) {
        if (!dense) {
          canvas.drawCircle(p, beadR * 2.1, litGlow);
        }
        canvas.drawCircle(p, beadR, litPaint);
      } else {
        canvas.drawCircle(p, beadR, unlit);
      }
    }
  }

  @override
  bool shouldRepaint(_MalaPainter old) =>
      old.count != count ||
      old.beads != beads ||
      old.color != color ||
      old.completedMalas != completedMalas;
}
