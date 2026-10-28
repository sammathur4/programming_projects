import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../offline.dart';
import '../state.dart';
import '../theme.dart';

/// The Sync screen: shows what is waiting to reach the server, then pushes it
/// up and refreshes from the server.
///
/// This is the user-facing half of the offline feature. The point is that
/// "Synced" is never a guess — the list below is the real queue, and after a
/// push the counts come from what actually succeeded.
class SyncScreen extends StatefulWidget {
  const SyncScreen({super.key});

  @override
  State<SyncScreen> createState() => _SyncScreenState();
}

class _SyncScreenState extends State<SyncScreen> {
  SyncReport? _report;

  @override
  void initState() {
    super.initState();
    OfflineStore.notify = () {
      if (mounted) setState(() {});
    };
  }

  @override
  void dispose() {
    OfflineStore.notify = null;
    super.dispose();
  }

  Future<void> _sync() async {
    final state = context.read<AppState>();
    final report = await state.sync(
      onProgress: (done, total, label) {
        if (mounted) setState(() {});
      },
    );
    if (!mounted) return;
    setState(() => _report = report);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(report.ok
            ? (report.nothingToDo ? 'Already up to date' : 'Synced · ${report.summary}')
            : report.summary),
        backgroundColor: report.ok ? null : AppColors.surface,
      ),
    );
  }

  Future<void> _clearQueue() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Discard queued changes?'),
        content: const Text(
            'These changes were made offline and have not reached the server. '
            'Discarding them cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: AppColors.danger),
            child: const Text('Discard'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    await OfflineStore.clear();
    if (!mounted) return;
    setState(() => _report = null);
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final queue = OfflineStore.queue;
    final last = OfflineStore.lastSyncAt;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Sync'),
        actions: [
          if (queue.isNotEmpty)
            IconButton(
              tooltip: 'Discard queued changes',
              onPressed: state.syncing ? null : _clearQueue,
              icon: const Icon(Icons.delete_outline),
            ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ---------------- status card
          Card(
            color: AppColors.surface,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        queue.isEmpty ? Icons.cloud_done_outlined : Icons.cloud_upload_outlined,
                        color: queue.isEmpty ? AppColors.mint : AppColors.amber,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          queue.isEmpty
                              ? 'Everything is on the server'
                              : '${queue.length} change${queue.length == 1 ? '' : 's'} waiting',
                          style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Server: ${Api.base}',
                    style: const TextStyle(fontSize: 12, color: AppColors.dim),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    last == null
                        ? 'Never synced'
                        : 'Last synced ${_ago(last)}',
                    style: const TextStyle(fontSize: 12, color: AppColors.dim),
                  ),
                  const SizedBox(height: 14),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: state.syncing ? null : _sync,
                      icon: state.syncing
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.sync),
                      label: Text(state.syncing ? 'Syncing…' : 'Sync now'),
                    ),
                  ),
                  if (state.syncing && state.syncLabel.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(state.syncLabel,
                        style: const TextStyle(fontSize: 12, color: AppColors.dim)),
                  ],
                ],
              ),
            ),
          ),

          // ---------------- last result
          if (_report != null) ...[
            const SizedBox(height: 12),
            Card(
              color: AppColors.surface,
              child: ListTile(
                leading: Icon(
                  _report!.ok ? Icons.check_circle_outline : Icons.error_outline,
                  color: _report!.ok ? AppColors.mint : AppColors.danger,
                ),
                title: Text(_report!.summary),
                subtitle: Text(
                  '${_report!.pushed} pushed · ${_report!.failed} rejected · '
                  '${_report!.stillQueued} remaining',
                  style: const TextStyle(fontSize: 12),
                ),
              ),
            ),
          ],

          const SizedBox(height: 18),

          // ---------------- the queue itself
          if (queue.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(
                child: Text(
                  'Nothing waiting to sync.\nChanges you make offline appear here.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.dim, fontSize: 13, height: 1.5),
                ),
              ),
            )
          else ...[
            SectionLabel('Waiting to upload (${queue.length})',
                icon: Icons.pending_actions_outlined),
            const SizedBox(height: 6),
            ...queue.map((op) => Card(
                  color: AppColors.surface,
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    dense: true,
                    leading: Icon(_methodIcon(op.method), size: 18, color: AppColors.dim),
                    title: Text(op.label, style: const TextStyle(fontSize: 13)),
                    subtitle: Text(
                      '${_ago(op.at)} · ${op.method} ${op.path}',
                      style: const TextStyle(fontSize: 11, color: AppColors.faint),
                    ),
                  ),
                )),
          ],
        ],
      ),
    );
  }

  static IconData _methodIcon(String m) => switch (m) {
        'POST' => Icons.add_circle_outline,
        'PATCH' => Icons.edit_outlined,
        'DELETE' => Icons.delete_outline,
        _ => Icons.circle_outlined,
      };

  /// "just now", "4 min ago", "2 h ago", "3 d ago".
  static String _ago(DateTime t) {
    final d = DateTime.now().difference(t);
    if (d.inSeconds < 45) return 'just now';
    if (d.inMinutes < 60) return '${d.inMinutes} min ago';
    if (d.inHours < 24) return '${d.inHours} h ago';
    return '${d.inDays} d ago';
  }
}
