import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

/// One queued write that has not reached the server yet.
///
/// Every mutating request in the app is described by these five fields, which
/// is enough to replay it verbatim later. `id` is a locally-generated dedupe
/// key (so re-queueing the same logical change replaces the old one rather than
/// stacking up), and `at` is the wall-clock time of the edit — the server uses
/// it to decide the winner when the same record changed in both places.
class PendingOp {
  PendingOp({
    required this.id,
    required this.method,
    required this.path,
    this.body,
    this.query,
    required this.at,
    this.label = '',
  });

  final String id;
  final String method;
  final String path;
  final Map<String, dynamic>? body;
  final Map<String, String>? query;
  final DateTime at;

  /// Short human text for the Sync screen ("Habit toggle", "Weight 72.5kg").
  final String label;

  Map<String, dynamic> toJson() => {
        'id': id,
        'method': method,
        'path': path,
        'body': body,
        'query': query,
        'at': at.toIso8601String(),
        'label': label,
      };

  static PendingOp fromJson(Map<String, dynamic> j) => PendingOp(
        id: j['id'] as String,
        method: j['method'] as String,
        path: j['path'] as String,
        body: j['body'] == null
            ? null
            : Map<String, dynamic>.from(j['body'] as Map),
        query: j['query'] == null
            ? null
            : Map<String, String>.from(j['query'] as Map),
        at: DateTime.tryParse(j['at'] as String? ?? '') ?? DateTime.now(),
        label: (j['label'] ?? '').toString(),
      );
}

/// Durable queue of writes made while the server was unreachable.
///
/// Backed by [SharedPreferences] as a JSON list: the payloads are small and the
/// queue is short-lived (it drains on the next successful Sync), so a full
/// SQLite database would be far more machinery than this needs.
///
/// Ordering matters — a PATCH to a row cannot run before the POST that created
/// it — so the queue is strictly FIFO and drain stops at the first hard failure.
class OfflineStore {
  static const String _key = 'offline_queue_v1';
  static const String _syncedKey = 'last_sync_at';

  static List<PendingOp> _queue = [];
  static DateTime? lastSyncAt;
  static bool _loaded = false;

  static List<PendingOp> get queue => List.unmodifiable(_queue);
  static int get length => _queue.length;
  static bool get isEmpty => _queue.isEmpty;

  static Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    _queue = [];
    if (raw != null && raw.isNotEmpty) {
      try {
        final list = jsonDecode(raw) as List;
        _queue = list
            .map((e) => PendingOp.fromJson(Map<String, dynamic>.from(e as Map)))
            .toList();
      } catch (_) {
        // A corrupt queue must never brick startup; drop it and carry on.
        _queue = [];
      }
    }
    final ts = prefs.getString(_syncedKey);
    lastSyncAt = ts == null ? null : DateTime.tryParse(ts);
    _loaded = true;
  }

  static Future<void> _persist() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(_queue.map((e) => e.toJson()).toList()));
  }

  static Future<void> _markSynced() async {
    lastSyncAt = DateTime.now();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_syncedKey, lastSyncAt!.toIso8601String());
  }

  /// Queue a write. If an operation with the same [id] is already waiting, it is
  /// replaced — pressing a habit twice offline should leave one pending toggle,
  /// not two that cancel out on the server.
  static Future<void> enqueue(PendingOp op, {bool dedupe = true}) async {
    if (!_loaded) await load();
    if (dedupe) {
      _queue.removeWhere((e) => e.id == op.id);
    }
    _queue.add(op);
    await _persist();
    notify?.call();
  }

  /// Convenience wrapper for the common "POST/PATCH/DELETE this path" case.
  static Future<void> queueWrite({
    required String id,
    required String method,
    required String path,
    Map<String, dynamic>? body,
    Map<String, String>? query,
    String label = '',
    bool dedupe = true,
  }) =>
      enqueue(
        PendingOp(
          id: id,
          method: method,
          path: path,
          body: body,
          query: query,
          at: DateTime.now(),
          label: label,
        ),
        dedupe: dedupe,
      );

  static Future<void> remove(PendingOp op) async {
    _queue.removeWhere((e) => e.id == op.id);
    await _persist();
    notify?.call();
  }

  static Future<void> clear() async {
    _queue = [];
    await _persist();
    notify?.call();
  }

  static Future<void> markSynced() async {
    await _markSynced();
    notify?.call();
  }

  /// Called after any change so the UI (badge, Sync page) can rebuild.
  static VoidCallback? notify;
}

/// Result of one Sync press — shown to the user so "Synced" is never a lie.
class SyncReport {
  SyncReport({
    required this.pushed,
    required this.failed,
    required this.stillQueued,
    this.error,
  });

  final int pushed;
  final int failed;
  final int stillQueued;
  final String? error;

  bool get ok => failed == 0 && error == null;
  bool get nothingToDo => pushed == 0 && failed == 0 && stillQueued == 0;

  String get summary {
    if (error != null) return error!;
    if (nothingToDo) return 'Already up to date';
    final bits = <String>[];
    if (pushed > 0) bits.add('$pushed pushed');
    if (failed > 0) bits.add('$failed failed');
    if (stillQueued > 0) bits.add('$stillQueued still queued');
    return bits.join(' · ');
  }
}

/// Push local changes up, then let the caller refresh from the server.
///
/// Deliberately *sequential*: the queue is ordered, and a PATCH must not run
/// before the POST that created its row. On the first transport failure we stop
/// rather than skipping ahead, because a later op may depend on an earlier one.
/// HTTP errors (the server rejected the row) are different: those are dropped,
/// since retrying them forever would wedge the queue permanently.
class SyncEngine {
  /// Replay the queue. [onProgress] fires after each item for live UI.
  static Future<SyncReport> push({
    void Function(int done, int total, String label)? onProgress,
  }) async {
    if (!OfflineStore._loaded) await OfflineStore.load();
    final ops = OfflineStore.queue;
    if (ops.isEmpty) {
      await OfflineStore.markSynced();
      return SyncReport(pushed: 0, failed: 0, stillQueued: 0);
    }
    var pushed = 0;
    var failed = 0;
    String? transportError;

    for (var i = 0; i < ops.length; i++) {
      final op = ops[i];
      onProgress?.call(i, ops.length, op.label);
      try {
        await Api.replay(op);
        await OfflineStore.remove(op);
        pushed++;
      } catch (e) {
        final msg = e.toString();
        // A 4xx/5xx means the server refused it — dropping keeps the queue
        // drainable. A transport error means "try again later", so stop.
        final isHttp = RegExp(r'-> \d{3}').hasMatch(msg);
        if (isHttp) {
          await OfflineStore.remove(op);
          failed++;
        } else {
          transportError = msg;
          break;
        }
      }
    }

    final remaining = OfflineStore.length;
    if (transportError == null) {
      await OfflineStore.markSynced();
    }
    return SyncReport(
      pushed: pushed,
      failed: failed,
      stillQueued: remaining,
      error: transportError == null
          ? null
          : 'Server unreachable — $transportError',
    );
  }
}
