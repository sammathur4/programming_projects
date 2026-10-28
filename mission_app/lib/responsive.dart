import 'package:flutter/material.dart';

import 'theme.dart';

/// Breakpoints mirroring the web mockup's CSS media queries.
///
/// The mockup shell is
///   `.shell{grid-template-columns:var(--sidebar) minmax(0,1fr) var(--rail)}`
/// with the sidebar dropping out below 1180px and the right rail below 1400px.
class Breakpoints {
  Breakpoints._();

  /// Below this width the persistent sidebar collapses into a Drawer.
  static const double sidebar = 1180;

  /// Below this width the right rail is hidden and its content is folded into
  /// the main column.
  static const double rail = 1400;

  /// Below this width two-column grids stack.
  static const double twoCol = 980;
}

/// Convenience flags for the current viewport.
class Layout {
  final double width;
  const Layout(this.width);

  bool get showSidebar => width >= Breakpoints.sidebar;
  bool get showRail => width >= Breakpoints.rail;
  bool get twoCol => width >= Breakpoints.twoCol;
  bool get isPhone => width < 700;

  static Layout of(BuildContext context) =>
      Layout(MediaQuery.sizeOf(context).width);
}

/// The mockup's `.card` — panel gradient, 1px line, 14px radius.
class MockCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;
  final Color? borderColor;

  const MockCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(14),
    this.margin,
    this.borderColor,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: margin,
      padding: padding,
      decoration: BoxDecoration(
        gradient: AppColors.cardGrad,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: borderColor ?? AppColors.border),
      ),
      child: child,
    );
  }
}

/// The mockup's small uppercase caption, e.g. `📝 NOTE FOR TODAY`.
class Cap extends StatelessWidget {
  final String text;
  const Cap(this.text, {super.key});

  @override
  Widget build(BuildContext context) => Text(
        text.toUpperCase(),
        style: const TextStyle(
          fontSize: 10.5,
          fontWeight: FontWeight.w800,
          color: AppColors.dim,
          letterSpacing: .7,
        ),
      );
}

/// The mockup's `.btn.sm` — a 32px bordered button.
class SmBtn extends StatelessWidget {
  final String label;
  final VoidCallback? onTap;
  final bool primary;
  const SmBtn(this.label, {super.key, this.onTap, this.primary = false});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Opacity(
        opacity: onTap == null ? .45 : 1,
        child: Container(
          height: 32,
          alignment: Alignment.center,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: BoxDecoration(
            color: primary ? AppColors.emerald : AppColors.surface2,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: primary ? AppColors.emerald : AppColors.border),
          ),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: primary ? const Color(0xFF04140A) : AppColors.text,
            ),
          ),
        ),
      ),
    );
  }
}

/// The mockup's `.ico` — a square bordered icon button.
class IcoBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;
  final double size;

  /// Optional icon colour — used to flag state (e.g. a pending-sync amber).
  final Color? tint;
  const IcoBtn(this.icon, {super.key, this.onTap, this.size = 34, this.tint});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Opacity(
        opacity: onTap == null ? .4 : 1,
        child: Container(
          width: size,
          height: size,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: AppColors.surface2,
            borderRadius: BorderRadius.circular(size <= 30 ? 8 : 10),
            border: Border.all(color: AppColors.border),
          ),
          child: Icon(icon, size: size <= 30 ? 15 : 17, color: tint ?? AppColors.text),
        ),
      ),
    );
  }
}

/// The mockup's `.ring` — a conic progress ring with the % in the middle.
class ScoreRing extends StatelessWidget {
  final int pct;
  final double size;
  final Color? color;
  final int stroke;
  const ScoreRing(this.pct, {super.key, this.size = 52, this.color, this.stroke = 5});

  @override
  Widget build(BuildContext context) {
    final c = color ??
        (pct >= 100
            ? AppColors.emerald
            : pct >= 50
                ? AppColors.blue
                : AppColors.amber);
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _RingPainter(pct: pct, color: c, stroke: stroke.toDouble()),
        child: Center(
          child: Text(
            '$pct%',
            style: TextStyle(fontSize: size <= 60 ? 12.5 : 16, fontWeight: FontWeight.w900),
          ),
        ),
      ),
    );
  }
}

class _RingPainter extends CustomPainter {
  final int pct;
  final Color color;
  final double stroke;
  _RingPainter({required this.pct, required this.color, required this.stroke});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final r = size.width / 2 - stroke / 2 - 1;
    canvas.drawCircle(
      center,
      r,
      Paint()
        ..color = AppColors.track
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke,
    );
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: r),
      -1.5708,
      6.2832 * (pct.clamp(0, 100) / 100),
      false,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(covariant _RingPainter old) =>
      old.pct != pct || old.color != color || old.stroke != stroke;
}

/// Lets a screen inside the shell jump to another tab.
///
/// The shell owns the selected tab, so a child that wants to open (say) the
/// Jaap counter asks for it through this rather than pushing a second copy of
/// the screen onto the navigation stack.
class TabSwitch extends InheritedWidget {
  final void Function(String id) go;

  const TabSwitch({super.key, required this.go, required super.child});

  /// Switch to [id], if the caller is inside a shell. Returns false when it
  /// is not (e.g. the screen is being shown on its own).
  static bool goTo(BuildContext context, String id) {
    final ts = context.dependOnInheritedWidgetOfExactType<TabSwitch>();
    if (ts == null) return false;
    ts.go(id);
    return true;
  }

  @override
  bool updateShouldNotify(TabSwitch oldWidget) => oldWidget.go != go;
}
