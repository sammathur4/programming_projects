#!/usr/bin/env python3
"""
Sub-Video Generator — layered, accelerated affirmation video from a text script.

What it does
------------
1. Parses a subliminal script (markdown with "## Module" headings) into modules.
2. Fetches images for each module (local folder, Pexels, Bing image search, or
   picsum.photos) and builds a Ken-Burns image sequence with cross-fades.
3. Synthesises every affirmation with espeak-ng, loops each one N times
   (default 100), speeds it up with cascaded atempo so it fits the module
   duration, then layers/mixes the affirmations over an ambience bed.
4. Concatenates all module video + audio into a single MP4 with:
      - embedded MP4 chapters (one per module)
      - subtitles (soft mov_text track, burned-in, or both)
      - a title card overlay at the start of every module
      - faststart flag so it can stream.

Requirements
------------
    sudo apt install ffmpeg espeak-ng
    (optional) export PEXELS_API_KEY=...      # best quality auto images
    (optional) put curated Pinterest/Google images in ./images/

Examples
--------
    # Full build using curated ./images (falls back to web search automatically)
    python3 sub_video_gen.py

    # Fast preview: module 2 only, 40 s, visible subtitles
    python3 sub_video_gen.py --modules 2 --seconds-per-module 40 \
        --subtitle-mode burn --out output/preview.mp4

    # Vertical (shorts/Reels) render at 1080x1920
    python3 sub_video_gen.py --resolution 1080x1920 --show-titles

    # Just show what would be generated
    python3 sub_video_gen.py --dry-run

"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths & constants
# --------------------------------------------------------------------------- #

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SCRIPT = BASE_DIR / "god_mode_lifemaxxing.md"
IMAGES_DIR = BASE_DIR / "images"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / "cache"
VOICE_CACHE = CACHE_DIR / "voice"
IMAGE_CACHE = CACHE_DIR / "images"
AMBIENCE_DIR = BASE_DIR / "audio"

DEFAULT_OUT = OUTPUT_DIR / "apex_protocol_subliminal_video.mp4"
DEFAULT_AMBIENCE = AMBIENCE_DIR / "rain.mp3"

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".opus",
                    ".mkv", ".mp4", ".webm", ".mov", ".avi"}

SKIP_SECTIONS = {"listening protocol"}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

# Module keyword -> image search queries (first ~3 words of the title matched).
IMAGE_QUERY_MAP: list[tuple[tuple[str, ...], list[str]]] = [
    (("identity", "god-tier", "weakness"), ["confident man portrait", "luxury lifestyle man", "silhouette suit"]),
    (("upsc", "ias", "air 1", "officer"), ["study desk books", "library study night", "indian civil services"]),
    (("greek god", "physique", "physical"), ["gym muscular man", "fitness training", "athletic body"]),
    (("skin",), ["clear skin face", "skincare routine", "glowing skin"]),
    (("hair",), ["curly black hair man", "healthy hair", "barber haircut"]),
    (("eye", "vision"), ["eye close up", "blue sky horizon", "focus eye"]),
    (("smoking", "compulsion", "addiction"), ["running outdoors morning", "fresh air mountains", "healthy lifestyle"]),
    (("romantic", "dating"), ["romantic couple sunset", "candle dinner date", "couple walking beach"]),
    (("intimate", "100"), ["attractive man portrait", "night city lights", "party celebration"]),
    (("instagram", "social proof"), ["smartphone social media", "content creator camera", "city rooftop"]),
    (("dental", "smile"), ["smile white teeth", "bright smile portrait"]),
    (("money", "wealth"), ["money cash luxury", "gold coins", "sports car city"]),
    (("luck", "serendipity", "opportunity"), ["sunrise road horizon", "open door light", "hot air balloon sky"]),
    (("fame", "friendship", "social circle"), ["friends party night", "group celebration", "luxury party"]),
    (("youthful", "energy"), ["young energetic man", "morning jog sunlight"]),
    (("charisma", "intelligence", "communication"), ["public speaking stage", "confident man suit", "microphone talk"]),
    (("discipline", "time mastery"), ["clock schedule discipline", "workout discipline", "desk focus timer"]),
    (("emotional", "self-respect"), ["calm meditation man", "man looking horizon", "peaceful mountain"]),
    (("100x", "life upgrade"), ["luxury lifestyle travel", "penthouse view city", "private jet"]),
    (("gratitude", "receiving"), ["sunrise gratitude hands", "golden hour field", "thankful nature"]),
    (("sleep", "absorption"), ["night sky stars", "comfortable bed night", "moon clouds"]),
    (("weight loss", "fat", "lean"), ["running weight loss", "fitness transformation", "healthy salad gym"]),
    (("letting go", "past"), ["freedom beach sunset", "balloon releasing sky", "peaceful sunrise lake"]),
    (("happening", "phone", "blowing"), ["friends party night", "phone notifications", "city nightlife people"]),
]

DEFAULT_QUERIES = ["luxury lifestyle motivation", "cinematic dark aesthetic", "success inspiration"]

# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def log(message: str) -> None:
    print(message, flush=True)


def die(message: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    log(f"[ERROR] {message}")
    raise SystemExit(code)


def run(command: list[str], label: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess and surface clear errors."""
    result = subprocess.run(command, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "no details").strip()
        log(f"[ERROR] {label} failed (exit {result.returncode})")
        log(detail[-3000:])
        raise SystemExit(result.returncode)
    return result


def slugify(value: str, max_len: int = 48) -> str:
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    value = re.sub(r"[\s_-]+", "_", value)
    return (value[:max_len] or "module").strip("_")


def speech_text(line: str) -> str:
    """Clean a line so the TTS engine reads it naturally."""
    line = re.sub(r"(\d)\s*[–—-]\s*(\d)", r"\1 to \2", line)
    line = line.replace("—", ",").replace("–", ",")
    line = line.replace("%", " percent").replace("&", " and ")
    line = re.sub(r"\s*([,;:.!?])\s*", r"\1 ", line)
    return re.sub(r"\s+", " ", line).strip()


