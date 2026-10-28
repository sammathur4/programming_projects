import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'offline.dart';
import 'device_env.dart';

/// Base URL resolution:
///  - web        -> the page's own origin (Django serves both), with a
///                  localhost fallback for the Flutter dev server
///  - android em -> 10.0.2.2:8000 (host loopback)
///  - real phone -> the built-in `mission` alias (maps to [hostIp])
///  - ios sim    -> localhost:8000
/// Can always be overridden at runtime via the in-app Settings screen.
///
/// **Why the web build uses the page origin.** The deployed site is served by
/// Django itself, so the API lives at the same origin as the page. A
/// hardcoded `localhost:8000` only works on the machine running Django — open
/// the same site on a phone and every call points at the phone's own
/// (nonexistent) localhost. Deriving the base from the origin makes the build
/// work from any device with no configuration.
///
/// **Friendly hostnames.** Android has no DNS entry for the dev machine, so a
/// bare name like `mission` never resolves on a real phone. To make the app
/// usable with a short, stable address we translate known aliases to a real
/// host at request time — no DNS, no root, works over USB tethering.
class Api {
  static const String fallback = 'http://10.0.2.2:8000';
  static String? _override;

  /// Resolved web base, cached after the first successful probe.
  static String? _webBase;

  /// Whether this is an Android emulator, resolved once at startup.
  static bool? _isEmulator;

  /// The host the dev server listens on. Update this if the laptop's tether
  /// address changes (`ip -4 -o addr show <iface>`), then rebuild the APK.
  static const String hostIp = '10.210.195.182';

  /// Friendly name(s) -> real address. Lets Settings accept `mission` /
  /// `mission:8000` instead of an IP that changes between replugs.
  static const Map<String, String> hostAliases = {
    'mission': hostIp,
    'mission.local': hostIp,
  };

  /// Default port the dev server listens on when the user omits one.
  static const int defaultPort = 8000;

  /// Persisted choice of a working web base, so the probe runs only when
  /// needed rather than on every page load.
  static const String _webBaseKey = 'api_base_resolved';

  /// Candidates tried on web, in order: the page's own origin first (that is
  /// where Django serves the API), then localhost (the Flutter dev-server
  /// case, where the app runs on :5000 but Django is still on :8000).
  static List<String> get webCandidates {
    final list = <String>[];
    try {
      final origin = Uri.base.origin;
      if (origin.isNotEmpty && origin != 'null') list.add(origin);
    } catch (_) {
      // Uri.base is not available outside a browser; fall through.
    }
    list.add('http://localhost:$defaultPort');
    return list;
  }

  /// Pick the first candidate that actually answers.
  ///
  /// Split out from [init] with an injectable probe so the selection logic
  /// can be unit-tested without a network.
  static Future<String?> pickWorkingBase(
    List<String> candidates,
    Future<bool> Function(String base) probe,
  ) async {
    for (final c in candidates) {
      try {
        if (await probe(c)) return c;
      } catch (_) {
        // Try the next candidate.
      }
    }
    return null;
  }

  /// Ask a candidate base whether the API is there.
  static Future<bool> _probe(String base, {Duration timeout = const Duration(seconds: 6)}) async {
    try {
      final res = await http
          .get(Uri.parse('$base/api/settings/'))
          .timeout(timeout);
      return res.statusCode >= 200 && res.statusCode < 300;
    } catch (_) {
      return false;
    }
  }

  /// Normalise user input into a usable base URL:
  ///  - trims whitespace
  ///  - adds `http://` when no scheme is given (`mission` -> `http://mission`)
  ///  - swaps a friendly host for its real address (`mission` -> 10.210.195.182)
  ///  - fills in the default port when none was typed (`mission` -> :8000)
  ///  - keeps any path, but drops a trailing slash so `$base/api/...` stays clean
  ///
  /// Always returns a string without a trailing slash, so it is safe to use as
  /// the left-hand side of `'$base/api/$path'`.
  static String normalizeBase(String url) {
    var s = url.trim();
    if (s.isEmpty) return s;
    if (!s.contains('://')) s = 'http://$s';
    Uri uri;
    try {
      uri = Uri.parse(s);
    } catch (_) {
      return s;
    }
    final mapped = hostAliases[uri.host.toLowerCase()];
    if (mapped != null) uri = uri.replace(host: mapped);
    // A friendly name with no port almost certainly means the dev server, not
    // port 80. Fill it in so `mission` works the same as `mission:8000`.
    if (mapped != null && !uri.hasPort) {
      uri = uri.replace(port: defaultPort);
    }
    var out = uri.toString();
    // Strip a trailing slash (and any empty path) so joins never double up.
    out = out.replaceAll(RegExp(r'/+$'), '');
    return out;
  }

  /// Backwards-compatible alias for [normalizeBase].
  static String resolveAlias(String url) => normalizeBase(url);

