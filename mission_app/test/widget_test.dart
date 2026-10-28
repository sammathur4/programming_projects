import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mission_app/main.dart';
import 'package:mission_app/state.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('app builds and shows the mobile bottom navigation', (tester) async {
    SharedPreferences.setMockInitialValues({});
    // Mirror main(): Provider above MissionApp. AppState() without loadAll()
    // so the test stays offline (no real HTTP).
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AppState(),
        child: const MissionApp(),
      ),
    );
    await tester.pump();

    // The APK shell is deliberately focused: Today, Fitness, Timeline.
    // (Web keeps the full tab set — see kMobileShell in main.dart.)
    for (final label in kMobileTabLabels) {
      expect(find.text(label), findsWidgets);
    }
    expect(find.byType(NavigationBar), findsOneWidget);
    expect(find.byType(NavigationDestination), findsNWidgets(kMobileTabLabels.length));
  });

  testWidgets('wide surface keeps the mobile shell when kMobileShell is on',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = const Size(1600, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AppState(),
        child: const MissionApp(),
      ),
    );
    await tester.pump();

    // kMobileShell forces the phone shell at every size, so every mobile tab
    // must still be reachable rather than silently dropping to a sidebar.
    for (final label in kMobileTabLabels) {
      expect(find.text(label), findsWidgets);
    }
  });
}