def escape_filter_path(path: str) -> str:
    """Escape a filesystem path for use inside an ffmpeg filter argument."""
    return (
        path.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def find_font() -> str | None:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def wav_info(path: Path) -> tuple[int, int]:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes(), handle.getframerate()


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Script parsing
# --------------------------------------------------------------------------- #


class Module:
    def __init__(self, number: int, title: str, lines: list[str]):
        self.number = number
        self.title = title
        self.lines = lines

    @property
    def chapter_title(self) -> str:
        return re.sub(r"^\d+[.)]\s*", "", self.title).strip()

    @property
    def slug(self) -> str:
        return slugify(self.chapter_title)


def parse_script(path: Path) -> list[Module]:
    if not path.exists():
        die(f"subliminal script not found: {path}")
    raw = path.read_text(encoding="utf-8").splitlines()

    modules: list[Module] = []
    current_title: str | None = None
    current_lines: list[str] = []
    counter = 0

    def flush() -> None:
        nonlocal counter
        if current_title is None:
            return
        if current_title.strip().lower() in SKIP_SECTIONS:
            return
        if not current_lines:
            return
        counter += 1
        modules.append(Module(counter, current_title.strip(), current_lines[:]))

    for raw_line in raw:
        line = raw_line.rstrip()
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip()
            current_lines = []
            continue
        if current_title is None:
            continue
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith(("- ", "* ")):
            stripped = stripped[2:].strip()
        if stripped:
            current_lines.append(stripped)

    flush()
    if not modules:
        die(f"no modules found in {path} (expected '## ' headings).")
    return modules


# --------------------------------------------------------------------------- #
# Image sourcing
# --------------------------------------------------------------------------- #


def queries_for(title: str) -> list[str]:
    lowered = title.lower()
    for keywords, queries in IMAGE_QUERY_MAP:
        if any(keyword in lowered for keyword in keywords):
            return queries
    return DEFAULT_QUERIES


def local_images() -> list[Path]:
    if not IMAGES_DIR.exists():
        return []
    found = [
        p
        for p in sorted(IMAGES_DIR.rglob("*"))
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return found


def load_image_manifest(path: Path) -> dict[str, list[Path]]:
    """Parse a per-module image list.

    Format:
        ## MODULE TITLE
        relative/or/absolute/image.jpg
        ...

    Paths resolve relative to the manifest file. Missing files are reported and
    skipped so a half-finished download still renders the rest.
    """
    if not path.exists():
        die(f"image manifest not found: {path}")
    base = path.parent
    manifest: dict[str, list[Path]] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or (line.startswith("#") and not line.startswith("## ")):
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            manifest.setdefault(current, [])
            continue
        if current is None:
            continue
        candidate = Path(line).expanduser()
        if not candidate.is_absolute():
            candidate = (base / candidate).resolve()
        if candidate.exists():
            manifest[current].append(candidate)
        else:
            log(f"[WARN] manifest image missing: {line}")
    return {title: paths for title, paths in manifest.items() if paths}


def manifest_images(
    manifest: dict[str, list[Path]], title: str, index: int, count: int
) -> list[Path]:
    """Pick `count` images for a module, matching on title (loose)."""
    key = title.strip().lower()
    for name, paths in manifest.items():
        lowered = name.strip().lower()
        if lowered == key or lowered in key or key in lowered:
            return [paths[(index + i) % len(paths)] for i in range(count)]
    return []


def http_get(url: str, timeout: int = 20, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            ),
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def save_image(data: bytes, destination: Path) -> bool:
    if len(data) < 8_000:
        return False
    destination.write_bytes(data)
    return True


def fetch_pexels(query: str, count: int, key: str, orientation: str) -> list[bytes]:
    url = (
        "https://api.pexels.com/v1/search?"
        + urllib.parse.urlencode({"query": query, "per_page": count, "orientation": orientation})
    )
    payload = json.loads(http_get(url, headers={"Authorization": key}))
    blobs: list[bytes] = []
    for photo in payload.get("photos", []):
        src = photo.get("src", {})
        link = src.get("large2x") or src.get("large") or src.get("original")
        if not link:
            continue
        try:
            blobs.append(http_get(link, timeout=30))
        except Exception:
            continue
    return blobs


def fetch_bing(query: str, count: int) -> list[bytes]:
    url = (
        "https://www.bing.com/images/async?"
        + urllib.parse.urlencode({"q": query, "count": count * 4, "first": 1, "mkt": "en-US"})
    )
    html = http_get(url, timeout=25).decode("utf-8", "ignore")
    links = re.findall(r'murl&quot;:&quot;(.*?)&quot;', html)
    if not links:
        links = re.findall(r'"murl":"(.*?)"', html)
    blobs: list[bytes] = []
    random.shuffle(links)
    for link in links:
        if len(blobs) >= count:
            break
        try:
            data = http_get(link, timeout=20)
        except Exception:
            continue
        if save_image(data, IMAGE_CACHE / f"probe_{md5_hex(link)[:10]}.jpg"):
            blobs.append(data)
    return blobs


def fetch_picsum(count: int, width: int, height: int, seed: int) -> list[bytes]:
    blobs: list[bytes] = []
    for i in range(count):
        url = f"https://picsum.photos/{width}/{height}?random={seed}-{i}"
        try:
            blobs.append(http_get(url, timeout=25))
        except Exception:
            continue
    return blobs


def make_placeholder_image(destination: Path, width: int, height: int, seed: int) -> None:
    rng = random.Random(seed)
    c0 = f"0x{rng.randint(10, 40):02x}{rng.randint(10, 40):02x}{rng.randint(30, 70):02x}"
    c1 = f"0x{rng.randint(30, 90):02x}{rng.randint(10, 40):02x}{rng.randint(50, 110):02x}"
    run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi",
            "-i", f"gradients=s={width}x{height}:c0={c0}:c1={c1}:d=1",
            "-frames:v", "1",
            str(destination),
        ],
        f"placeholder image {destination.name}",
    )