  static Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _override = prefs.getString('api_base');
    if (!kIsWeb && Platform.isAndroid) {
      // Work out whether the host is reachable at the emulator's 10.0.2.2 or
      // only at the real LAN/tether address.
      _isEmulator = await isAndroidEmulator();
    }
    if (kIsWeb) {
      await _resolveWebBase(prefs);
    } else if (_override != null && _override!.trim().isNotEmpty) {
      // A saved URL that no longer answers must not brick the app: check it
      // once and fall back to the built-in alias if it is dead. The saved value
      // is kept, so a server that comes back is picked up again.
      _overrideAlive = await _probe(normalizeBase(_override!),
          timeout: const Duration(seconds: 3));
      if (!_overrideAlive!) online = false;
    }
  }

  /// Whether the saved override answered when the app started.
  static bool? _overrideAlive;

  /// Decide which base URL the web build should use.
  ///
  /// Candidates are tried in order and the first that answers wins:
  ///   1. the URL the user saved in Settings,
  ///   2. a cached winner from a previous load (so a normal page load costs
  ///      one request),
  ///   3. the page's own origin (the deployed site: Django serves both),
  ///   4. localhost (the `flutter run -d chrome` dev-server case).
  ///
  /// If the saved URL turns out to be unreachable but another candidate works,
  /// the stale saved URL is **cleared** — otherwise a phone that once saved
  /// `localhost:8000` would keep failing forever with no way out.
  static Future<void> _resolveWebBase(SharedPreferences prefs) async {
    final saved = _override == null || _override!.trim().isEmpty
        ? null
        : normalizeBase(_override!);
    final cached = prefs.getString(_webBaseKey);

    final ordered = <String>[];
    void add(String? c) {
      if (c != null && c.isNotEmpty && !ordered.contains(c)) ordered.add(c);
    }

    // An explicit override the user saved always outranks the cache — the
    // cache is only an optimisation for the common "nothing saved" case.
    add(saved);
    add(cached);
    for (final c in webCandidates) {
      add(c);
    }

    final working = await pickWorkingBase(ordered, _probe);
    if (working == null) {
      // Nothing answered. Prefer the saved URL so the error message names the
      // address the user chose, and fall back to the origin otherwise.
      _webBase = saved ?? webCandidates.first;
      online = false;
      return;
    }

    _webBase = working;
    online = true;
    await prefs.setString(_webBaseKey, working);

    // The saved URL was dead — drop it so the next load starts clean.
    if (saved != null && working != saved) {
      _override = null;
      await prefs.remove('api_base');
    }
  }

  /// The base URL currently in use, resolved the same way for every platform.
  static String get base {
    final hasOverride = _override != null && _override!.trim().isNotEmpty;
    if (hasOverride) {
      // On native, a saved URL that failed its startup probe is skipped in
      // favour of the built-in alias. On web, `_resolveWebBase` has already
      // removed a dead override.
      if (kIsWeb || _overrideAlive != false) return normalizeBase(_override!);
    }
    if (kIsWeb) return _webBase ?? webCandidates.first;
    if (Platform.isAndroid) return _androidBase();
    if (Platform.isIOS) return 'http://localhost:$defaultPort';
    return fallback;
  }

  /// Android default.
  ///
  /// The emulator reaches the host through 10.0.2.2; a real phone cannot, so
  /// it uses the built-in `mission` alias instead — which resolves to
  /// [hostIp] without needing any DNS.
  static String _androidBase() {
    if (_isEmulator == true) return 'http://10.0.2.2:$defaultPort';
    return normalizeBase('http://mission:$defaultPort');
  }

  /// Detect the Android emulator by its characteristic 10.0.2.x address.
  ///
  /// The emulator's NAT gives the device a 10.0.2.15-style address; a real
  /// phone on Wi-Fi or tethering never looks like that.
  static bool _looksLikeEmulator() => _isEmulator == true;

  /// The URL the user actually typed, run through [normalizeBase] so the
  /// Settings screen can show them exactly where requests are going.
  static String get resolvedOverride =>
      _override == null ? '' : normalizeBase(_override!);

  static Future<void> setOverride(String url) async {
    final prefs = await SharedPreferences.getInstance();
    _override = url.trim();
    // A freshly saved URL is trusted until it is proven dead.
    _overrideAlive = null;
    if (_override!.isEmpty) {
      await prefs.remove('api_base');
    } else {
      await prefs.setString('api_base', _override!);
    }
  }

  static Uri _u(String path, [Map<String, String>? q]) {
    final b = base.replaceAll(RegExp(r'/+$'), '');
    final p = path.replaceAll(RegExp(r'^/+'), '');
    final uri = Uri.parse('$b/api/$p');
    return q == null ? uri : uri.replace(queryParameters: q);
  }

  static Future<dynamic> get(String path, [Map<String, String>? q]) async {
    final uri = _u(path, q);
    final http.Response res;
    try {
      res = await http.get(uri).timeout(const Duration(seconds: 20));
    } catch (e) {
      throw ApiException(_netError('GET', uri, e));
    }
    if (res.statusCode >= 200 && res.statusCode < 300) {
      return jsonDecode(utf8.decode(res.bodyBytes));
    }
    throw ApiException('GET /$path -> ${res.statusCode}  ($uri)');
  }

  /// Turn any thrown value into a non-empty, human-readable message that names
  /// the URL we tried. Without this a bare socket error prints as
  /// "Failed: " with nothing after it, which is impossible to diagnose.
  static String _netError(String method, Uri uri, Object e) {
    final detail = e.toString().trim();
    final kind = e.runtimeType.toString();
    final why = detail.isEmpty || detail == kind ? kind : detail;
    return '$method $uri failed: $why';
  }

  /// DELETE with an optional query string (e.g. ?index=1).
  ///
  /// Like [send], a transport failure is queued rather than thrown, so deleting
  /// an entry offline is replayed on the next Sync.
  static Future<dynamic> delete(
    String path, [
    Map<String, String>? q,
    bool offline = true,
    String label = '',
  ]) async {
    final uri = _u(path, q);
    final http.Response res;
    try {
      res = await http.delete(uri).timeout(const Duration(seconds: 20));
    } catch (e) {
      if (!offline) {
        throw ApiException(_netError('DELETE', uri, e));
      }
      await OfflineStore.queueWrite(
        id: 'DELETE $path ${q ?? const {}}',
        method: 'DELETE',
        path: path,
        query: q,
        label: label.isEmpty ? 'DELETE $path' : label,
      );
      Api.online = false;
      return {'queued': true, 'offline': true};
    }
    if (res.statusCode >= 200 && res.statusCode < 300) {
      Api.online = true;
      return res.body.isEmpty ? null : jsonDecode(utf8.decode(res.bodyBytes));
    }
    throw ApiException('DELETE /$path -> ${res.statusCode}  ($uri)');
  }

  /// POST with no body (action endpoints like habits/1/pause/).
  static Future<dynamic> post(String path, [Map<String, dynamic>? body]) =>
      send('POST', path, body ?? const {});

  /// Send a raw write, and — when [offline] is set — fall back to the local
  /// queue if the server cannot be reached.
  ///
  /// Only *transport* failures are queued. An HTTP error (400/404/500) always
  /// throws, because silently storing a request the server actively rejected
  /// would turn a bug into invisible data loss.
  static Future<dynamic> send(
    String method,
    String path,
    Map<String, dynamic> body, {
    bool offline = true,
    String label = '',
    String? dedupeId,
  }) async {
    final uri = _u(path);
    final encoded = utf8.encode(jsonEncode(body));
    final http.Response res;
    final headers = {'Content-Type': 'application/json'};
    try {
      if (method == 'PATCH') {
        // http has no top-level patch(); build the request explicitly.
        res = await http.Response.fromStream(
          await http.Client().send(http.Request('PATCH', uri)
            ..headers.addAll(headers)
            ..bodyBytes = encoded),
        ).timeout(const Duration(seconds: 20));
      } else if (method == 'POST') {
        res = await http
            .post(uri, headers: headers, body: encoded)
            .timeout(const Duration(seconds: 20));
      } else if (method == 'PUT') {
        res = await http
            .put(uri, headers: headers, body: encoded)
            .timeout(const Duration(seconds: 20));
      } else {
        res = await http
            .delete(uri, headers: headers)
            .timeout(const Duration(seconds: 20));
      }
    } catch (e) {
      if (!offline) {
        rethrow;
      }
      await OfflineStore.queueWrite(
        id: dedupeId ?? '$method $path ${jsonEncode(body)}',
        method: method,
        path: path,
        body: body,
        label: label.isEmpty ? '$method $path' : label,
      );
      online = false;
      return {'queued': true, 'offline': true};
    }
    if (res.statusCode >= 200 && res.statusCode < 300) {
      online = true;
      return res.body.isEmpty ? null : jsonDecode(utf8.decode(res.bodyBytes));
    }
    throw ApiException('$method /$path -> ${res.statusCode}  ($uri)');
  }

  /// True when the last request reached the server. Drives the offline banner.
  static bool online = true;

  /// Replay one queued operation exactly as it was originally issued.
  static Future<dynamic> replay(PendingOp op) => send(
        op.method,
        op.path,
        op.body ?? const {},
        offline: false,
      );

  static Future<void> checkConnectivity() async {
    await get('settings/');
    online = true;
  }

  /// Absolute URL for an API path — used for CSV export downloads.
  static String urlFor(String path, [Map<String, String>? q]) =>
      _u(path, q).toString();
}

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}
