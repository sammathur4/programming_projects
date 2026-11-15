# sub_gen — subliminal / affirmation video generator

Turns a text script into a long, chaptered MP4:

1. parses modules from a manifest (markdown `## Module` headings or text),
2. sources images (local `images/`, Pexels, Bing, picsum) and builds a
   Ken-Burns sequence with cross-fades,
3. synthesises each affirmation with `espeak-ng`, layers and speeds it up to
   fit the module duration, mixes it over an ambience bed,
4. renders one MP4 with chapters, soft/burned subtitles, title cards, and
   `faststart`.

Formerly nested at `yt_downloader/sub_gen/`; promoted to its own project. It has
no code dependency on `yt_downloader` — that folder just supplied source media.

## Requirements

```bash
sudo apt install ffmpeg espeak-ng
# optional: export PEXELS_API_KEY=...
```

Python: standard library only for the renderer. Optional extras for the helper
scripts (Telegram download, vision-board rendering) live in `.venv/`.

## Usage

```bash
cd sub_gen

# what would be generated?
python3 sub_video_gen.py --dry-run

# full build from a manifest
python3 sub_video_gen.py --script gf_manifest_10k.txt \
  --out output/gf_manifest_10k.mp4 \
  --minutes-per-module 3 --repeats 100 --max-speed 5 \
  --resolution 1920x1080 --images-per-module 4 \
  --subtitle-mode soft --show-titles

# quick preview: module 2 only, 40 s, visible subtitles
python3 sub_video_gen.py --modules 2 --seconds-per-module 40 \
  --subtitle-mode burn --out output/preview.mp4

# vertical 1080x1920
python3 sub_video_gen.py --resolution 1080x1920 --show-titles
```

## Layout

```
sub_gen/
├── sub_video_gen.py            main renderer
├── sub_gen.py                  script-to-manifest helper
├── make_1m_audio.py            dense high-repetition audio builder
├── make_god_mode_30m.py        fast 30-minute layered render
├── tg_download.py              Telegram channel/group downloader
├── build_vision_board.py       Notion export → offline HTML vision board
├── render_vision_board_previews.py
├── gf_*.txt, god_mode_*.md     manifests / scripts
├── images/                     curated source images (optional)
├── audio/                      source tracks + ambience beds
├── assets/
│   └── girlfriends/            music bed for the GF manifest (see its README)
├── cache/                      images, voice layers, ambience, music beds
├── output/                     rendered MP4s
└── vision_board/               generated vision-board pages
```

`cache/` is large (~1.7 GB) and safe to delete; it is re-fetched or re-synthesised
on the next render. Keeping it makes re-renders much faster.

## Music bed

`assets/girlfriends/gf_music_seamless_loop.m4a` is a seamless 4750 s loop built
from the source tracks in `audio/`. Rebuild it with:

```bash
bash assets/girlfriends/build_girlfriends_audio.sh
```

## Paths

Everything resolves relative to `sub_video_gen.py` (`BASE_DIR = Path(__file__).parent`),
so the project can be moved without editing code. Pass `--script` / `--out`
relative to the current directory.