def ensure_images(
    module: Module,
    index: int,
    count: int,
    args: argparse.Namespace,
    fallback_pool: list[Path],
    manifest_pool: dict[str, list[Path]] | None = None,
) -> list[Path]:
    """Return `count` usable image paths for a module (downloads if needed)."""
    if manifest_pool:
        picked = manifest_images(manifest_pool, module.title, index, count)
        if picked:
            log(f"[IMG] module {index}: {len(picked)} image(s) from manifest")
            return picked

    destination_dir = IMAGE_CACHE / f"{index:02d}_{module.slug}"
    destination_dir.mkdir(parents=True, exist_ok=True)

    orientation = "portrait" if args.height > args.width else "landscape"
    queries = queries_for(module.title)

    for query in queries[:2]:
        tag = md5_hex(f"{query}|{orientation}")[:10]
        cached = sorted(destination_dir.glob(f"{tag}_*.jpg"))
        if len(cached) >= count:
            return cached[:count]

        blobs: list[bytes] = []
        source_used = "none"
        if args.image_source in ("auto", "pexels") and args.pexels_key:
            try:
                blobs = fetch_pexels(query, count, args.pexels_key, orientation)
                source_used = "pexels"
            except Exception as exc:  # noqa: BLE001
                log(f"[WARN] Pexels failed for '{query}': {exc}")
        if not blobs and args.image_source in ("auto", "bing"):
            try:
                blobs = fetch_bing(query, count)
                source_used = "bing"
            except Exception as exc:  # noqa: BLE001
                log(f"[WARN] Bing images failed for '{query}': {exc}")
        if not blobs and args.image_source in ("auto", "picsum"):
            try:
                blobs = fetch_picsum(count, args.width, args.height, seed=index * 97 + 13)
                source_used = "picsum"
            except Exception as exc:  # noqa: BLE001
                log(f"[WARN] picsum failed: {exc}")

        saved: list[Path] = []
        for i, blob in enumerate(blobs):
            target = destination_dir / f"{tag}_{i:02d}.jpg"
            if save_image(blob, target):
                saved.append(target)
        if saved:
            log(f"[IMG] module {index}: using {len(saved)} image(s) from {source_used} for '{query}'")
            return (saved * count)[:count]

    # Fall back to any locally curated images (Pinterest / Google dumps).
    # Each module takes its own slice of the pool so a long video shows every
    # curated image once instead of repeating the first few over and over.
    if fallback_pool:
        offset = (index - 1) * count
        picks = [fallback_pool[(offset + i) % len(fallback_pool)] for i in range(count)]
        log(f"[IMG] module {index}: using {count} curated local image(s)")
        return picks

    # Last resort: generated gradient cards so the build still succeeds offline.
    placeholders: list[Path] = []
    for i in range(count):
        target = destination_dir / f"placeholder_{i:02d}.jpg"
        if not target.exists():
            make_placeholder_image(target, args.width, args.height, seed=index * 100 + i)
        placeholders.append(target)
    log(f"[IMG] module {index}: generated {count} placeholder image(s) (offline)")
    return placeholders


# --------------------------------------------------------------------------- #
# Audio
# --------------------------------------------------------------------------- #


def atempo_chain(factor: float) -> str:
    """Build an atempo filter chain, keeping each stage <= 2.0 for quality."""
    factor = max(factor, 0.5)
    stages: list[str] = []
    remaining = factor
    while remaining > 2.0:
        stages.append("atempo=2.0")
        remaining /= 2.0
    stages.append(f"atempo={remaining:.6f}")
    return ",".join(stages)


def synth_line(text: str, voice: str, wpm: int) -> Path:
    """Synthesise one affirmation line, cached by content hash."""
    key = md5_hex(f"{voice}|{wpm}|{text}")[:16]
    target = VOICE_CACHE / f"{key}.wav"
    if target.exists() and target.stat().st_size > 44:
        return target
    VOICE_CACHE.mkdir(parents=True, exist_ok=True)
    run(
        ["espeak-ng", "-v", voice, "-s", str(wpm), "-w", str(target), text],
        f"TTS '{text[:40]}...'",
    )
    return target


def build_module_audio(
    lines: list[str],
    voice_wavs: list[Path],
    out_path: Path,
    duration: float,
    args: argparse.Namespace,
    ambience: Path | None,
    rain: Path | None = None,
    theta: Path | None = None,
    ambience_offset: float = 0.0,
) -> None:
    """Create one module's audio: layered loops of every line over the bed.

    The bed has three optional layers, each with its own gain:
      * `ambience` — songs / music (conscious)
      * `rain`     — rain loop (conscious)
      * `theta`    — binaural theta tone, e.g. 6 Hz (subconscious entrainment)
    The affirmation voice sits under all of them (`--voice-gain`), so the
    conscious mind follows the music/rain while the script lands underneath.

    `ambience_offset` is where the bed starts inside the (infinitely looped)
    bed files. Passing the running module offset keeps everything playing
    continuously across chapter boundaries instead of restarting per chapter.
    """
    max_layers = max(1, args.max_layers)
    blocks = [list(range(i, min(i + max_layers, len(lines)))) for i in range(0, len(lines), max_layers)]
    n_blocks = max(1, len(blocks))
    block_duration = duration / n_blocks

    # Step 1: speed each line up ONCE (only a few seconds of audio), then loop
    # the short result. Looping first and speeding up afterwards would push
    # `repeats x line-length` seconds (hours) through atempo and take an age.
    prepared: list[Path] = []
    loop_info: list[tuple[int, int, float]] = []  # (frames, loops, speed)
    for line_index, wav in enumerate(voice_wavs):
        frames, rate = wav_info(wav)
        source_seconds = max(frames / float(rate), 0.05)
        loops = args.repeats
        if args.max_speed > 0:
            fits = int(math.floor((block_duration * args.max_speed) / source_seconds))
            loops = max(1, min(args.repeats, fits))
        required = (source_seconds * loops) / max(block_duration, 0.01)
        effective = max(args.speed_factor, required)

        tempo_wav = out_path.parent / f"{out_path.stem}_line{line_index:02d}.wav"
        run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
                "-i", str(wav),
                "-filter:a", atempo_chain(effective),
                "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
                str(tempo_wav),
            ],
            f"speeding up line {line_index + 1}",
        )
        tframes, _ = wav_info(tempo_wav)
        prepared.append(tempo_wav)
        loop_info.append((tframes, loops, effective))
        log(f"    loop x{loops} | {effective:6.2f}x speed | {lines[line_index][:52]}")

    command = ["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-nostdin"]
    bed_sources: list[tuple[str, Path]] = []
    if ambience is not None:
        command += ["-stream_loop", "-1", "-i", str(ambience)]
        bed_sources.append(("amb", ambience))
    if rain is not None:
        command += ["-stream_loop", "-1", "-i", str(rain)]
        bed_sources.append(("rain", rain))
    if theta is not None:
        command += ["-stream_loop", "-1", "-i", str(theta)]
        bed_sources.append(("theta", theta))
    for wav in prepared:
        command += ["-i", str(wav)]
    first_voice = len(bed_sources)
    if bed_sources:
        log(
            f"    bed continues at {ambience_offset:,.1f}s "
            f"({len(bed_sources)} layer(s): "
            + ", ".join(kind for kind, _ in bed_sources) + ")"
        )

    filters: list[str] = []
    bed_labels: list[str] = []
    bed_gains = {
        "amb": args.ambience_gain,
        "rain": args.rain_gain,
        "theta": args.theta_gain,
    }
    for index, (kind, _source) in enumerate(bed_sources):
        label = f"bed_{kind}"
        # atrim(start) -> skip into the looped bed, reset the clock, then keep
        # exactly `duration` seconds. The bed therefore flows on from where the
        # previous module stopped rather than jumping back to its first second.
        filters.append(
            f"[{index}:a]atrim=start={ambience_offset:.6f},asetpts=PTS-STARTPTS,"
            f"atrim=duration={duration:.6f},"
            f"volume={bed_gains[kind]}dB,aformat=sample_fmts=fltp:"
            f"channel_layouts=stereo:sample_rates=44100[{label}]"
        )
        bed_labels.append(f"[{label}]")

    block_labels: list[str] = []
    for b, line_indexes in enumerate(blocks):
        layer_labels: list[str] = []
        for j, line_index in enumerate(line_indexes):
            tframes, loops, _ = loop_info[line_index]
            label = f"b{b}l{j}"
            filters.append(
                f"[{first_voice + line_index}:a]"
                f"aloop=loop={loops - 1}:size={tframes},"
                f"atrim=duration={block_duration:.6f},asetpts=PTS-STARTPTS,"
                f"volume={args.voice_gain}dB,"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo:sample_rates=44100[{label}]"
            )
            layer_labels.append(f"[{label}]")
        if len(layer_labels) == 1:
            filters.append(f"{layer_labels[0]}alimiter=limit=0.90[mb{b}]")
        else:
            filters.append(
                "".join(layer_labels)
                + f"amix=inputs={len(layer_labels)}:duration=longest:normalize=0,"
                f"alimiter=limit=0.90[mb{b}]"
            )
        block_labels.append(f"[mb{b}]")

    if len(block_labels) == 1:
        filters.append(f"{block_labels[0]}anull[voice]")
    else:
        filters.append("".join(block_labels) + f"concat=n={len(block_labels)}:v=0:a=1[voice]")

    if bed_labels:
        mix_inputs = "".join(bed_labels) + "[voice]"
        filters.append(
            f"{mix_inputs}amix=inputs={len(bed_labels) + 1}:duration=longest:normalize=0,"
            f"alimiter=limit=0.95,atrim=duration={duration:.6f}[out]"
        )
    else:
        filters.append(f"[voice]alimiter=limit=0.95,atrim=duration={duration:.6f}[out]")

    command += [
        "-filter_complex", ";".join(filters),
        "-map", "[out]",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        str(out_path),
    ]
    run(command, f"module audio -> {out_path.name}")


