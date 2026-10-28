import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'responsive.dart';
import 'offline.dart';
import 'screens/fitness.dart';
import 'screens/food.dart';
import 'screens/goals.dart' as goals;
import 'screens/habits.dart' as habits;
import 'screens/jaap.dart';
import 'screens/notes.dart' as notes;
import 'screens/settings.dart';
import 'screens/stats.dart';
import 'screens/study.dart' as study;
import 'screens/sync.dart';
import 'screens/timeline.dart';
import 'screens/today.dart';
import 'screens/vision_board.dart';
import 'state.dart';
import 'theme.dart';

/// The APK ships a focused, phone-sized shell; the web build keeps every tab.
///
/// Flip this to `false` to get the full 10-tab shell in a native build (useful
/// on a tablet, or when developing against the phone UI).
const bool kMobileShell = !kIsWeb;

/// Tabs that survive into the mobile shell — Today, Fitness, Jaap and Timeline.
const List<String> kMobileTabIds = ['today', 'fitness', 'jaap', 'timeline'];

/// Human labels for the mobile tabs, derived from [kTabs] so tests and UI can
/// never disagree about what the phone shell shows.
List<String> get kMobileTabLabels =>
    [for (final id in kMobileTabIds) kTabs.firstWhere((t) => t.id == id).label];

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // In release builds a thrown layout error renders as a plain grey box.
  // Surface the actual exception so bugs are visible instead of mysterious.
  ErrorWidget.builder = (details) {
    if (kDebugMode) return ErrorWidget(details.exception);
    return Directionality(
      textDirection: TextDirection.ltr,
      child: Container(
        margin: const EdgeInsets.all(8),
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: const Color(0xFF3B1420),
          border: Border.all(color: const Color(0xFFEF4444)),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          'UI error: ${details.exception}',
          style: const TextStyle(color: Color(0xFFFCA5A5), fontSize: 11),
        ),
      ),
    );
  };
  runApp(
    ChangeNotifierProvider(
      // Restore the saved Server URL override before the first API call, so a
      // phone that has been pointed at a LAN IP keeps working after a restart.
      create: (_) {
        final state = AppState();
        // Rebuild the header badge whenever the offline queue changes.
        OfflineStore.notify = state.notifyQueueChanged;
        state.init();
        return state;
      },
      child: const MissionApp(),
    ),
  );
}

class MissionApp extends StatelessWidget {
  const MissionApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Mission 2026',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      home: const HomeShell(),
    );
  }
}

/// One entry in the app's navigation — mirrors `TABS` in the web mockup.
class MissionTab {
  final String id;
  final String icon;
  final String label;
  final String sub;
  final String add; // label for the header's primary button, '' hides it
  final bool rail; // does this tab show the right rail?
  const MissionTab({
    required this.id,
    required this.icon,
    required this.label,
    required this.sub,
    this.add = '',
    this.rail = true,
  });
}

const kTabs = <MissionTab>[
  MissionTab(id: 'today', icon: '✅', label: 'Today', sub: 'Your day at a glance', add: 'Log habit'),
  MissionTab(id: 'habits', icon: '▦', label: 'Habits', sub: 'Track consistency', add: 'New habit'),
  MissionTab(id: 'study', icon: '📚', label: 'Study', sub: 'Learning & resources', add: 'Add resource'),
  MissionTab(id: 'fitness', icon: '🏋️', label: 'Fitness', sub: 'Training & recovery', add: 'Log workout'),
  MissionTab(id: 'jaap', icon: '🙏', label: 'Jaap', sub: 'Count your mantra', add: ''),
  MissionTab(id: 'food', icon: '🍛', label: 'Food', sub: 'Nutrition & macros', add: 'Log food'),
  MissionTab(id: 'goals', icon: '🎯', label: 'Goals', sub: 'Objectives & milestones', add: 'New goal'),
  MissionTab(id: 'notes', icon: '📝', label: 'Notes', sub: 'Thoughts & reflections', add: 'New note'),
  MissionTab(id: 'stats', icon: '📊', label: 'Stats', sub: 'Trends & insights'),
  MissionTab(id: 'timeline', icon: '🕓', label: 'Timeline', sub: 'Everything you logged', rail: false),
  MissionTab(id: 'vision', icon: '✨', label: 'Vision', sub: 'North star', rail: false),
  MissionTab(id: 'settings', icon: '⚙️', label: 'Settings', sub: 'Preferences', rail: false),
];

