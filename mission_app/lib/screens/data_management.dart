import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

import '../api.dart';
import '../theme.dart';

/// Data Management — CSV import / export inside Settings.
///
/// Export hits `data/export/` and opens the file (or ZIP) in the browser.
/// Import parses a CSV client-side, previews/validates the rows, then posts
/// them as JSON so the server can wrap the write in a transaction.
class DataManagementScreen extends StatefulWidget {
  const DataManagementScreen({super.key});

  @override
  State<DataManagementScreen> createState() => _DataManagementScreenState();
}

const _datasets = <String, String>{
  'habits': 'Habits',
  'habit_logs': 'Daily habit logs',
  'weights': 'Weight history',
  'resources': 'Study resources',
  'study_activity': 'Study activity logs',
};

class _DataManagementScreenState extends State<DataManagementScreen> {
  String _exportDataset = 'habits';
  final _from = TextEditingController();
  final _to = TextEditingController();
  bool _busy = false;
  String _status = '';

  @override
  void dispose() {
    _from.dispose();
    _to.dispose();
    super.dispose();
  }

  Future<void> _export() async {
    setState(() {
      _busy = true;
      _status = '';
    });
    final q = <String, String>{'dataset': _exportDataset};
    if (_from.text.trim().isNotEmpty) q['from'] = _from.text.trim();
    if (_to.text.trim().isNotEmpty) q['to'] = _to.text.trim();
    final url = Api.urlFor('data/export/', q);
    try {
      if (kIsWeb) {
        await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
        setState(() => _status = 'Download started for "$_exportDataset".');
      } else {
        final res = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 30));
        if (res.statusCode >= 200 && res.statusCode < 300) {
          setState(() => _status =
              'Exported ${res.bodyBytes.length} bytes (see the browser download).');
          await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
        } else {
          setState(() => _status = 'Export failed (${res.statusCode}).');
        }
      }
    } catch (e) {
      setState(() => _status = 'Export failed: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _exportAll() async {
    setState(() {
      _busy = true;
      _status = '';
    });
    final url = Api.urlFor('data/export/', {'dataset': 'all'});
    try {
      await launchUrl(Uri.parse(url), webOnlyWindowName: '_blank');
      setState(() => _status = 'Complete ZIP export started.');
    } catch (e) {
      setState(() => _status = 'Export failed: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _import() async {
    final result = await showDialog<bool>(
      context: context,
      builder: (_) => const _CsvImportDialog(),
    );
    if (result == true) {
      setState(() => _status = 'Import finished — totals refreshed.');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Data management')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const SectionLabel('Export to CSV', icon: Icons.download_outlined),
          const Text(
            'Each dataset exports as UTF-8 CSV with a header row, ISO dates and '
            'stable IDs so relationships survive a round-trip.',
            style: TextStyle(fontSize: 12, color: AppColors.dim, height: 1.4),
          ),
          const SizedBox(height: 12),
          DropdownButtonFormField<String>(
            initialValue: _exportDataset,
            decoration: const InputDecoration(labelText: 'Dataset'),
            items: _datasets.entries
                .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))
                .toList(),
            onChanged: (v) => setState(() => _exportDataset = v ?? 'habits'),
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _from,
                  decoration: const InputDecoration(
                      labelText: 'From (optional)', hintText: 'YYYY-MM-DD'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: TextField(
                  controller: _to,
                  decoration: const InputDecoration(
                      labelText: 'To (optional)', hintText: 'YYYY-MM-DD'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              FilledButton.icon(
                onPressed: _busy ? null : _export,
                icon: const Icon(Icons.download, size: 18),
                label: const Text('Export CSV'),
              ),
              const SizedBox(width: 10),
              OutlinedButton.icon(
                onPressed: _busy ? null : _exportAll,
                icon: const Icon(Icons.folder_zip_outlined, size: 18),
                label: const Text('Export everything (ZIP)'),
              ),
            ],
          ),
          const SizedBox(height: 26),
          const SectionLabel('Import from CSV', icon: Icons.upload_outlined),
          const Text(
            'Pick a dataset, choose a CSV, preview the detected columns and rows, '
            'then choose whether to add, skip duplicates, or update matches.',
            style: TextStyle(fontSize: 12, color: AppColors.dim, height: 1.4),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _busy ? null : _import,
            icon: const Icon(Icons.upload_file, size: 18),
            label: const Text('Import CSV'),
          ),
          if (_status.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(_status,
                  style: const TextStyle(fontSize: 12.5, color: AppColors.mint)),
            ),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ import

class _CsvImportDialog extends StatefulWidget {
  const _CsvImportDialog();

  @override
  State<_CsvImportDialog> createState() => _CsvImportDialogState();
}

class _CsvImportDialogState extends State<_CsvImportDialog> {
  String _dataset = 'habits';
  String _mode = 'skip_duplicates';
  final _csv = TextEditingController();
  List<String> _headers = [];
  List<Map<String, String>> _rows = [];
  bool _busy = false;
  String? _error;
  Map<String, dynamic>? _report;

  void _parse() {
    setState(() {
      _error = null;
      _report = null;
      _headers = [];
      _rows = [];
    });
    final text = _csv.text.trim();
    if (text.isEmpty) {
      setState(() => _error = 'Paste CSV content first.');
      return;
    }
    try {
      final parsed = _parseCsv(text);
      if (parsed.isEmpty) {
        setState(() => _error = 'No rows found in the CSV.');
        return;
      }
      setState(() {
        _headers = parsed.first;
        _rows = parsed.skip(1).map((r) {
          final m = <String, String>{};
          for (var i = 0; i < _headers.length; i++) {
            m[_headers[i]] = i < r.length ? r[i] : '';
          }
          return m;
        }).toList();
      });
    } catch (e) {
      setState(() => _error = 'Could not parse CSV: $e');
    }
  }

  /// Minimal RFC-4180 parser: handles quoted fields and embedded commas.
  static List<List<String>> _parseCsv(String input) {
    final rows = <List<String>>[];
    var field = StringBuffer();
    var row = <String>[];
    var inQuotes = false;
    for (var i = 0; i < input.length; i++) {
      final c = input[i];
      if (inQuotes) {
        if (c == '"') {
          if (i + 1 < input.length && input[i + 1] == '"') {
            field.write('"');
            i++;
          } else {
            inQuotes = false;
          }
        } else {
          field.write(c);
        }
      } else if (c == '"') {
        inQuotes = true;
      } else if (c == ',') {
        row.add(field.toString());
        field = StringBuffer();
      } else if (c == '\n') {
        row.add(field.toString());
        rows.add(row);
        row = <String>[];
        field = StringBuffer();
      } else if (c == '\r') {
        // skip
      } else {
        field.write(c);
      }
    }
    if (field.isNotEmpty || row.isNotEmpty) {
      row.add(field.toString());
      rows.add(row);
    }
    return rows.where((r) => r.any((c) => c.trim().isNotEmpty)).toList();
  }

  Future<void> _submit() async {
    if (_rows.isEmpty) {
      setState(() => _error = 'Parse the CSV first.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final res = await Api.post('data/import/', {
        'dataset': _dataset,
        'mode': _mode,
        'rows': _rows,
      });
      if (!mounted) return;
      setState(() {
        _report = res is Map ? Map<String, dynamic>.from(res) : null;
        _busy = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _error = 'Import failed: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;
    return AlertDialog(
      backgroundColor: AppColors.surface,
      title: const Text('Import CSV'),
      content: SizedBox(
        width: 560,
        child: SingleChildScrollView(
          padding: EdgeInsets.only(bottom: bottom),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                initialValue: _dataset,
                decoration: const InputDecoration(labelText: 'Dataset type'),
                items: _datasets.entries
                    .map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))
                    .toList(),
                onChanged: (v) => setState(() => _dataset = v ?? 'habits'),
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: _mode,
                decoration: const InputDecoration(labelText: 'If a record already exists'),
                items: const [
                  DropdownMenuItem(value: 'skip_duplicates', child: Text('Skip duplicates')),
                  DropdownMenuItem(value: 'new', child: Text('Only add new records')),
                  DropdownMenuItem(value: 'update', child: Text('Update matching records')),
                ],
                onChanged: (v) => setState(() => _mode = v ?? 'skip_duplicates'),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: _csv,
                maxLines: 6,
                minLines: 3,
                style: const TextStyle(fontSize: 12, fontFamily: 'monospace'),
                decoration: const InputDecoration(
                  labelText: 'CSV content',
                  hintText: 'Paste the file contents here (header row first)',
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  OutlinedButton.icon(
                    onPressed: _parse,
                    icon: const Icon(Icons.preview, size: 16),
                    label: const Text('Validate & preview'),
                  ),
                ],
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(_error!,
                      style: const TextStyle(color: AppColors.rose, fontSize: 12)),
                ),
              if (_headers.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text('Detected columns: ${_headers.join(', ')}',
                    style: const TextStyle(fontSize: 11.5, color: AppColors.dim)),
                const SizedBox(height: 6),
                Text('${_rows.length} data row(s) ready to import.',
                    style: const TextStyle(fontSize: 11.5, color: AppColors.mint)),
                const SizedBox(height: 6),
                Container(
                  constraints: const BoxConstraints(maxHeight: 120),
                  decoration: BoxDecoration(
                    color: AppColors.surface2,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: DataTable(
                      headingTextStyle: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700),
                      dataTextStyle: const TextStyle(fontSize: 10.5),
                      columns: _headers
                          .take(6)
                          .map((h) => DataColumn(label: Text(h)))
                          .toList(),
                      rows: _rows
                          .take(5)
                          .map((r) => DataRow(
                                cells: _headers
                                    .take(6)
                                    .map((h) => DataCell(Text(r[h] ?? '')))
                                    .toList(),
                              ))
                          .toList(),
                    ),
                  ),
                ),
              ],
              if (_report != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppColors.surface2,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Created ${_report!['created']} · Updated ${_report!['updated']} · '
                        'Skipped ${_report!['skipped']} · Invalid ${_report!['invalid']}',
                        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
                      ),
                      if ((_report!['errors'] as List? ?? []).isNotEmpty) ...[
                        const SizedBox(height: 6),
                        for (final e in (_report!['errors'] as List).take(8))
                          Text(
                            'row ${e['row']}: ${e['reason']}',
                            style: const TextStyle(fontSize: 11, color: AppColors.rose),
                          ),
                      ],
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, _report != null),
          child: Text(_report == null ? 'Cancel' : 'Done'),
        ),
        if (_report == null)
          FilledButton(
            onPressed: _busy ? null : _submit,
            child: _busy
                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                : const Text('Import'),
          ),
      ],
    );
  }
}

/// Unused today but kept for callers that need raw bytes (tests).
Uint8List decodeCsvBytes(String s) => Uint8List.fromList(utf8.encode(s));
