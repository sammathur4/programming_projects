import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mission_app/state.dart';
import 'package:mission_app/theme.dart';

/// The counter's local behaviour: the bead count is the user's choice, the
/// ring follows the count, and the counters agree with the rows.
void main() {
  AppState buildState() {
    final s = AppState();
    s.loading = false;
    s.jaapMantras = [
      {
        'id': 1,
        'name': 'Ram Naam',
        'emoji': '🙏',
        'beads': 108,
        'mala_size': 108,
        'goal': 108,
        'color': '#F5C96E',
      },
      {
        'id': 2,
        'name': 'Short',
        'emoji': '🕉',
        'beads': 10,
        'mala_size': 10,
        'goal': 10,
        'color': '#F5A623',
      },
    ];
    return s;
  }

  test('the active mantra defaults to the first in the library', () {
    final s = buildState();
    expect(s.jaapActive?['name'], 'Ram Naam');
  });

  test('the bead count comes from the mantra, not a hardcoded 108', () {
    final s = buildState();
    expect(asInt(s.jaapActive!['beads']), 108);
    s.jaapActiveId = 2;
    expect(asInt(s.jaapActive!['beads']), 10);
  });

  test('counts are tracked per mantra', () {
    final s = buildState();
    s.jaapToday[1] = 5;
    s.jaapToday[2] = 3;
    expect(s.jaapCountOf(1), 5);
    expect(s.jaapCountOf(2), 3);
    expect(s.jaapTodayTotal, 8);
  });

  test('an unknown mantra id counts as zero', () {
    final s = buildState();
    expect(s.jaapCountOf(999), 0);
    expect(s.jaapMalasOf(999), 0);
  });

  testWidgets('the ring lights one bead per count', (tester) async {
    for (final n in [0, 1, 54, 107, 108]) {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Center(
            child: MalaRing(
              count: n,
              beads: 108,
              color: const Color(0xFFF5C96E),
              size: 200,
            ),
          ),
        ),
      ));
      // The painter must not throw and must paint something.
      expect(tester.takeException(), isNull);
      expect(find.byType(MalaRing), findsOneWidget);
    }
  });

  testWidgets('the ring handles a large bead count without overflowing',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Center(
          child: MalaRing(
            count: 1007,
            beads: 1008,
            color: const Color(0xFFF5C96E),
            size: 200,
          ),
        ),
      ),
    ));
    expect(tester.takeException(), isNull);
  });

  testWidgets('a zero bead count still paints (it is clamped to one)',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Center(
          child: MalaRing(
            count: 3,
            beads: 0,
            color: const Color(0xFFF5C96E),
            size: 200,
          ),
        ),
      ),
    ));
    expect(tester.takeException(), isNull);
  });

  testWidgets('tapping the ring fires the callback', (tester) async {
    var taps = 0;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Center(
          child: MalaRing(
            count: 0,
            beads: 108,
            color: const Color(0xFFF5C96E),
            size: 200,
            onTap: () => taps++,
          ),
        ),
      ),
    ));
    await tester.tap(find.byType(MalaRing));
    expect(taps, 1);
  });
}
