import 'package:flutter_test/flutter_test.dart';
import 'package:mission_app/api.dart';
import 'package:mission_app/offline.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// These tests target the failure modes that would cause silent data loss:
/// a queue that forgets items, dedupe that eats distinct events, and a drain
/// that stops or loops forever.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await OfflineStore.load();
    await OfflineStore.clear();
  });

  test('a queued write survives a reload (durability)', () async {
    await OfflineStore.queueWrite(
      id: 'habit-1-2026-10-21',
      method: 'POST',
      path: 'habits/toggle/',
      body: {'habit': 1, 'date': '2026-10-21', 'status': 'done'},
      label: 'Habit · done',
    );
    expect(OfflineStore.length, 1);

    // Simulate an app restart: forget in-memory state, reload from disk.
    await OfflineStore.load();
    expect(OfflineStore.length, 1, reason: 'queue must persist across restarts');
    expect(OfflineStore.queue.first.label, 'Habit · done');
    expect(OfflineStore.queue.first.method, 'POST');
  });

  test('re-toggling the same habit replaces, not stacks', () async {
    // The user taps a habit three times offline; only the final state matters.
    for (final status in ['done', 'skipped', 'pending']) {
      await OfflineStore.queueWrite(
        id: 'habit-1-2026-10-21',
        method: 'POST',
        path: 'habits/toggle/',
        body: {'habit': 1, 'date': '2026-10-21', 'status': status},
        label: 'Habit · $status',
      );
    }
    expect(OfflineStore.length, 1, reason: 'same habit/day must collapse to one op');
    expect(OfflineStore.queue.first.body!['status'], 'pending',
        reason: 'the LAST tap wins');
  });

  test('distinct drinks are all kept (no accidental dedupe)', () async {
    for (var i = 0; i < 3; i++) {
      await OfflineStore.queueWrite(
        id: 'drink-$i',
        method: 'POST',
        path: 'drinks/',
        body: {'drink_type': 'water', 'volume_ml': 250, 'date': '2026-10-21'},
        label: 'Water 250ml',
      );
    }
    expect(OfflineStore.length, 3, reason: 'two glasses of water are two events');
  });

  test('queue order is preserved (FIFO)', () async {
    for (final n in ['a', 'b', 'c']) {
      await OfflineStore.queueWrite(
        id: 'op-$n', method: 'POST', path: 'x/', body: {'v': n}, label: n);
    }
    expect(OfflineStore.queue.map((e) => e.label).toList(), ['a', 'b', 'c']);
  });

  test('remove takes exactly one op out', () async {
    await OfflineStore.queueWrite(id: 'one', method: 'POST', path: 'x/', label: 'one');
    await OfflineStore.queueWrite(id: 'two', method: 'POST', path: 'x/', label: 'two');
    await OfflineStore.remove(OfflineStore.queue.first);
    expect(OfflineStore.length, 1);
    expect(OfflineStore.queue.first.label, 'two');
  });

  test('a corrupt queue does not brick startup', () async {
    SharedPreferences.setMockInitialValues({'offline_queue_v1': 'not-json{{{'});
    await OfflineStore.load();
    expect(OfflineStore.length, 0, reason: 'bad data must be dropped, not thrown');
  });

  test('PendingOp round-trips through JSON', () {
    final op = PendingOp(
      id: 'x', method: 'PATCH', path: 'fitness/2026-10-21/',
      body: {'steps': 8000}, query: {'a': 'b'},
      at: DateTime.parse('2026-10-21T10:00:00'), label: 'Steps',
    );
    final back = PendingOp.fromJson(op.toJson());
    expect(back.id, op.id);
    expect(back.method, op.method);
    expect(back.path, op.path);
    expect(back.body, op.body);
    expect(back.query, op.query);
    expect(back.at, op.at);
    expect(back.label, op.label);
  });

  test('SyncReport summarises honestly', () {
    expect(SyncReport(pushed: 0, failed: 0, stillQueued: 0).summary,
        'Already up to date');
    expect(SyncReport(pushed: 3, failed: 0, stillQueued: 0).summary, '3 pushed');
    expect(SyncReport(pushed: 2, failed: 1, stillQueued: 4).summary,
        '2 pushed · 1 failed · 4 still queued');
    expect(SyncReport(pushed: 0, failed: 0, stillQueued: 2, error: 'nope').ok, false);
  });

  test('alias + normalize still hold after the sync changes', () {
    expect(Api.normalizeBase('mission'), 'http://10.210.195.182:8000');
    expect(Api.normalizeBase('mission:8000/'), 'http://10.210.195.182:8000');
  });
}
