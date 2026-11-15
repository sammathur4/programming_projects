#!/usr/bin/env python3
"""Layered affirmation audio over rain.

One clean sequential spine per layer, layered copies staggered around the loop,
mixed under rain.

Why this replaces simultaneous-mixing of the whole script:
  * each sentence is actually spoken `--reps` times in a row (real repetition)
  * only `--layers` voices overlap, so the words stay decodable
  * layers are rotated around the loop, so there is no burst/pulse
  * the script is cut into chunks, so density stays human

Examples:
  python3 sub_builder.py scripts/manifest_7_nov_2026.txt
  python3 sub_builder.py scripts/manifest_7_nov_2026.txt --chunk-sentences 40 --reps 3 --layers 3 --minutes 20

Requires: espeak-ng, ffmpeg, ffprobe.
"""
from __future__ import annotations

import argparse
import math
import random
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RAIN = BASE_DIR / "audio" / "rain.mp3"


def run(cmd: list[str], label: str) -> None:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()[-3000:]
        raise SystemExit(f"[ERROR] {label} failed (exit {result.returncode})\n{detail}")


def split_sentences(text: str) -> list[str]:
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    content = re.sub(r"\s+", " ", " ".join(lines)).strip()
    if not content:
        return []
    parts = re.split(r'(?<=[.!?])\s+(?=[\\"“‘(]*[A-Z0-9])', content)
    return [p.strip() for p in parts if p.strip()]


def synth(sentence: str, dest: Path, voice: str, wpm: int, pitch: int) -> None:
    run(
        ["espeak-ng", "-v", voice, "-s", str(wpm), "-p", str(pitch), "-w", str(dest), sentence],
        f"espeak: {sentence[:50]}",
    )


def read_wav(path: Path):
    with wave.open(str(path), "rb") as w:
        return w.getparams(), w.readframes(w.getnframes())


def ms_to_bytes(params, milliseconds: float) -> bytes:
    frames = int(params.framerate * milliseconds / 1000.0)
    return b"\x00" * (frames * params.sampwidth * params.nchannels)


def make_block(sentence_wavs: list[Path], reps: int, silence: bytes) -> bytes:
    """One pass of the chunk: every sentence repeated `reps` times, gap after each."""
    parts = []
    for path in sentence_wavs:
        data = read_wav(path)[1]
        for _ in range(reps):
            parts.append(data)
            parts.append(silence)
    return b"".join(parts)


def apply_tempo(block: bytes, params, tempo: float, tmp_dir: Path) -> bytes:
    """Exact 2x playback via atempo (pitch preserved), or passthrough."""
    if tempo == 1.0:
        return block
    src, dst = tmp_dir / "tempo_in.wav", tmp_dir / "tempo_out.wav"
    with wave.open(str(src), "wb") as wf:
        wf.setparams(params)
        wf.writeframes(block)
    run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
         "-filter:a", f"atempo={tempo:g}", "-c:a", "pcm_s16le", str(dst)],
        "atempo",
    )
    return read_wav(dst)[1]


def fit_frames(block: bytes, target_frames: int, frame_bytes: int) -> bytes:
    """Loop the block until it covers target_frames, then truncate/pad exactly."""
    need = target_frames * frame_bytes
    if not block:
        return b"\x00" * need
    loops = math.ceil(need / len(block))
    data = (block * loops)[:need]
    if len(data) < need:
        data += b"\x00" * (need - len(data))
    return data


