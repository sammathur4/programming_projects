import 'package:flutter_test/flutter_test.dart';
import 'package:mission_app/state.dart';

/// The Today tracker must support four statuses: pending, in progress, done
/// and skipped — and the counters must never disagree with the rows.
///
/// These exercise the optimistic layer directly. Going through the network
/// path in a test would only prove that a stubbed HTTP 400 triggers a revert.
void main() {
  AppState buildState() {
    final s = AppState();
    s.loading = false;
    s.overview = {
      'date': '2026-10-21',
      'daily_score': 0,
      'done_today': 0,
      'skipped_today': 0,
      'in_progress_today': 0,
      'habit_total': 3,
      'habits': [
        {'id': 1, 'name': 'A', 'status_today': '', 'done_today': false},
        {'id': 2, 'name': 'B', 'status_today': '', 'done_today': false},
        {'id': 3, 'name': 'C', 'status_today': '', 'done_today': false},
      ],
    };
    return s;
  }

  Map<String, dynamic> row(AppState s, int i) =>
      (s.overview!['habits'] as List)[i] as Map<String, dynamic>;

  test('the four statuses are the ones the server accepts', () {
    expect(AppState.habitStatuses,
        containsAll(['pending', 'in_progress', 'done', 'skipped']));
    expect(AppState.habitStatuses.length, 4);
  });

  test('in_progress is shown and counted separately from done', () {
    final s = buildState();
    s.applyStatusLocally(1, 'in_progress');
    expect(row(s, 0)['status_today'], 'in_progress');
    expect(row(s, 0)['done_today'], isFalse);
    expect(s.overview!['in_progress_today'], 1);
    expect(s.overview!['done_today'], 0);
  });

  test('done, in_progress and skipped are three separate counters', () {
    final s = buildState();
    s.applyStatusLocally(1, 'done');
    s.applyStatusLocally(2, 'in_progress');
    s.applyStatusLocally(3, 'skipped');
    expect(s.overview!['done_today'], 1);
    expect(s.overview!['in_progress_today'], 1);
    expect(s.overview!['skipped_today'], 1);
    expect(s.overview!['daily_score'], 33); // 1 of 3
  });

  test('moving a habit from in_progress to done moves the counters', () {
    final s = buildState();
    s.applyStatusLocally(1, 'in_progress');
    expect(s.overview!['in_progress_today'], 1);
    s.applyStatusLocally(1, 'done');
    expect(s.overview!['in_progress_today'], 0);
    expect(s.overview!['done_today'], 1);
  });

  test('the counters always match the rows', () {
    final s = buildState();
    s.applyStatusLocally(1, 'done');
    s.applyStatusLocally(2, 'done');
    s.applyStatusLocally(3, 'in_progress');
    final rows = (s.overview!['habits'] as List).cast<Map<String, dynamic>>();
    final done = rows.where((h) => h['status_today'] == 'done').length;
    final inProg = rows.where((h) => h['status_today'] == 'in_progress').length;
    expect(s.overview!['done_today'], done);
    expect(s.overview!['in_progress_today'], inProg);
  });

  test('the revert closure restores the previous state', () {
    final s = buildState();
    s.applyStatusLocally(1, 'done');
    final revert = s.applyStatusLocally(1, 'in_progress');
    expect(s.overview!['in_progress_today'], 1);
    revert!();
    expect(row(s, 0)['status_today'], 'done');
    expect(row(s, 0)['done_today'], isTrue);
    expect(s.overview!['done_today'], 1);
    expect(s.overview!['in_progress_today'], 0);
  });

  test('an unknown habit id is a no-op', () {
    final s = buildState();
    expect(s.applyStatusLocally(999, 'in_progress'), isNull);
    expect(s.overview!['in_progress_today'], 0);
  });
}