def build_ambience_playlist(folder: Path) -> Path | None:
    """Concatenate every song in `folder` into one looping backing track.

    Each file is re-encoded (extracting audio only) to a uniform AAC/M4A,
    then stream-concatenated. The result is cached under cache/ambience/
    keyed by file names + sizes + total duration, so it's rebuilt only when
    the folder's contents change. Returns None if the folder has no usable
    audio files.
    """
    songs = sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )
    if not songs:
        return None

    signature = md5_hex("|".join(
        f"{p.name}:{p.stat().st_size}" for p in songs
    ))[:16]
    playlist_dir = CACHE_DIR / "ambience"
    playlist_dir.mkdir(parents=True, exist_ok=True)
    playlist = playlist_dir / f"playlist_{signature}.m4a"

    log(f"[AMB] Folder '{folder}': {len(songs)} song(s) -> {playlist.name}")
    if playlist.exists() and playlist.stat().st_size > 10_000:
        log("[AMB] Using cached combined playlist.")
        return playlist

    # Step 1: extract + uniform-encode each song's audio.
    segments: list[Path] = []
    for i, song in enumerate(songs, start=1):
        segment = playlist_dir / f"{signature}_{i:02d}.m4a"
        if not (segment.exists() and segment.stat().st_size > 10_000):
            log(f"    [{i}/{len(songs)}] extracting audio: {song.name[:70]}")
            run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
                    "-i", str(song),
                    "-map", "0:a:0",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
                    str(segment),
                ],
                f"extracting ambience audio from {song.name}",
            )
        probe = run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(segment)],
            f"probing {segment.name}",
            check=False,
        )
        log(f"    segment {i}: {probe.stdout.strip() or '?'}s")
        segments.append(segment)

    # Step 2: concatenate all segments (same codec, so stream copy works).
    concat_path = playlist_dir / f"{signature}_concat.txt"
    concat_files(concat_path, segments)
    result = run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-c", "copy", str(playlist),
        ],
        "concatenating ambience playlist",
        check=False,
    )
    if result.returncode != 0 or not playlist.exists() or playlist.stat().st_size <= 10_000:
        log("[WARN] Playlist concat failed; mixing songs with re-encode instead.")
        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin"]
        for segment in segments:
            command += ["-i", str(segment)]
        command += [
            "-filter_complex",
            "".join(f"[{i}:a]" for i in range(len(segments)))
            + f"concat=n={len(segments)}:v=0:a=1[out]",
            "-map", "[out]",
            "-c:a", "aac", "-b:a", "160k",
            str(playlist),
        ]
        run(command, "concatenating ambience playlist (re-encode)")

    # Step 3: clean up per-song segments, keep the cached playlist.
    for segment in segments:
        segment.unlink(missing_ok=True)
    concat_path.unlink(missing_ok=True)
    log(f"[AMB] Combined playlist ready: {playlist.name}")
    return playlist


def build_ambience(path: Path, duration_seconds: int) -> Path:
    """Return an ambience file, generating pink noise if none exists.

    `path` may be a single audio file OR a folder of songs. A folder is
    concatenated (in sorted order, audio only) into one cached playlist file
    so every song plays, instead of only the first one looping.
    """
    if path and Path(path).is_dir():
        combined = build_ambience_playlist(Path(path))
        if combined is not None:
            return combined
    for candidate in (path, DEFAULT_AMBIENCE):
        if candidate and Path(candidate).exists():
            return Path(candidate)
    generated = CACHE_DIR / "generated_ambience.wav"
    if not generated.exists() or generated.stat().st_size < 100_000:
        generated.parent.mkdir(parents=True, exist_ok=True)
        run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi",
                "-i", f"anoisesrc=color=pink:sample_rate=44100:duration={max(duration_seconds, 60)}",
                "-af", "highpass=f=200,lowpass=f=8000,volume=-3dB",
                "-ac", "2", str(generated),
            ],
            "generating ambience bed",
        )
    return generated