/// The mockup's `NAV_GROUPS`.
const kNavGroups = <List<String>>[
  ['today', 'jaap', 'habits', 'stats'],
  ['study', 'fitness', 'food'],
  ['goals', 'notes', 'vision'],
];

/// Tabs surfaced alongside Settings in the sidebar's SYSTEM section.
const kSystemTabs = <String>['timeline'];

class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  String _tab = 'today';
  bool _collapsed = false;

  /// The tabs available in this build — the full set on web, a focused set
  /// (Today · Fitness · Jaap · Timeline) in the phone app.
  List<MissionTab> get _tabs => kMobileShell
      ? [for (final id in kMobileTabIds) kTabs.firstWhere((t) => t.id == id)]
      : kTabs;

  MissionTab get _current =>
      _tabs.firstWhere((t) => t.id == _tab, orElse: () => _tabs.first);

  void _go(String id) {
    setState(() => _tab = id);
    final state = context.read<AppState>();
    if (id == 'stats') {
      state.loadStats();
      if (state.heatmap == null) state.loadHeatmap();
    }
    if (id == 'habits') state.loadHeatmap();
    if (id == 'goals') state.loadStats();
    if (id == 'notes') state.loadNoteSnapshot();
    if (id == 'fitness') state.loadFitnessSnapshot();
    if (id == 'food') state.loadDiaryTotals();
    if (id == 'jaap') state.loadJaap();
  }

  Widget _screen(String id) {
    switch (id) {
      case 'habits':
        return const habits.HabitsScreen();
      case 'study':
        return const study.StudyScreen();
      case 'fitness':
        return const FitnessScreen();
      case 'jaap':
        return const JaapScreen();
      case 'food':
        return const FoodScreen();
      case 'goals':
        return const goals.GoalsScreen();
      case 'notes':
        return const notes.NotesScreen();
      case 'stats':
        return const StatsScreen();
      case 'timeline':
        return const TimelineScreen();
      case 'vision':
        return const VisionBoardScreen();
      case 'settings':
        return const SettingsScreen();
      case 'today':
      default:
        return const TodayScreen();
    }
  }

  @override
  Widget build(BuildContext context) {
    final layout = Layout.of(context);
    final tab = _current;

    if (!layout.showSidebar) {
      // Phone/narrow: bottom navigation, no rail.
      return Scaffold(
        appBar: _header(context, tab, compact: true),
        drawer: _drawer(context),
        body: TabSwitch(
          go: _go,
          child: IndexedStack(
            index: _tabs.indexWhere((t) => t.id == _tab),
            children: [for (final t in _tabs) _screen(t.id)],
          ),
        ),
        bottomNavigationBar: NavigationBar(
          height: 62,
          selectedIndex: _navIndex(),
          onDestinationSelected: (i) => _go(_bottomTabs()[i].id),
          destinations: [
            for (final t in _bottomTabs())
              NavigationDestination(
                icon: Text(t.icon, style: const TextStyle(fontSize: 18)),
                selectedIcon: Text(t.icon, style: const TextStyle(fontSize: 20)),
                label: t.label,
              ),
          ],
        ),
      );
    }

    // Desktop: sidebar + main + optional rail, exactly like `.shell`.
    return Scaffold(
      backgroundColor: AppColors.bg,
      body: TabSwitch(
        go: _go,
        child: Row(
          children: [
            _Sidebar(
              current: _tab,
              collapsed: _collapsed,
              onToggle: () => setState(() => _collapsed = !_collapsed),
              onGo: _go,
            ),
            Expanded(
              child: Column(
                children: [
                  _header(context, tab, compact: false),
                  Expanded(child: _screen(_tab)),
                ],
              ),
            ),
            if (layout.showRail && tab.rail)
              SizedBox(
                width: 320,
                child: _Rail(tab: _tab, onGo: _go),
              ),
          ],
        ),
      ),
    );
  }

  /// The primary tabs shown in the mobile bottom bar.
  ///
  /// Mobile shell: Today · Fitness · Timeline. Web/narrow: the five core tabs.
  List<MissionTab> _bottomTabs() => kMobileShell
      ? _tabs
      : [
          kTabs[0], // today
          kTabs[1], // habits
          kTabs[2], // study
          kTabs[3], // fitness
          kTabs[4], // food
        ];

  int _navIndex() {
    final i = _bottomTabs().indexWhere((t) => t.id == _tab);
    return i == -1 ? 0 : i;
  }

  /// Open Settings. On web it's a real tab; in the mobile shell (where it has
  /// no tab of its own) it's pushed as a page so the Server URL field and the
  /// weight-tracker profile stay reachable.
  void _openSettings(BuildContext context) {
    if (kMobileShell) {
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => const SettingsScreen()),
      );
    } else {
      _go('settings');
    }
  }

  PreferredSizeWidget _header(BuildContext context, MissionTab tab, {required bool compact}) {
    final state = context.watch<AppState>();
    final daysLeft = _daysLeft(state);
    return AppBar(
      toolbarHeight: 60,
      backgroundColor: AppColors.bg.withValues(alpha: .86),
      elevation: 0,
      scrolledUnderElevation: 0,
      automaticallyImplyLeading: false,
      titleSpacing: compact ? 8 : 20,
      title: Row(
        children: [
          if (compact)
            Builder(
              builder: (ctx) => IcoBtn(Icons.menu, onTap: () => Scaffold.of(ctx).openDrawer()),
            ),
          if (compact) const SizedBox(width: 10),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(tab.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, letterSpacing: -.2)),
                if (!compact)
                  Text(tab.sub,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 12, color: AppColors.dim, fontWeight: FontWeight.w500)),
              ],
            ),
          ),
        ],
      ),
      actions: [
        Expanded(child: Center(child: _Countdown(daysLeft: daysLeft))),
        const SizedBox(width: 8),
        _SyncButton(state: state),
        const SizedBox(width: 6),
        IcoBtn(Icons.refresh, onTap: () => state.loadAll()),
        const SizedBox(width: 6),
        IcoBtn(Icons.settings_outlined, onTap: () => _openSettings(context)),
        if (tab.add.isNotEmpty) ...[
          const SizedBox(width: 10),
          Padding(
            padding: const EdgeInsets.only(right: 18),
            child: SmBtn('＋ ${tab.add}', primary: true, onTap: () => _onAdd(context, tab.id)),
          ),
        ] else
          const SizedBox(width: 18),
      ],
    );
  }

  void _onAdd(BuildContext context, String tabId) async {
    final state = context.read<AppState>();
    switch (tabId) {
      case 'habits':
        await showDialog<bool>(
          context: context,
          builder: (_) => habits.HabitEditDialog(habit: null),
        );
        await state.loadAll();
        await state.loadHeatmap();
        break;
      case 'goals':
        await showDialog<bool>(
          context: context,
          builder: (_) => goals.GoalEditDialog(objective: null),
        );
        await state.loadStats();
        break;
      case 'notes':
        await showDialog<bool>(
          context: context,
          builder: (_) => notes.NoteEditor(note: null, defaultTag: 'day'),
        );
        await state.loadNoteSnapshot();
        break;
      case 'study':
        await showDialog<bool>(
          context: context,
          builder: (_) => study.StudyResourceDialog(resource: null),
        );
        break;
      case 'today':
      default:
        _go('habits');
        await showDialog<bool>(
          context: context,
          builder: (_) => habits.HabitEditDialog(habit: null),
        );
        await state.loadAll();
        break;
    }
  }

  static int _daysLeft(AppState state) {
    final endStr = state.settingValue('mission_end', '');
    DateTime? end;
    if (endStr.contains('/')) {
      final p = endStr.split('/');
      if (p.length == 3) end = DateTime(int.parse(p[2]), int.parse(p[1]), int.parse(p[0]));
    } else if (endStr.isNotEmpty) {
      end = DateTime.tryParse(endStr);
    }
    end ??= DateTime(2027, 5, 1);
    return end.difference(DateTime.now()).inDays;
  }

  Widget _drawer(BuildContext context) {
    return Drawer(
      backgroundColor: AppColors.surface,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 18, 16, 10),
              child: Text('🔥 Mission 2026',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: -.3)),
            ),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                children: [
                  if (kMobileShell) ...[
                    const Padding(
                      padding: EdgeInsets.fromLTRB(11, 8, 11, 6),
                      child: Text('MISSION',
                          style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 1,
                              color: AppColors.faint)),
                    ),
                    for (final id in kMobileTabIds) _drawerItem(id),
                  ] else
                    for (final group in kNavGroups) ...[
                      for (final id in group) _drawerItem(id),
                    ],
                  const SizedBox(height: 10),
                  const Padding(
                    padding: EdgeInsets.fromLTRB(11, 8, 11, 6),
                    child: Text('SYSTEM',
                        style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1,
                            color: AppColors.faint)),
                  ),
                  if (!kMobileShell) _drawerItem('timeline'),
                  _drawerItem('settings'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _drawerItem(String id) {
    final t = kTabs.firstWhere((x) => x.id == id);
    final on = _tab == id;
    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: ListTile(
        dense: true,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(11)),
        selected: on,
        selectedTileColor: AppColors.surface3,
        leading: Text(t.icon, style: const TextStyle(fontSize: 16)),
        title: Text(t.label,
            style: TextStyle(
                fontSize: 13.5,
                fontWeight: on ? FontWeight.w700 : FontWeight.w600,
                color: on ? AppColors.text : AppColors.dim)),
        onTap: () {
          Navigator.pop(context);
          if (id == 'settings') {
            _openSettings(context);
          } else {
            _go(id);
          }
        },
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Sidebar — the mockup's `.side`, with grouped nav and the streak footer.
// ---------------------------------------------------------------------------
class _Sidebar extends StatelessWidget {
  final String current;
  final bool collapsed;
  final VoidCallback onToggle;
  final void Function(String) onGo;
  const _Sidebar({
    required this.current,
    required this.collapsed,
    required this.onToggle,
    required this.onGo,
  });

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final habits = (state.overview?['habits'] as List? ?? []);
    Map<String, dynamic>? best;
    for (final h in habits) {
      final m = Map<String, dynamic>.from(h as Map);
      if (best == null || asInt(m['best_streak']) > asInt(best['best_streak'])) best = m;
    }

    return Container(
      width: collapsed ? 64 : 236,
      decoration: const BoxDecoration(
        color: Color(0xFF0D111E),
        border: Border(right: BorderSide(color: AppColors.border)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(14, 16, 14, 14),
            child: Row(
              children: [
                const Text('🔥', style: TextStyle(fontSize: 19)),
                if (!collapsed) ...[
                  const SizedBox(width: 9),
                  const Flexible(
                    child: Text.rich(
                      TextSpan(children: [
                        TextSpan(text: 'Mission ', style: TextStyle(color: AppColors.text)),
                        TextSpan(text: '2026', style: TextStyle(color: AppColors.emerald)),
                      ]),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, letterSpacing: -.3),
                    ),
                  ),
                ],
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              children: [
                for (var g = 0; g < kNavGroups.length; g++) ...[
                  if (g == 1 || g == 2)
                    Padding(
                      padding: const EdgeInsets.fromLTRB(11, 14, 11, 6),
                      child: Text(
                        collapsed ? '···' : (g == 1 ? 'DIRECTION' : 'INSIGHT'),
                        style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1,
                            color: AppColors.faint),
                      ),
                    ),
                  for (final id in kNavGroups[g]) _navBtn(id, state),
                ],
                const Padding(
                  padding: EdgeInsets.fromLTRB(11, 14, 11, 6),
                  child: Text('SYSTEM',
                      style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1,
                          color: AppColors.faint)),
                ),
                for (final id in kSystemTabs) _navBtn(id, state),
                _navBtn('settings', state),
              ],
            ),
          ),
          if (!collapsed)
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 8, 10, 12),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.fromLTRB(11, 10, 11, 10),
                decoration: BoxDecoration(
                  color: AppColors.surface2,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Cap('Longest streak'),
                    const SizedBox(height: 2),
                    Text('🔥 ${best == null ? 0 : asInt(best['best_streak'])} days',
                        style: const TextStyle(
                            fontSize: 19, fontWeight: FontWeight.w900, color: AppColors.orange)),
                    const SizedBox(height: 1),
                    Text((best?['name'] ?? '—').toString(),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 10.5, color: AppColors.dim)),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _navBtn(String id, AppState state) {
    final t = kTabs.firstWhere((x) => x.id == id);
    final on = current == id;
    final badge = _badgeFor(id, state);
    return Padding(
      padding: const EdgeInsets.only(bottom: 2),
      child: Material(
        color: on ? AppColors.surface3 : Colors.transparent,
        borderRadius: BorderRadius.circular(11),
        child: InkWell(
          borderRadius: BorderRadius.circular(11),
          onTap: () => onGo(id),
          child: Padding(
            padding: EdgeInsets.symmetric(horizontal: collapsed ? 0 : 11, vertical: 9),
            child: Row(
              mainAxisAlignment: collapsed ? MainAxisAlignment.center : MainAxisAlignment.start,
              children: [
                if (on && !collapsed)
                  Container(
                    width: 3,
                    height: 16,
                    margin: const EdgeInsets.only(right: 8),
                    decoration: const BoxDecoration(
                      color: AppColors.emerald,
                      borderRadius: BorderRadius.only(
                        topRight: Radius.circular(3),
                        bottomRight: Radius.circular(3),
                      ),
                    ),
                  ),
                Text(t.icon, style: const TextStyle(fontSize: 16)),
                if (!collapsed) ...[
                  const SizedBox(width: 11),
                  Expanded(
                    child: Text(
                      t.label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: on ? FontWeight.w700 : FontWeight.w600,
                        color: on ? AppColors.text : AppColors.dim,
                      ),
                    ),
                  ),
                  if (badge != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        color: on ? AppColors.emerald.withValues(alpha: .18) : AppColors.surface3,
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(badge,
                          style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w800,
                              color: on ? AppColors.greenText : AppColors.dim)),
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  String? _badgeFor(String id, AppState state) {
    switch (id) {
      case 'habits':
        final n = (state.overview?['habit_total'] ?? 0).toString();
        return n;
      case 'study':
        return 'UPSC';
      case 'goals':
        return '${(state.stats?['objectives'] as List? ?? []).length}';
      default:
        return null;
    }
  }
}

// ---------------------------------------------------------------------------
// Header Sync button — cloud icon with a badge when writes are waiting.
// ---------------------------------------------------------------------------
class _SyncButton extends StatelessWidget {
  const _SyncButton({required this.state});
  final AppState state;

  @override
  Widget build(BuildContext context) {
    final pending = OfflineStore.length;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Builder(
          builder: (ctx) => Tooltip(
            message: pending == 0
                ? 'Sync with server'
                : 'Sync — $pending change${pending == 1 ? '' : 's'} waiting',
            child: IcoBtn(
              pending == 0 ? Icons.cloud_sync_outlined : Icons.cloud_upload_outlined,
              tint: pending == 0 ? null : AppColors.amber,
              onTap: () async {
                if (pending == 0) {
                  // Nothing queued: a lightweight refresh is what the user
                  // actually wants, and it avoids an empty Sync page.
                  await state.loadAll();
                  await state.loadStats();
                  await state.loadDashboard();
                  if (ctx.mounted) {
                    ScaffoldMessenger.of(ctx).showSnackBar(
                      const SnackBar(
                        content: Text('Refreshed from server'),
                        duration: Duration(seconds: 1),
                      ),
                    );
                  }
                } else {
                  await Navigator.of(ctx).push(
                    MaterialPageRoute(builder: (_) => const SyncScreen()),
                  );
                }
              },
            ),
          ),
        ),
        if (pending > 0)
          Positioned(
            right: -2,
            top: -2,
            child: IgnorePointer(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: AppColors.amber,
                  borderRadius: BorderRadius.circular(9),
                ),
                constraints: const BoxConstraints(minWidth: 16),
                child: Text(
                  pending > 99 ? '99+' : '$pending',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 9,
                    fontWeight: FontWeight.w900,
                    color: Colors.black,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Header countdown pill — `.countdown`.
// ---------------------------------------------------------------------------
class _Countdown extends StatelessWidget {
  final int daysLeft;
  const _Countdown({required this.daysLeft});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 6),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            AppColors.violet.withValues(alpha: .16),
            AppColors.blue.withValues(alpha: .16),
          ],
        ),
        borderRadius: BorderRadius.circular(11),
        border: Border.all(color: AppColors.violet.withValues(alpha: .35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('$daysLeft',
              style: const TextStyle(
                  fontSize: 22, fontWeight: FontWeight.w900, height: 1, color: AppColors.violetText)),
          const SizedBox(width: 10),
          const Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('DAYS LEFT',
                  style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      letterSpacing: .4,
                      color: Color(0xFFE9D5FF))),
              Text('until 1 May 2027',
                  style: TextStyle(fontSize: 10.5, color: AppColors.dim)),
            ],
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Right rail — `.rail`, per-tab content.
// ---------------------------------------------------------------------------
class _Rail extends StatelessWidget {
  final String tab;
  final void Function(String) onGo;
  const _Rail({required this.tab, required this.onGo});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF0D111E),
        border: Border(left: BorderSide(color: AppColors.border)),
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(14, 16, 14, 20),
        child: switch (tab) {
          'food' => const _FoodRail(),
          'notes' => const _NotesRail(),
          'fitness' => const _FitnessRail(),
          _ => _DayRail(onGo: onGo),
        },
      ),
    );
  }
}

class _DayRail extends StatelessWidget {
  final void Function(String) onGo;
  const _DayRail({required this.onGo});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final o = state.overview;
    final dash = state.dashboard;
    final total = asInt(o?['habit_total']);
    final done = asInt(o?['done_today']);
    final pct = total == 0 ? 0 : (done / total * 100).round();
    final remaining = total - done;
    final ringColor = pct >= 100
        ? AppColors.emerald
        : pct >= 50
            ? AppColors.blue
            : AppColors.amber;

    final atRisk = (dash?['at_risk'] as List? ?? []);
    final focus = dash?['focus'] as Map?;
    final burnout = dash?['burnout'] as Map?;
    final recovery = dash?['recovery'] as Map?;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        MockCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  ScoreRing(pct, size: 64, stroke: 6, color: ringColor),
                  const SizedBox(width: 13),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Cap('Day score'),
                        const SizedBox(height: 3),
                        Text.rich(
                          TextSpan(children: [
                            TextSpan(
                                text: '$done',
                                style: const TextStyle(fontSize: 34, fontWeight: FontWeight.w900)),
                            TextSpan(
                                text: '/$total',
                                style: const TextStyle(fontSize: 17, color: AppColors.dim)),
                          ]),
                        ),
                        Text(remaining > 0 ? '$remaining to go' : '🎉 perfect day',
                            style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              ProgressBar(value: pct / 100, color: ringColor),
            ],
          ),
        ),
        const _RailSec('Needs attention'),
        if (atRisk.isEmpty && focus == null && burnout == null)
          const _Tile(k: '🔥 Streak at risk', v: 'None', vColor: AppColors.greenText, s: 'every streak is safe today')
        else ...[
          for (final a in atRisk.take(1))
            _Tile(
              k: '🔥 Streak at risk',
              v: '${asInt((a as Map)['streak'])} days',
              vColor: AppColors.orange,
              s: '${a['name']} · not done yet',
            ),
          if (focus != null)
            _Tile(
              k: '🎯 Focus next',
              v: (focus['name'] ?? '').toString(),
              vColor: AppColors.blueText,
              s: 'lowest momentum at ${asInt(focus['momentum'])}%',
            ),
          if (burnout != null)
            _Tile(
              k: '🫀 Burnout load',
              v: (burnout['level'] ?? '').toString().toUpperCase(),
              vColor: burnout['level'] == 'high' ? AppColors.roseText : AppColors.greenText,
              s: 'recovery ${asInt(recovery?['rate'])}%',
            ),
        ],
        const _RailSec('Quick log'),
        Row(
          children: [
            Expanded(child: SmBtn('📚 Study', onTap: () => onGo('study'))),
            const SizedBox(width: 7),
            Expanded(child: SmBtn('🏋️ Gym', onTap: () => onGo('fitness'))),
          ],
        ),
        const _RailSec('Top streaks'),
        for (final h in _topStreaks(state))
          Padding(
            padding: const EdgeInsets.only(bottom: 7),
            child: Row(
              children: [
                SizedBox(
                  width: 22,
                  child: Text((h['emoji'] ?? '').toString(), style: const TextStyle(fontSize: 13)),
                ),
                Expanded(
                  child: Text((h['name'] ?? '').toString(),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                ),
                const SizedBox(width: 8),
                SizedBox(
                  width: 70,
                  child: ProgressBar(
                    value: asDouble(h['completion_30d']) / 100,
                    color: hexColor(h['color'] as String?),
                    height: 5,
                  ),
                ),
                const SizedBox(width: 7),
                SizedBox(
                  width: 34,
                  child: Text('🔥 ${asInt(h['streak'])}',
                      textAlign: TextAlign.right,
                      style: const TextStyle(
                          fontSize: 10.5, color: AppColors.orange, fontWeight: FontWeight.w800)),
                ),
              ],
            ),
          ),
      ],
    );
  }

  List<Map<String, dynamic>> _topStreaks(AppState state) {
    final habits = List<Map<String, dynamic>>.from(
      (state.overview?['habits'] as List? ?? []).map((h) => Map<String, dynamic>.from(h as Map)),
    );
    habits.sort((a, b) => asInt(b['streak']).compareTo(asInt(a['streak'])));
    return habits.take(3).toList();
  }
}

class _FoodRail extends StatelessWidget {
  const _FoodRail();

  @override
  Widget build(BuildContext context) {
    // The Food screen owns its own data; this rail reports the day's diary roll-up.
    final state = context.watch<AppState>();
    final d = state.diaryTotals;
    final goal = asDouble(state.settingValue('fit_daily_calorie', '2100'), 2100);
    final rem = goal - d.kcal;
    final over = rem < 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        MockCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Cap('Calories today'),
              const SizedBox(height: 4),
              Text('${rem.abs().round()}',
                  style: TextStyle(
                      fontSize: 34,
                      fontWeight: FontWeight.w900,
                      height: 1,
                      color: over ? AppColors.danger : AppColors.emerald)),
              const SizedBox(height: 4),
              Text('${over ? 'over goal' : 'remaining'} of ${goal.round()} kcal',
                  style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
              const SizedBox(height: 12),
              ProgressBar(
                value: goal == 0 ? 0 : (d.kcal / goal).clamp(0.0, 1.0),
                color: over ? AppColors.danger : AppColors.emerald,
              ),
              const SizedBox(height: 7),
              Text('${d.kcal.round()} eaten · ${d.items} items',
                  style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
            ],
          ),
        ),
        const _RailSec('Macros'),
        _MacroRow('Protein', d.protein, asDouble(state.settingValue('macro_protein', '140'), 140),
            AppColors.blue),
        _MacroRow('Carbs', d.carbs, asDouble(state.settingValue('macro_carbs', '210'), 210),
            AppColors.amber),
        _MacroRow('Fat', d.fat, asDouble(state.settingValue('macro_fat', '60'), 60),
            AppColors.violet),
      ],
    );
  }
}

