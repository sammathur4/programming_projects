/// Real implementation, used wherever `dart:io` exists (Android, desktop).
library;

import 'dart:io' show InternetAddressType, NetworkInterface;

/// Detect the Android emulator by its characteristic 10.0.2.x address.
///
/// The emulator's NAT gives the device a 10.0.2.15-style address; a real
/// phone on Wi-Fi or USB tethering never looks like that.
Future<bool> isAndroidEmulator() async {
  try {
    final ifaces = await NetworkInterface.list();
    for (final i in ifaces) {
      for (final a in i.addresses) {
        if (a.type == InternetAddressType.IPv4 && a.address.startsWith('10.0.2.')) {
          return true;
        }
      }
    }
  } catch (_) {
    // If we cannot tell, assume a real device.
  }
  return false;
}
