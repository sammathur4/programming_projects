import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../state.dart';
import '../theme.dart';

/// Vision Board tab — opens the standalone HTML board.
///
/// It is served by the Django backend at `<base>/vision-board/index.html`, so it
/// works on web, Android and iOS. You can point it anywhere else from Settings
/// (including a `file://` path when running on the same machine).
class VisionBoardScreen extends StatefulWidget {
  const VisionBoardScreen({super.key});

  @override
  State<VisionBoardScreen> createState() => _VisionBoardScreenState();
}

class _VisionBoardScreenState extends State<VisionBoardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AppState>().loadVisionBoardOverride();
    });
  }

  Future<void> _open(String url) async {
    final uri = Uri.tryParse(url);
    if (uri == null) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!ok && mounted) {
        messenger.showSnackBar(const SnackBar(content: Text('Could not open the board')));
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(SnackBar(content: Text('Could not open: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final url = state.effectiveVisionBoardUrl;
    final isOverride = (state.visionBoardUrl ?? '').trim().isNotEmpty;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        AppCard(
          gradient: AppColors.gradViolet,
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: const [
                  Icon(Icons.auto_awesome, color: Colors.white, size: 22),
                  SizedBox(width: 8),
                  Text('Vision Board',
                      style: TextStyle(
                          fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white)),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'The things you are building this year. Open it, look at it, '
                'and remember why the early mornings matter.',
                style: TextStyle(color: Colors.white70, fontSize: 12.5, height: 1.45),
              ),
              const SizedBox(height: 16),
              FilledButton.icon(
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF6D28D9),
                ),
                onPressed: () => _open(url),
                icon: const Icon(Icons.open_in_new, size: 18),
                label: const Text('Open Vision Board'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        SectionLabel('Source', icon: Icons.link, trailing: Pill(isOverride ? 'custom' : 'default', color: isOverride ? AppColors.amber : AppColors.sky)),
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SelectableText(
                url,
                style: const TextStyle(fontSize: 12, color: AppColors.dim, height: 1.4),
              ),
              const SizedBox(height: 10),
              const Text(
                'Hosted by your backend so phones and the web build can open it. '
                'Change it in Settings to use a local file or any other link.',
                style: TextStyle(fontSize: 11.5, color: AppColors.faint, height: 1.4),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        _BoardTips(),
        const SizedBox(height: 24),
        _IdeaList(),
      ],
    );
  }
}

/// A few ways to get the most out of the board.
class _BoardTips extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SectionLabel('How to use it', icon: Icons.tips_and_updates_outlined),
          const Text(
            'Open it in a browser for the full interactive board. Pin it, and '
            'look at it every morning before you start — the visual reminder '
            'beats willpower.',
            style: TextStyle(fontSize: 12, color: AppColors.dim, height: 1.45),
          ),
        ],
      ),
    );
  }
}

/// A gentle reminder list — the board is the destination, this is the nudge.
class _IdeaList extends StatelessWidget {
  static const _lines = [
    ('🏔️', 'The life you are building is bigger than today\'s mood.'),
    ('🔁', 'Motivation fades. Systems last. You built one — use it.'),
    ('📉', 'A missed day is data, not a verdict. Read it and adjust.'),
    ('🕯️', 'Consistency beats intensity. Show up small, show up often.'),
    ('🚀', '194 days left. That is enough to change everything.'),
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionLabel('Keep going', icon: Icons.favorite_outline),
        ..._lines.map((l) => AppCard(
              margin: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  Text(l.$1, style: const TextStyle(fontSize: 18)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(l.$2,
                        style: const TextStyle(fontSize: 12.5, height: 1.4, color: AppColors.text)),
                  ),
                ],
              ),
            )),
      ],
    );
  }
}
