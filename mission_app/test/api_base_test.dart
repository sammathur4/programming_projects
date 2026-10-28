import 'package:flutter_test/flutter_test.dart';
import 'package:mission_app/api.dart';

/// The web build must find the API wherever the page came from, because the
/// site is served by Django itself. These tests pin the selection rules.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('origin wins when it answers (deployed site on any device)', () async {
    final chosen = await Api.pickWorkingBase(
      ['http://10.210.195.182:8000', 'http://localhost:8000'],
      (base) async => base == 'http://10.210.195.182:8000',
    );
    expect(chosen, 'http://10.210.195.182:8000');
  });

  test('falls back to localhost when the origin is not the API', () async {
    // `flutter run -d chrome` serves the app from :5000 while Django is :8000.
    final chosen = await Api.pickWorkingBase(
      ['http://localhost:5000', 'http://localhost:8000'],
      (base) async => base == 'http://localhost:8000',
    );
    expect(chosen, 'http://localhost:8000');
  });

  test('returns null when nothing answers', () async {
    final chosen = await Api.pickWorkingBase(
      ['http://a:1', 'http://b:2'],
      (base) async => false,
    );
    expect(chosen, isNull);
  });

  test('a throwing probe does not abort the search', () async {
    final chosen = await Api.pickWorkingBase(
      ['http://boom:1', 'http://ok:2'],
      (base) async {
        if (base.contains('boom')) throw StateError('probe exploded');
        return true;
      },
    );
    expect(chosen, 'http://ok:2');
  });

  test('localhost is always the last resort candidate', () {
    final c = Api.webCandidates;
    expect(c.last, 'http://localhost:8000');
  });

  test('the alias still normalises for the phone default', () {
    expect(Api.normalizeBase('http://mission:8000'), 'http://10.210.195.182:8000');
    expect(Api.normalizeBase('mission'), 'http://10.210.195.182:8000');
  });

  test('a saved URL that no longer answers falls through to the origin', () async {
    // The phone's browser once saved `localhost:8000`; from the phone that
    // points at the phone. The origin must win instead.
    final chosen = await Api.pickWorkingBase(
      [
        'http://localhost:8000', // saved but dead
        'http://10.210.195.182:8000', // the page origin
      ],
      (base) async => base == 'http://10.210.195.182:8000',
    );
    expect(chosen, 'http://10.210.195.182:8000');
  });

  test('a saved URL that DOES answer is kept', () async {
    final chosen = await Api.pickWorkingBase(
      [
        'http://192.168.1.5:8000', // saved and alive
        'http://10.210.195.182:8000', // the page origin
      ],
      (base) async => true, // everything answers
    );
    expect(chosen, 'http://192.168.1.5:8000',
        reason: 'an explicit user choice must outrank the origin');
  });
}
