/// Platform probe used to tell an Android emulator from a real phone.
///
/// The emulator reaches the host machine through `10.0.2.2`; a real device
/// cannot, so it needs the LAN/tether address instead. Getting this wrong
/// means the app silently talks to a host that does not exist, so it is worth
/// a reliable check.
///
/// `dart:io` is unavailable on the web, so the real implementation lives in a
/// separate file and is pulled in by a conditional import.
library;

import 'device_env_stub.dart'
    if (dart.library.io) 'device_env_io.dart' as impl;

/// True when running on an Android emulator.
///
/// Always false on the web, where the host and the "device" are the same
/// machine.
Future<bool> isAndroidEmulator() => impl.isAndroidEmulator();
