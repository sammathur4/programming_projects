import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mission_app/screens/today.dart';
import 'package:mission_app/state.dart';
import 'package:mission_app/theme.dart';
import 'package:provider/provider.dart';

/// Renders the Today screen with a fully-populated overview + dashboard and
/// fails on any layout overflow / paint error.
void main() {
  testWidgets('Today screen renders with data and no overflow', (tester) async {
    tester.view.physicalSize = const Size(1080, 2100);
    tester.view.devicePixelRatio = 3.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    final state = AppState();
    state.loading = false;
    state.overview = {
      'date': '2026-10-20',
      'daily_score': 60,
      'done_today': 6,
      'habit_total': 10,
      'range': {'from': '2026-09-21', 'to': '2026-10-20'},
      'habits': List.generate(
        10,
        (i) => {
          'id': i + 1,
          'name': 'Habit number ${i + 1} with a longer name',
          'emoji': '✅',
          'color': '#22c55e',
          'streak': i,
          'best_streak': i + 2,
          'completion_30d': 40 + i,
          'is_paused': false,
          'done_today': i.isEven,
          'today_note': i == 0 ? 'a note' : '',
        },
      ),
      'fitness': {
        'date': '2026-10-20',
        'mode': 'WFO',
        'status': 'Pending',
        'weight_kg': 102.6,
        'calories_in': 1750,
        'water_litres': 4.5,
      },
      'study': {
        'date': '2026-10-20',
        'mode': 'WFH',
        'aw_count': 2,
        'mcq_count': 40,
        'study_hours': 5.5,
        'slots': [
          {'subject': 'Polity', 'status': 'Done'},
          {'subject': 'History', 'status': 'Pending'},
        ],
      },
    };
    state.dashboard = {
      'score': 60,
      'done_today': 6,
      'habit_total': 10,
      'at_risk': [
        {'id': 3, 'name': 'UPSC', 'emoji': '📚', 'color': '#3b82f6', 'streak': 12},
      ],
      'focus': {'id': 7, 'name': 'Diet', 'momentum': 12, 'trend': -30},
      'improving': [],
      'burnout': {
        'level': 'watch',
        'reasons': ['Momentum is cooling off'],
        'advice': 'Protect sleep this week.',
        'score': 30,
      },
      'recovery': {'rate': 62, 'label': 'Solid recovery'},
      'consistency_30d': 48,
      'spark': List.generate(14, (i) => {'date': 'd$i', 'score': i * 6}),
    };

    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: state,
        child: MaterialApp(
          theme: buildTheme(),
          home: const Scaffold(body: TodayScreen()),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // The app bar (which carries the word "Today") lives in main.dart's shell,
    // not in TodayScreen — so assert on what this screen actually renders.
    expect(find.byType(TodayScreen), findsOneWidget);
    // A habit name from the fixture must be on screen.
    expect(find.textContaining('Habit number 1'), findsWidgets);
    // no exception thrown during layout means no RenderFlex overflow
    expect(tester.takeException(), isNull);
  });
}