def build_theta(hz: float, carrier: float = 200.0) -> Path | None:
    """Create (or reuse) a seamless stereo binaural tone.

    Left ear gets `carrier` Hz, right ear gets `carrier + hz` Hz, so the brain
    hears a `hz` Hz beat (6 Hz = theta). Ten seconds is loop-safe because both
    frequencies complete whole cycles inside that window.
    """
    if hz <= 0:
        return None
    path = CACHE_DIR / f"theta_{carrier:g}_{hz:g}hz.wav"
    if path.exists() and path.stat().st_size > 100_000:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    left = carrier
    right = carrier + hz
    run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
            "-f", "lavfi",
            "-i",
            f"aevalsrc=0.25*sin(2*PI*{left}*t)|0.25*sin(2*PI*{right}*t)"
            ":s=44100:d=10",
            "-ac", "2", "-c:a", "pcm_s16le", str(path),
        ],
        f"generating {hz:g} Hz binaural theta tone",
    )
    return path


def apply_fade_out(
    path: Path, total_seconds: float, fade_seconds: float, workdir: Path
) -> Path:
    """Fade the tail of a finished audio file so it never ends abruptly.

    Returns the original path when fading is disabled or the file is shorter
    than the fade, so existing builds are untouched unless --fade-out is used.
    """
    if fade_seconds <= 0 or total_seconds <= fade_seconds:
        return path
    out_path = workdir / f"{path.stem}_faded{path.suffix}"
    start = max(total_seconds - fade_seconds, 0.0)
    log(f"[FADE] fading out the last {fade_seconds:g}s")
    run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
            "-i", str(path),
            "-af", f"afade=t=out:st={start:.3f}:d={fade_seconds:.3f},"
                   f"alimiter=limit=0.95",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            str(out_path),
        ],
        "fading out the ending",
    )
    return out_path


# --------------------------------------------------------------------------- #
# Video
# --------------------------------------------------------------------------- #


def build_module_video(
    images: list[Path],
    duration: float,
    out_path: Path,
    args: argparse.Namespace,
    title: str,
    font: str | None,
    title_file: Path | None,
    srt_file: Path | None = None,
) -> None:
    """Ken-Burns image sequence with cross-fades and an optional title card.

    When `srt_file` is given, its subtitles are burned in here (one pass per
    module) instead of re-encoding the whole finished movie afterwards.
    """
    n = len(images)
    transition = args.transition_seconds if n > 1 and args.transition != "none" else 0.0
    if n > 1 and transition > 0:
        clip_duration = (duration + (n - 1) * transition) / n
    else:
        clip_duration = duration / n

    width, height = args.width, args.height
    command = ["ffmpeg", "-hide_banner", "-y", "-loglevel", "error", "-nostdin"]
    for image in images:
        command += ["-loop", "1", "-t", f"{clip_duration:.6f}", "-i", str(image)]

    filters: list[str] = []
    for i in range(n):
        if args.ken_burns:
            big_w, big_h = int(width * 1.30), int(height * 1.30)
            chain = (
                f"[{i}:v]scale={big_w}:{big_h}:force_original_aspect_ratio=increase,"
                f"crop={big_w}:{big_h},setsar=1,fps={args.fps},"
                f"zoompan=z='min(zoom+0.0007,1.20)':d={max(1, int(clip_duration * args.fps))}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={width}x{height}:fps={args.fps},"
                f"trim=duration={clip_duration:.6f},setpts=PTS-STARTPTS[v{i}]"
            )
        else:
            chain = (
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},setsar=1,fps={args.fps},"
                f"trim=duration={clip_duration:.6f},setpts=PTS-STARTPTS[v{i}]"
            )
        filters.append(chain)

    if n == 1:
        last = "v0"
    elif transition <= 0:
        filters.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vseq]")
        last = "vseq"
    else:
        previous = "v0"
        for i in range(1, n):
            offset = i * (clip_duration - transition)
            label = f"x{i}"
            filters.append(
                f"[{previous}][v{i}]xfade=transition=fade:duration={transition:.3f}:"
                f"offset={offset:.3f}[{label}]"
            )
            previous = label
        last = previous

    current = f"[{last}]"
    if args.show_titles and font and title_file is not None:
        font_size = max(28, int(height * 0.038))
        safe_font = escape_filter_path(font)
        safe_title = escape_filter_path(str(title_file))
        filters.append(
            f"{current}drawtext=fontfile='{safe_font}':textfile='{safe_title}':"
            f"fontcolor=white@0.94:fontsize={font_size}:"
            f"x=(w-text_w)/2:y=h*0.80:box=1:boxcolor=black@0.42:boxborderw=20:"
            f"alpha='if(lt(t,0.8),t/0.8,if(lt(t,4.0),1,max(0,(5.0-t)/1.0)))'[vt]"
        )
        current = "[vt]"

    if srt_file is not None:
        escaped_srt = escape_filter_path(str(srt_file))
        filters.append(
            f"{current}subtitles=filename='{escaped_srt}':"
            f"force_style='{subtitle_style(args)}'[vs]"
        )
        current = "[vs]"

    filters.append(f"{current}format=yuv420p[vfinal]")

    command += [
        "-filter_complex", ";".join(filters),
        "-map", "[vfinal]",
        "-an",
        "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-r", str(args.fps),
    ]
    if args.threads > 0:
        command += ["-threads", str(args.threads)]
    command += [
        "-t", f"{duration:.6f}",
        "-movflags", "+faststart",
        str(out_path),
    ]
    run(command, f"module video -> {out_path.name}")


def concat_files(list_path: Path, files: list[Path]) -> None:
    lines = ["file '" + str(f).replace("'", "'\\''") + "'" for f in files]
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def concat_streams(files: list[Path], out_path: Path, workdir: Path, kind: str) -> None:
    """Concatenate same-codec segments (stream copy, with re-encode fallback)."""
    list_path = workdir / f"concat_{kind}.txt"
    concat_files(list_path, files)
    copy_result = run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c", "copy", str(out_path),
        ],
        f"concatenating {kind} (stream copy)",
        check=False,
    )
    if copy_result.returncode == 0 and out_path.exists() and out_path.stat().st_size > 10_000:
        return
    log(f"[WARN] {kind} stream-copy concat failed; re-encoding instead.")
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin"]
    for f in files:
        command += ["-i", str(f)]
    stream = "v" if kind == "video" else "a"
    command += [
        "-filter_complex",
        "".join(f"[{i}:{stream}]" for i in range(len(files)))
        + f"concat=n={len(files)}:v={1 if kind == 'video' else 0}:a={0 if kind == 'video' else 1}[out]",
        "-map", "[out]",
    ]
    if kind == "video":
        command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    else:
        command += ["-c:a", "aac", "-b:a", "192k"]
    command += [str(out_path)]
    run(command, f"concatenating {kind} (re-encode)")