class _MacroRow extends StatelessWidget {
  final String label;
  final double value;
  final double goal;
  final Color color;
  const _MacroRow(this.label, this.value, this.goal, this.color);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Row(
        children: [
          SizedBox(
            width: 64,
            child: Text(label, style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
          ),
          Expanded(
            child: ProgressBar(
              value: goal == 0 ? 0 : (value / goal).clamp(0.0, 1.0),
              color: color,
              height: 6,
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 58,
            child: Text.rich(
              TextSpan(children: [
                TextSpan(
                    text: '${value.round()}',
                    style: const TextStyle(fontWeight: FontWeight.w800, color: AppColors.text)),
                TextSpan(text: '/${goal.round()}g', style: const TextStyle(color: AppColors.faint)),
              ]),
              textAlign: TextAlign.right,
              style: const TextStyle(fontSize: 11),
            ),
          ),
        ],
      ),
    );
  }
}

class _NotesRail extends StatelessWidget {
  const _NotesRail();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final counts = state.noteCounts;
    final total = counts.values.fold<int>(0, (a, b) => a + b);
    final pinned = state.pinnedNote;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        MockCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Cap('Total notes'),
              const SizedBox(height: 4),
              Text('$total',
                  style: const TextStyle(fontSize: 34, fontWeight: FontWeight.w900, height: 1)),
              const SizedBox(height: 4),
              Text('across ${counts.length} categories',
                  style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
            ],
          ),
        ),
        const _RailSec('By category'),
        for (final e in (counts.entries.toList()..sort((a, b) => b.value.compareTo(a.value))))
          _Tile(k: e.key, v: '${e.value}'),
        if (pinned != null) ...[
          const _RailSec('Pinned'),
          _Tile(
            k: '📌 pinned',
            v: (pinned['text'] ?? '').toString().length > 40
                ? '${(pinned['text'] as String).substring(0, 40)}…'
                : (pinned['text'] ?? '').toString(),
            s: (pinned['date'] ?? '').toString(),
          ),
        ],
      ],
    );
  }
}