def mix(
    layer_paths: list[Path],
    rain_path: Path | None,
    out_path: Path,
    duration: float,
    voice_seconds: float,
    voice_gain: float,
    rain_gain: float,
    duck: bool,
    lufs: float,
    fade: float,
) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for p in layer_paths:
        cmd += ["-i", str(p)]
    if rain_path:
        cmd += ["-stream_loop", "-1", "-i", str(rain_path)]

    n = len(layer_paths)
    filters = [f"[{i}:a]aformat=channel_layouts=stereo[v{i}]" for i in range(n)]
    filters.append(
        "".join(f"[v{i}]" for i in range(n))
        + f"amix=inputs={n}:normalize=0:duration=longest,volume={voice_gain}dB"
        + f",afade=t=out:st={max(0.0, voice_seconds - 1.5):.3f}:d=1.5[voice]"
    )
    filters.append("[voice]asplit=2[vout][vkey]" if (rain_path and duck) else "[voice]anull[vout]")

    if rain_path:
        r = n
        filters.append(
            f"[{r}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,"
            f"aformat=channel_layouts=stereo,volume={rain_gain}dB[rain]"
        )
        if duck:
            filters.append("[rain][vkey]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=500[bed]")
        else:
            filters.append("[rain]anull[bed]")
        filters.append("[bed][vout]amix=inputs=2:normalize=0[mix]")
    else:
        filters.append("[vout]anull[mix]")

    tail = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"
    if fade > 0:
        tail += f",afade=t=in:st=0:d={fade},afade=t=out:st={max(0.0, duration - fade)}:d={fade}"
    filters.append(f"[mix]{tail}[out]")

    cmd += [
        "-filter_complex", ";".join(filters), "-map", "[out]",
        "-t", f"{duration:.3f}", "-c:a", "libmp3lame", "-b:a", "192k",
        str(out_path),
    ]
    run(cmd, f"mix {out_path.name}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build layered affirmation audio over rain.")
    ap.add_argument("script", help="Affirmation text file.")
    ap.add_argument("--out-dir", default=str(BASE_DIR / "output"))
    ap.add_argument("--chunk-sentences", type=int, default=40, help="Sentences per file. 0 = whole script in one file.")
    ap.add_argument("--reps", type=int, default=3, help="Sequential repeats per sentence (default 3).")
    ap.add_argument("--layers", type=int, default=3, help="Simultaneous staggered voices (default 3).")
    ap.add_argument("--gap-ms", type=float, default=220, help="Silence after each repetition (default 220).")
    ap.add_argument("--minutes", type=float, default=0, help="Loop each file to at least this many minutes (0 = off).")
    ap.add_argument("--voice", default="en-us", help="Base espeak voice (default en-us).")
    ap.add_argument("--variants", default="m1,m2,m3,m4", help="espeak variants, one per layer (default m1,m2,m3,m4).")
    ap.add_argument("--wpm", type=int, default=165, help="Base speed in words/minute (default 165).")
    ap.add_argument("--tempo", type=float, default=1.0, help="Playback speed multiplier via atempo, pitch kept (2 = 2x).")
    ap.add_argument("--tail", type=float, default=15.0, help="Rain-only outro seconds so the bed never cuts with the voice.")
    ap.add_argument("--pitch-spread", type=int, default=6, help="Pitch offset between layers (default 6).")
    ap.add_argument("--pitch-base", type=int, default=50, help="espeak pitch for the middle layer (50 = voice default).")
    ap.add_argument("--speed-spread", type=float, default=0.03, help="Speed offset between layers (default 0.03).")
    ap.add_argument("--rain", default=str(DEFAULT_RAIN))
    ap.add_argument("--rain-gain", type=float, default=-14.0)
    ap.add_argument("--voice-gain", type=float, default=-3.0)
    ap.add_argument("--no-duck", action="store_true", help="Do not duck rain under the voice.")
    ap.add_argument("--lufs", type=float, default=-16.0)
    ap.add_argument("--fade", type=float, default=2.0)
    ap.add_argument("--shuffle", action="store_true", help="Shuffle sentence order per chunk.")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--layers-dir", default="", help="Save layer WAVs here, and reuse them on the next run (level/mix changes without re-synth).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    for tool in ("espeak-ng", "ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            print(f"[ERROR] missing {tool}. Install with: sudo apt install ffmpeg espeak-ng")
            return 1

    script = Path(args.script).expanduser().resolve()
    sentences = split_sentences(script.read_text(encoding="utf-8"))
    if not sentences:
        print("[ERROR] no sentences found")
        return 1

    size = args.chunk_sentences if args.chunk_sentences > 0 else len(sentences)
    chunks = [sentences[i:i + size] for i in range(0, len(sentences), size)]
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    rain = Path(args.rain).expanduser().resolve()
    rain = rain if rain.exists() else None

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    mid = (args.layers - 1) / 2.0
    pitches = [max(0, min(99, int(args.pitch_base + (k - mid) * args.pitch_spread))) for k in range(args.layers)]
    speeds = [max(80, int(args.wpm * (1 + (k - mid) * args.speed_spread))) for k in range(args.layers)]

    print("=" * 70)
    print(f"script      : {script.name}")
    print(f"sentences   : {len(sentences)}  ->  {len(chunks)} file(s) of <= {size}")
    print(f"layers      : {args.layers}   voices={[args.voice + '+' + variants[k % len(variants)] for k in range(args.layers)]}")
    print(f"pitch/speed : {list(zip(pitches, speeds))}")
    print(f"reps        : {args.reps} per sentence, gap {args.gap_ms:g} ms")
    print(f"tempo/tail  : {args.tempo:g}x atempo, {args.tail:g} s rain-only tail")
    print(f"target      : {'>= ' + str(args.minutes) + ' min each' if args.minutes else 'natural length'}")
    print("=" * 70)
    if args.dry_run:
        return 0

    rng = random.Random(args.seed)
    for index, chunk in enumerate(chunks, 1):
        if args.shuffle:
            chunk = chunk[:]
            rng.shuffle(chunk)
        with tempfile.TemporaryDirectory(prefix="sub_builder_") as tmp:
            tmp_dir = Path(tmp)
            cache = Path(args.layers_dir).expanduser().resolve() if args.layers_dir else None
            layer_paths: list[Path] = []

            if cache and all((cache / f"layer_{k}.wav").exists() for k in range(args.layers)):
                layer_paths = [cache / f"layer_{k}.wav" for k in range(args.layers)]
                params, first = read_wav(layer_paths[0])
                frame_bytes = params.sampwidth * params.nchannels
                target = len(first) // frame_bytes
                print("reusing cached layers (synth flags ignored)")
            else:
                synth_paths: list[list[Path]] = []
                for k in range(args.layers):
                    paths = [tmp_dir / f"L{k}_{i:04d}.wav" for i in range(len(chunk))]
                    synth_paths.append(paths)

                with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                    futures = []
                    for k in range(args.layers):
                        voice = f"{args.voice}+{variants[k % len(variants)]}"
                        for sentence, path in zip(chunk, synth_paths[k]):
                            futures.append(pool.submit(synth, sentence, path, voice, speeds[k], pitches[k]))
                    for f in futures:
                        f.result()

                params, _ = read_wav(synth_paths[0][0])
                gap = ms_to_bytes(params, args.gap_ms)
                frame_bytes = params.sampwidth * params.nchannels
                blocks = [
                    apply_tempo(make_block(synth_paths[k], args.reps, gap), params, args.tempo, tmp_dir)
                    for k in range(args.layers)
                ]
                target = max(len(b) // frame_bytes for b in blocks)
                if args.minutes:
                    target = max(target, int(args.minutes * 60 * params.framerate))

                dest_dir = cache if cache else tmp_dir
                dest_dir.mkdir(parents=True, exist_ok=True)
                for k in range(args.layers):
                    data = fit_frames(blocks[k], target, frame_bytes)
                    blocks[k] = b""
                    if k:
                        shift = int(target * k / args.layers) * frame_bytes
                        data = data[shift:] + data[:shift]
                    out = dest_dir / f"layer_{k}.wav"
                    with wave.open(str(out), "wb") as wf:
                        wf.setparams(params)
                        wf.writeframes(data)
                    layer_paths.append(out)

            duration = target / params.framerate
            total = duration + args.tail
            name = f"{script.stem}"
            name += f"_{index:02d}" if len(chunks) > 1 else ""
            dest = out_dir / f"{name}.mp3"
            print(f"[{index}/{len(chunks)}] {len(chunk)} sentences, {total/60:.1f} min -> {dest.name}")
            mix(
                layer_paths, rain, dest, total, duration,
                args.voice_gain, args.rain_gain, not args.no_duck, args.lufs, args.fade,
            )

    print(f"\nDone. Files in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