# --------------------------------------------------------------------------- #
# Subtitles & chapters
# --------------------------------------------------------------------------- #


def srt_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def srt_cues(
    modules: list[Module], durations: list[float], max_layers: int = 3
) -> list[tuple[float, float, str]]:
    """Build the subtitle cue list, mirroring build_module_audio's block math.

    Audio plays lines in blocks of `max_layers` (looped and layered), so each
    line is audibly playing for its whole block, not duration/len(lines).
    Each cue therefore spans its line's block (split equally among the block's
    lines for display), keeping the visible decree inside the set currently
    audible.
    """
    cues: list[tuple[float, float, str]] = []
    clock = 0.0
    per_block = max(1, max_layers)
    for module, duration in zip(modules, durations):
        title_span = min(3.0, duration * 0.12)
        cues.append((clock, clock + title_span, module.chapter_title.upper()))
        lines = module.lines
        blocks = [lines[i : i + per_block] for i in range(0, len(lines), per_block)]
        n_blocks = max(1, len(blocks))
        block_duration = duration / n_blocks
        for b, block_lines in enumerate(blocks):
            per_line = block_duration / max(1, len(block_lines))
            cursor = clock + b * block_duration
            for line in block_lines:
                cues.append((cursor, cursor + per_line, line))
                cursor += per_line
        clock += duration
    return cues


def write_cues(cues: list[tuple[float, float, str]], path: Path) -> None:
    """Write a cue list to an SRT file."""
    blocks = []
    for i, (start, end, text) in enumerate(cues, start=1):
        blocks.append(f"{i}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def write_srt(
    modules: list[Module], durations: list[float], path: Path, max_layers: int = 3
) -> None:
    """Write a full-length SRT covering every module back to back."""
    write_cues(srt_cues(modules, durations, max_layers), path)


def subtitle_style(args: argparse.Namespace) -> str:
    """libass force_style string for burned-in subtitles."""
    return (
        f"FontName=DejaVu Sans,FontSize={args.subtitle_font_size},"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,BorderStyle=3,"
        "Outline=2,Shadow=0,MarginV=60,Alignment=2"
    ).replace(",FontSize=0,", ",")