class _FitnessRail extends StatelessWidget {
  const _FitnessRail();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final muscle = state.muscleFatigue;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        MockCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Cap('Weekly volume'),
              const SizedBox(height: 4),
              Text.rich(
                TextSpan(children: [
                  TextSpan(
                      text: fmtNum(state.weeklyVolumeKg),
                      style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w900, height: 1)),
                  const TextSpan(
                      text: ' kg', style: TextStyle(fontSize: 14, color: AppColors.dim)),
                ]),
              ),
              const SizedBox(height: 4),
              Text('${state.exerciseCount} exercises in the library',
                  style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
            ],
          ),
        ),
        const _RailSec('Muscle fatigue'),
        if (muscle.isEmpty)
          const _Tile(k: 'No data', v: '—', s: 'log a workout to see this')
        else
          for (final m in (muscle.entries.toList()
            ..sort((a, b) => asDouble(b.value).compareTo(asDouble(a.value)))).take(8))
            SizedBox(
              height: 22,
              child: Row(
                children: [
                  SizedBox(
                    width: 84,
                    child: Text(m.key,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                  ),
                  Expanded(
                    child: ProgressBar(
                      value: (asDouble(m.value) / 100).clamp(0.0, 1.0),
                      color: asDouble(m.value) >= 70
                          ? AppColors.danger
                          : asDouble(m.value) >= 40
                              ? AppColors.amber
                              : AppColors.blue,
                      height: 6,
                    ),
                  ),
                  const SizedBox(width: 7),
                  SizedBox(
                    width: 34,
                    child: Text('${asDouble(m.value).round()}%',
                        textAlign: TextAlign.right,
                        style: const TextStyle(fontSize: 10.5, color: AppColors.dim)),
                  ),
                ],
              ),
            ),
      ],
    );
  }
}

class _RailSec extends StatelessWidget {
  final String text;
  const _RailSec(this.text);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(2, 16, 2, 8),
        child: Text(text.toUpperCase(),
            style: const TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: 1,
                color: AppColors.faint)),
      );
}

class _Tile extends StatelessWidget {
  final String k;
  final String v;
  final String? s;
  final Color? vColor;
  const _Tile({required this.k, required this.v, this.s, this.vColor});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: MockCard(
        padding: const EdgeInsets.fromLTRB(11, 10, 11, 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Cap(k),
            const SizedBox(height: 3),
            Text(v,
                style: TextStyle(
                    fontSize: 15, fontWeight: FontWeight.w900, color: vColor ?? AppColors.text)),
            if (s != null) ...[
              const SizedBox(height: 1),
              Text(s!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 11, color: AppColors.dim)),
            ],
          ],
        ),
      ),
    );
  }
}
