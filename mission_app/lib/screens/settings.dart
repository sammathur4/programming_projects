import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api.dart';
import '../offline.dart';
import '../state.dart';
import '../theme.dart';
import 'data_management.dart';
import 'sync.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _url;
  late final TextEditingController _vision;
  late final TextEditingController _height;
  late final TextEditingController _goalWeight;
  late final TextEditingController _birthYear;
  String _status = '';
  bool _testing = false;

  @override
  void initState() {
    super.initState();
    _url = TextEditingController(text: Api.base);
    _vision = TextEditingController(text: context.read<AppState>().visionBoardUrl ?? '');
    final state = context.read<AppState>();
    _height = TextEditingController(text: state.settingValue('height_cm', ''));
    _goalWeight = TextEditingController(text: state.settingValue('goal_weight_kg', ''));
    _birthYear = TextEditingController(text: state.settingValue('birth_year', ''));
    state.loadVisionBoardOverride().then((_) {
      if (mounted) {
        setState(() => _vision.text = context.read<AppState>().visionBoardUrl ?? '');
      }
    });
    state.loadAll().then((_) {
      if (!mounted) return;
      setState(() {
        _height.text = state.settingValue('height_cm', '');
        _goalWeight.text = state.settingValue('goal_weight_kg', '');
        _birthYear.text = state.settingValue('birth_year', '');
      });
    });
  }

  @override
  void dispose() {
    _url.dispose();
    _vision.dispose();
    _height.dispose();
    _goalWeight.dispose();
    _birthYear.dispose();
    super.dispose();
  }

  void _openSync() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const SyncScreen()),
    );
  }

  /// Forget the saved server URL and let the app detect it again.
  ///
  /// On web that means the page's own origin; on a phone it means the
  /// built-in `mission` alias.
  Future<void> _resetUrl() async {
    setState(() {
      _testing = true;
      _status = '';
    });
    await Api.setOverride('');
    await Api.init();
    final state = context.read<AppState>();
    try {
      await Api.checkConnectivity();
      await state.loadAll();
      if (!mounted) return;
      setState(() {
        _url.text = Api.base;
        _status = 'Connected ✓  (${Api.base})';
      });
    } catch (e) {
      if (!mounted) return;
      final msg = e.toString().trim();
      setState(() => _status = msg.isEmpty
          ? 'Failed at ${Api.base} — no error detail'
          : 'Failed at ${Api.base} — $msg');
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  Future<void> _test() async {
    setState(() {
      _testing = true;
      _status = '';
    });
    final appState = context.read<AppState>();
    await Api.setOverride(_url.text);
    try {
      await Api.checkConnectivity();
      await appState.loadAll();
      if (!mounted) return;
      setState(() => _status = 'Connected ✓  (${Api.base})');
    } catch (e) {
      if (!mounted) return;
      final msg = e.toString().trim();
      setState(() => _status = msg.isEmpty
          ? 'Failed at ${Api.base} — no error detail (unknown ${e.runtimeType})'
          : 'Failed at ${Api.base} — $msg');
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  Future<void> _saveVision() async {
    final state = context.read<AppState>();
    await state.saveVisionBoardOverride(_vision.text);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(_vision.text.trim().isEmpty
            ? 'Vision board reset to the hosted default'
            : 'Vision board URL saved'),
      ),
    );
  }

  /// Persist the weight-tracker profile (BMI inputs) as Settings keys.
  Future<void> _saveBodyProfile() async {
    final state = context.read<AppState>();
    final entries = {
      'height_cm': _height.text.trim(),
      'goal_weight_kg': _goalWeight.text.trim(),
      'birth_year': _birthYear.text.trim(),
    };
    try {
      for (final e in entries.entries) {
        if (e.value.isEmpty) continue;
        await Api.send('POST', 'settings/', {'key': e.key, 'value': e.value},
            label: 'Setting · ${e.key}', dedupeId: 'setting-${e.key}');
      }
      await state.loadAll();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Body profile saved')),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Sync lives here too, so the queue is reachable from Settings even
          // when the app bar is crowded.
          Card(
            color: AppColors.surface,
            margin: const EdgeInsets.only(bottom: 14),
            child: ListTile(
              leading: Stack(
                clipBehavior: Clip.none,
                children: [
                  const Icon(Icons.cloud_sync_outlined),
                  if (OfflineStore.length > 0)
                    Positioned(
                      right: -4,
                      top: -4,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                        decoration: BoxDecoration(
                          color: AppColors.amber,
                          borderRadius: BorderRadius.circular(9),
                        ),
                        child: Text(
                          '${OfflineStore.length}',
                          style: const TextStyle(
                              fontSize: 9, fontWeight: FontWeight.w900, color: Colors.black),
                        ),
                      ),
                    ),
                ],
              ),
              title: const Text('Sync'),
              subtitle: Text(
                OfflineStore.length == 0
                    ? 'All changes are on the server'
                    : '${OfflineStore.length} change${OfflineStore.length == 1 ? '' : 's'} waiting to upload',
                style: const TextStyle(fontSize: 12),
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: _openSync,
            ),
          ),
          const SectionLabel('Backend server', icon: Icons.dns_outlined),
          const Text(
            'Tip: type "mission" or "mission:8000" — it is built in and resolves '
            'to your computer automatically. On the Android emulator use '
            '10.0.2.2; on a real phone over Wi-Fi use your computer\'s LAN IP, '
            'e.g. http://192.168.1.5:8000',
            style: TextStyle(fontSize: 12, color: AppColors.dim, height: 1.4),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _url,
            keyboardType: TextInputType.url,
            decoration: const InputDecoration(
              labelText: 'Server URL',
              hintText: 'http://mission:8000',
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              FilledButton.icon(
                onPressed: _testing ? null : _test,
                icon: _testing
                    ? const SizedBox(
                        width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.wifi_tethering, size: 18),
                label: const Text('Save & test'),
              ),
              const SizedBox(width: 10),
              // A wrong URL must never be a dead end — this clears the saved
              // override and goes back to the automatic detection.
              TextButton.icon(
                onPressed: _testing ? null : _resetUrl,
                icon: const Icon(Icons.restart_alt, size: 18),
                label: const Text('Auto'),
              ),
            ],
          ),
          if (_status.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text(
                _status,
                style: TextStyle(
                  color: _status.startsWith('Connected') ? AppColors.mint : AppColors.rose,
                  fontSize: 13,
                ),
              ),
            ),
          const SizedBox(height: 26),
          const SectionLabel('Body profile', icon: Icons.monitor_weight_outlined),
          const Text(
            'Used by the weight tracker for BMI, your healthy-weight range and goal '
            'progress. Height is required for BMI.',
            style: TextStyle(fontSize: 12, color: AppColors.dim, height: 1.4),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _height,
                  decoration: const InputDecoration(labelText: 'Height (cm)', isDense: true),
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _goalWeight,
                  decoration: const InputDecoration(labelText: 'Goal weight (kg)', isDense: true),
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          TextField(
            controller: _birthYear,
            decoration: const InputDecoration(labelText: 'Birth year', isDense: true),
            keyboardType: TextInputType.number,
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              FilledButton.icon(
                onPressed: _saveBodyProfile,
                icon: const Icon(Icons.save_outlined, size: 18),
                label: const Text('Save'),
              ),
            ],
          ),
          const SizedBox(height: 26),
          const SectionLabel('Vision board', icon: Icons.auto_awesome_outlined),
          const Text(
            'Leave empty to use the board hosted by your backend '
            '(<server>/vision-board/index.html). Paste any URL to override — '
            'including a file:// path if you run the app on the same machine.',
            style: TextStyle(fontSize: 12, color: AppColors.dim, height: 1.4),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _vision,
            keyboardType: TextInputType.url,
            maxLines: 2,
            minLines: 1,
            decoration: const InputDecoration(
              labelText: 'Vision board URL',
              hintText: 'file:///home/saksham/.../vision_board/index.html',
            ),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              FilledButton.icon(
                onPressed: _saveVision,
                icon: const Icon(Icons.save_outlined, size: 18),
                label: const Text('Save'),
              ),
              const SizedBox(width: 10),
              TextButton(
                onPressed: () {
                  _vision.clear();
                  _saveVision();
                },
                child: const Text('Reset to default'),
              ),
            ],
          ),
          const SizedBox(height: 26),
          const Divider(),
          const SizedBox(height: 14),
          const SectionLabel('Data management', icon: Icons.storage_outlined),
          const Text(
            'Back up your habits, logs, weights and study records to CSV, or '
            'restore them from a previous export.',
            style: TextStyle(fontSize: 12, color: AppColors.dim, height: 1.4),
          ),
          const SizedBox(height: 10),
          OutlinedButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const DataManagementScreen()),
            ),
            icon: const Icon(Icons.table_chart_outlined, size: 18),
            label: const Text('Open data management'),
          ),
          const SizedBox(height: 26),
          const Divider(),
          const SizedBox(height: 14),
          const SectionLabel('Mission window', icon: Icons.calendar_today_outlined),
          Consumer<AppState>(
            builder: (context, state, _) {
              return Column(
                children: [
                  _row('Start', state.settingValue('mission_start', '—')),
                  _row('End', state.settingValue('mission_end', '—')),
                  _row('Days left (sheet)', state.settingValue('mission_days_left', '—')),
                ],
              );
            },
          ),
          const SizedBox(height: 20),
          const Text(
            'Source of truth: the Google Sheet exports, imported into MySQL by '
            'manage.py import_csvs. WhatsApp check-ins sync in from the bot via '
            'POST /api/mission/checkins/.',
            style: TextStyle(fontSize: 11.5, color: AppColors.faint, height: 1.4),
          ),
          const SizedBox(height: 30),
        ],
      ),
    );
  }

  Widget _row(String k, String v) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(k, style: const TextStyle(fontSize: 13, color: AppColors.dim)),
          Text(v, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}