def write_chapters(modules: list[Module], durations: list[float], path: Path, title: str) -> None:
    lines = [";FFMETADATA1", f"title={title}"]
    clock = 0.0
    for module, duration in zip(modules, durations):
        start_ms = int(round(clock * 1000))
        end_ms = int(round((clock + duration) * 1000))
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={start_ms}",
            f"END={end_ms}",
            f"title={module.chapter_title}",
        ]
        clock += duration
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a chaptered, subtitled subliminal MP4 from a text script.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--script", default=str(DEFAULT_SCRIPT), help="Subliminal text file.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output MP4 path.")
    parser.add_argument("--minutes-per-module", type=float, default=2.0, help="Target duration per module.")
    parser.add_argument("--seconds-per-module", type=float, default=None, help="Override module duration in seconds.")
    parser.add_argument("--repeats", type=int, default=100, help="Loops of every affirmation per module.")
    parser.add_argument("--speed-factor", type=float, default=1.5, help="Minimum playback speed multiplier.")
    parser.add_argument(
        "--max-speed",
        type=float,
        default=0.0,
        help="Cap the speed-up (0 = no cap). When capped, loops are reduced to the "
        "maximum that fit, keeping speech intelligible. Try 3-6 for audible subs.",
    )
    parser.add_argument("--max-layers", type=int, default=3, help="Affirmations mixed at once within a module.")
    parser.add_argument("--voice", default="en", help="espeak-ng voice.")
    parser.add_argument("--wpm", type=int, default=165, help="TTS speed in words per minute.")
    parser.add_argument("--voice-gain", type=float, default=-9.0, help="Voice layer gain in dB.")
    parser.add_argument("--ambience", default=str(DEFAULT_AMBIENCE), help="Ambience/background audio file.")
    parser.add_argument("--ambience-gain", type=float, default=-14.0, help="Ambience gain in dB.")
    parser.add_argument("--no-ambience", action="store_true", help="Skip the ambience bed entirely.")
    parser.add_argument(
        "--rain",
        default="",
        help="Rain layer file (looped). Empty = off. Try audio/rain.mp3.",
    )
    parser.add_argument("--rain-gain", type=float, default=-16.0, help="Rain layer gain in dB.")
    parser.add_argument(
        "--theta-hz",
        type=float,
        default=0.0,
        help="Binaural theta beat in Hz (4-8). 0 = off. Try 6.",
    )
    parser.add_argument("--theta-gain", type=float, default=-30.0, help="Theta tone gain in dB.")

    parser.add_argument("--resolution", default="1920x1080", help="WIDTHxHEIGHT, e.g. 1080x1920 for vertical.")
    parser.add_argument("--fps", type=int, default=30, help="Video frame rate.")
    parser.add_argument("--images-per-module", type=int, default=4, help="Images shown per module.")
    parser.add_argument("--image-source", choices=["auto", "local", "pexels", "bing", "picsum"], default="auto")
    parser.add_argument(
        "--image-manifest",
        type=Path,
        default=None,
        help="Per-module image list ('## MODULE TITLE' then image paths). Wins over search/local.",
    )
    parser.add_argument("--pexels-key", default=os.environ.get("PEXELS_API_KEY", ""), help="Pexels API key.")
    parser.add_argument("--transition", choices=["xfade", "fade", "none"], default="xfade")
    parser.add_argument("--transition-seconds", type=float, default=1.2, help="Cross-fade length in seconds.")
    parser.add_argument("--ken-burns", dest="ken_burns", action="store_true", default=True)
    parser.add_argument("--no-ken-burns", dest="ken_burns", action="store_false")
    parser.add_argument("--show-titles", dest="show_titles", action="store_true", default=True)
    parser.add_argument("--no-show-titles", dest="show_titles", action="store_false")
    parser.add_argument("--preset", default="veryfast", help="libx264 preset.")
    parser.add_argument("--crf", type=int, default=23, help="libx264 CRF quality (lower = better).")
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Modules rendered in parallel (1 = sequential). 3-4 is much faster "
             "on a multi-core box because each module is one long ffmpeg job.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=0,
        help="x264 threads per module (0 = auto). Use 1 when running several "
             "modules in parallel.",
    )

    parser.add_argument("--subtitle-mode", choices=["soft", "burn", "both", "none"], default="soft")
    parser.add_argument("--subtitle-font-size", type=int, default=0, help="Burn-in font size (0 = auto).")

    parser.add_argument("--modules", default="", help="Comma-separated module numbers to include.")
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Render layered audio only (skip images/video). Fast; good for marathon loops.",
    )
    parser.add_argument("--title", default="APEX PROTOCOL — GOD MODE SUBLIMINAL", help="Video title metadata.")
    parser.add_argument(
        "--reuse-video-dir",
        default="",
        help="Skip image/video rendering and reuse video_XX.mp4 segments from this folder.",
    )
    parser.add_argument(
        "--audio-file",
        default="",
        help="Use an existing audio file instead of rendering affirmations. "
             "Its duration should match the total module duration.",
    )
    parser.add_argument("--seed", type=int, default=int(time.time()) % 100000, help="Random seed for image order.")
    parser.add_argument("--fade-out", type=float, default=0.0,
                        help="Fade the finished audio out over the last N seconds "
                             "(0 = off). Stops the music ending abruptly.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan and exit.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary working files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    random.seed(args.seed)

    try:
        args.width, args.height = (int(x) for x in args.resolution.lower().split("x"))
    except Exception:
        die("--resolution must look like 1920x1080")

    for tool in ("ffmpeg", "ffprobe", "espeak-ng"):
        if not shutil.which(tool):
            die(f"missing required program '{tool}'. Install: sudo apt install ffmpeg espeak-ng")

    if args.subtitle_mode in ("burn", "both") and "libass" not in run(
        ["ffmpeg", "-hide_banner", "-version"], "checking ffmpeg build"
    ).stdout:
        log("[WARN] ffmpeg build may lack libass; burn-in subtitles might fail.")

    modules = parse_script(Path(args.script).expanduser())
    if args.modules.strip():
        wanted = {int(p) for p in re.split(r"[,\s]+", args.modules.strip()) if p}
        modules = [m for m in modules if m.number in wanted]
        if not modules:
            die("no modules matched --modules selection")

    duration = args.seconds_per_module or args.minutes_per_module * 60.0
    total = duration * len(modules)

    font = find_font()
    pool = local_images() if args.image_source in ("auto", "local") else []
    manifest = load_image_manifest(args.image_manifest) if args.image_manifest else None
    ambience = None if args.no_ambience else build_ambience(Path(args.ambience).expanduser(), int(duration))
    rain = Path(args.rain).expanduser() if args.rain else None
    if rain is not None and not rain.exists():
        die(f"rain file not found: {rain}")
    theta = build_theta(args.theta_hz)

    log("=" * 72)
    log("SUB-VIDEO GENERATOR")
    log("=" * 72)
    log(f"[INFO] Script:            {args.script}")
    log(f"[INFO] Modules:           {len(modules)}")
    log(f"[INFO] Duration/module:   {duration:g}s  (total {total / 60:.1f} min)")
    log(f"[INFO] Affirmation loops: {args.repeats:,} per line")
    log(f"[INFO] Layering:          up to {args.max_layers} lines mixed at once")
    log(f"[INFO] Resolution:        {args.width}x{args.height} @ {args.fps}fps")
    log(f"[INFO] Images/module:     {args.images_per_module}  (source: {args.image_source})")
    log(f"[INFO] Subtitles:         {args.subtitle_mode}")
    log(f"[INFO] Ambience:          {ambience if ambience else 'none'}")
    log(f"[INFO] Rain layer:        {rain if rain else 'none'}"
        + (f"  ({args.rain_gain:g} dB)" if rain else ""))
    log(f"[INFO] Theta layer:       "
        + (f"{args.theta_hz:g} Hz binaural ({args.theta_gain:g} dB)" if theta else "none"))
    log(f"[INFO] Voice layer:       {args.voice_gain:g} dB (subliminal when under the bed)")
    log(f"[INFO] Curated images:    {len(pool)} found in {IMAGES_DIR}")
    log(f"[INFO] Output:            {args.out}")
    log("")

    if args.dry_run:
        for module in modules:
            log(
                f"  [{module.number:02d}] {module.chapter_title} "
                f"({len(module.lines)} affirmations, {duration:g}s)"
            )
        log("\n[DRY-RUN] Nothing was generated.")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    temp_root = Path(tempfile.mkdtemp(prefix="subvideo_", dir=str(CACHE_DIR)))
    workdir = temp_root
    video_segments: list[Path] = []
    audio_segments: list[Path] = []

    try:
        burn = args.subtitle_mode in ("burn", "both")
        soft = args.subtitle_mode in ("soft", "both")
        jobs = max(1, args.jobs)

        def render_video(module: Module, module_index: int) -> Path:
            log(f"── Module {module.number:02d}: {module.chapter_title} " + "─" * 20)
            images = ensure_images(module, module.number, args.images_per_module, args, pool, manifest)

            title_file = workdir / f"title_{module.number:02d}.txt"
            title_file.write_text(module.chapter_title, encoding="utf-8")

            # Burn the subtitles per module so the finished movie never needs
            # a second full-length video encode.
            module_srt = None
            if burn:
                module_srt = workdir / f"srt_{module.number:02d}.srt"
                write_cues(
                    srt_cues([module], [duration], args.max_layers), module_srt
                )

            video_segment = workdir / f"video_{module.number:02d}.mp4"
            build_module_video(
                images, duration, video_segment, args, module.chapter_title,
                font, title_file, module_srt,
            )
            return video_segment

        def render_audio(module: Module, module_index: int) -> Path:
            log(f"── Module {module.number:02d}: {module.chapter_title} " + "─" * 20)
            voice_wavs = []
            for line in module.lines:
                voice_wavs.append(synth_line(speech_text(line), args.voice, args.wpm))

            audio_segment = workdir / f"audio_{module.number:02d}.m4a"
            build_module_audio(
                module.lines, voice_wavs, audio_segment, duration, args, ambience,
                rain=rain, theta=theta,
                ambience_offset=module_index * duration,
            )
            return audio_segment

        def run_stage(label: str, work, module_list: list[Module]) -> list[Path]:
            """Run one build stage, optionally several modules at a time."""
            results: list[Path] = []
            if jobs == 1:
                for module_index, module in enumerate(module_list):
                    results.append(work(module, module_index))
                return results
            log(f"[{label}] rendering {len(module_list)} module(s) with {jobs} workers...")
            with ThreadPoolExecutor(max_workers=jobs) as executor:
                futures = [
                    executor.submit(work, module, module_index)
                    for module_index, module in enumerate(module_list)
                ]
                for future in as_completed(futures):
                    results.append(future.result())
            results.sort(key=lambda p: int(p.stem.split("_")[1]))
            return results

        if not args.audio_only:
            if args.reuse_video_dir:
                reuse_dir = Path(args.reuse_video_dir).expanduser().resolve()
                video_segments = []
                for module in modules:
                    segment = reuse_dir / f"video_{module.number:02d}.mp4"
                    if not segment.exists():
                        die(f"missing reused video segment: {segment}")
                    video_segments.append(segment)
                log(f"[1/6 VIDEO] reusing {len(video_segments)} segment(s) from {reuse_dir}")
            else:
                video_segments = run_stage("1/6 VIDEO", render_video, modules)

        durations = [duration] * len(modules)

        if args.audio_file:
            provided_audio = Path(args.audio_file).expanduser().resolve()
            if not provided_audio.exists():
                die(f"audio file not found: {provided_audio}")
            log(f"[2/6 AUDIO] using existing audio: {provided_audio}")
            if provided_audio.suffix.lower() == ".mp3":
                full_audio = workdir / "provided_audio.m4a"
                run(
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
                        "-i", str(provided_audio),
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                        str(full_audio),
                    ],
                    "converting provided audio to AAC",
                )
            else:
                full_audio = provided_audio
            audio_segments = []
        else:
            audio_segments = run_stage("2/6 AUDIO", render_audio, modules)

        if args.audio_only:
            log("[2/3] Concatenating module audio...")
            if not args.audio_file:
                full_audio = workdir / "full_audio.m4a"
                concat_streams(audio_segments, full_audio, workdir, "audio")
                full_audio = apply_fade_out(full_audio, total, args.fade_out, workdir)

            log("[3/3] Writing chapters and metadata...")
            chapters_path = workdir / "chapters.ffmeta"
            write_chapters(modules, durations, chapters_path, args.title)
            run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(full_audio),
                    "-f", "ffmetadata", "-i", str(chapters_path),
                    "-map", "0:a:0", "-map_chapters", "1", "-map_metadata", "1",
                    "-c", "copy", "-movflags", "+faststart", str(out_path),
                ],
                "writing final audio file",
            )
            probe = run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
                 "-of", "default=noprint_wrappers=1", str(out_path)],
                "verifying output",
            )
            log("")
            log("=" * 72)
            log("[SUCCESS] Layered audio generated.")
            log(f"[AUDIO]   {out_path}")
            log(f"[DETAIL]  {probe.stdout.strip().replace(chr(10), ' | ')}")
            log(f"[LOOPS]   {args.repeats:,} per affirmation | {len(modules)} module(s)")
            log("=" * 72)
            return 0

        log("[3/6] Concatenating module videos...")
        full_video = workdir / "full_video.mp4"
        concat_streams(video_segments, full_video, workdir, "video")

        if not args.audio_file:
            log("[4/6] Concatenating module audio...")
            full_audio = workdir / "full_audio.m4a"
            concat_streams(audio_segments, full_audio, workdir, "audio")
            full_audio = apply_fade_out(full_audio, total, args.fade_out, workdir)

        log("[7/7] Writing subtitles, chapters, and muxing final MP4...")
        srt_path = workdir / "subtitles.srt"
        write_srt(modules, durations, srt_path, args.max_layers)
        external_srt = out_path.with_suffix(".srt")
        shutil.copyfile(srt_path, external_srt)

        chapters_path = workdir / "chapters.ffmeta"
        write_chapters(modules, durations, chapters_path, args.title)

        mux = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-nostdin",
               "-i", str(full_video), "-i", str(full_audio)]
        burn = args.subtitle_mode in ("burn", "both")
        soft = args.subtitle_mode in ("soft", "both")

        if burn or soft:
            mux += ["-i", str(srt_path)]
        chapter_input = len([a for a in mux if a == "-i"])
        mux += ["-f", "ffmetadata", "-i", str(chapters_path)]

        mux += ["-map", "0:v:0", "-map", "1:a:0"]
        if soft:
            mux += ["-map", "2:s:0"]
        mux += ["-map_chapters", str(chapter_input), "-map_metadata", str(chapter_input)]
        mux += ["-metadata", f"title={args.title}"]
        # Burned-in subtitles were already applied per module, so the video
        # stream is copied straight through instead of being re-encoded.
        mux += ["-c:v", "copy"]
        mux += ["-c:a", "copy"]
        if soft:
            mux += ["-c:s", "mov_text", "-metadata:s:s:0", "language=eng"]
        mux += ["-movflags", "+faststart", str(out_path)]
        run(mux, "muxing final MP4")

        probe = run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size", "-of", "default=noprint_wrappers=1", str(out_path)],
            "verifying output",
        )
        chapters_check = run(
            ["ffprobe", "-v", "error", "-show_chapters", "-of", "csv=p=0", str(out_path)],
            "verifying chapters",
        )

        log("")
        log("=" * 72)
        log("[SUCCESS] Subliminal video generated.")
        log(f"[VIDEO]    {out_path}")
        log(f"[SUBTITLES]{external_srt}")
        log(f"[DETAIL]   {probe.stdout.strip().replace(chr(10), ' | ')}")
        log(f"[CHAPTERS] {len(chapters_check.stdout.strip().splitlines())} chapter markers embedded")
        log(f"[MODULES]  {len(modules)} | [LOOPS] {args.repeats:,} per affirmation")
        log("=" * 72)
        return 0
    finally:
        if args.keep_temp:
            log(f"[INFO] Temporary files kept in {temp_root}")
        else:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())


"""cd sub_gen && python3 sub_video_gen.py   --script gf_manifest_10k.txt   --out output/gf_manifest_10k.mp4   --minutes-per-module 3   --repeats 100   --max-speed 5   --resolution 1920x1080   --images-per-module 4   --subtitle-mode soft   --show-titles"""