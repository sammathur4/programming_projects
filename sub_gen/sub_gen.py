#!/usr/bin/env python3
"""
Generate sentence-level affirmation audio over rain ambience.

Requirements:
  sudo apt install ffmpeg espeak-ng
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install pydub

Run:
  python3 potent_subliminal.py
  python3 potent_subliminal.py --minutes 5 --repeats 10

Every sentence is made into its own voice track. Each track is repeated the
requested number of times, accelerated if necessary to fit the requested
duration, and mixed with the other tracks. Headings and blank lines are ignored.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "audio"
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_RAIN = AUDIO_DIR / "rain.mp3"
DEFAULT_OUTPUT = OUTPUT_DIR / "manifestation_layered_subliminal.mp3"
DEFAULT_DUB_OUTPUT = OUTPUT_DIR / "affirmations_dub_only.mp3"

DEFAULT_AFFIRMATIONS_TEXT = r"""

"""


def run(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
    print(f"[RUN] {label}")
    try:
        result = subprocess.run(command, text=True, capture_output=True)
    except FileNotFoundError:
        print(f"[ERROR] Required executable not found: {command[0]}")
        print("        Install dependencies with: sudo apt install ffmpeg espeak-ng")
        raise SystemExit(1)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "No error details returned.").strip()
        print(f"[ERROR] {label} failed (exit code {result.returncode}).")
        print(detail[-4000:])
        raise SystemExit(result.returncode)
    return result


def split_sentences(content: str) -> list[str]:
    """Remove headings/comments and split paragraphs into sentence-level tracks."""
    cleaned_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cleaned_lines.append(stripped)
    content = " ".join(cleaned_lines)
    content = re.sub(r"\s+", " ", content).strip()
    if not content:
        return []
    # Split after sentence-ending punctuation when the next sentence begins.
    sentences = re.split(r'(?<=[.!?])\s+(?=[\\"“‘(]*[A-Z0-9])', content)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def load_affirmations(path: Path) -> list[str]:
    if path.exists():
        custom_text = path.read_text(encoding="utf-8")
        affirmations = split_sentences(custom_text)
        if affirmations:
            print(f"[INFO] Loaded and split custom text into {len(affirmations)} sentence(s) from {path}.")
            return affirmations
        print(f"[WARN] {path} is empty; using built-in affirmations.")
    else:
        print(f"[INFO] No custom affirmation file at {path}; using built-in affirmations.")
    affirmations = split_sentences(DEFAULT_AFFIRMATIONS_TEXT)
    print(f"[INFO] Built-in text split into {len(affirmations)} sentence(s).")
    return affirmations


def make_voice(sentence: str, destination: Path, voice: str, wpm: int, index: int, total: int) -> None:
    print(f"[VOICE {index}/{total}] {sentence}")
    run(
        ["espeak-ng", "-v", voice, "-s", str(wpm), "-w", str(destination), sentence],
        f"generating sentence {index}/{total}",
    )


def wav_info(path: Path) -> tuple[int, int]:
    try:
        with wave.open(str(path), "rb") as wav_file:
            return wav_file.getnframes(), wav_file.getframerate()
    except (wave.Error, OSError) as exc:
        print(f"[ERROR] Could not inspect generated WAV {path}: {exc}")
        raise SystemExit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sentence-level affirmation audio over rain.")
    parser.add_argument("--minutes", type=float, default=30, help="Output duration in minutes (default: 30).")
    parser.add_argument("--repeats", type=int, default=1000, help="Repeats per sentence track (default: 1000).")
    parser.add_argument("--speed-factor", type=float, default=2.0, help="Minimum playback speed multiplier (1.0 to 4.0; may be exceeded to fit repeats).")
    parser.add_argument("--voice-gain", type=float, default=-8.0, help="Volume adjustment per affirmation layer in dB.")
    parser.add_argument("--rain-gain", type=float, default=-12.0, help="Rain volume adjustment in dB.")
    parser.add_argument("--voice", default="en", help="espeak-ng voice, e.g. en, en-us, en-gb.")
    parser.add_argument("--wpm", type=int, default=165, help="Speech synthesis speed in words/minute.")
    parser.add_argument("--affirmations-file", default=str(BASE_DIR / "affirmations.txt"), help="Optional text file; sentences are split automatically.")
    parser.add_argument("--rain-file", default=str(DEFAULT_RAIN), help="Rain recording path (optional).")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Mixed rain + affirmations MP3 path.")
    parser.add_argument("--dub-output", default=str(DEFAULT_DUB_OUTPUT), help="Affirmation-only MP3 path.")
    parser.add_argument("--batch-size", type=int, default=32, help="Number of sentence tracks mixed per ffmpeg batch to stay under OS argument limits (default: 32).")
    args = parser.parse_args()

    if not (0 < args.minutes <= 1440):
        parser.error("--minutes must be greater than 0 and no more than 1440.")
    if not (1 <= args.repeats <= 100000):
        parser.error("--repeats must be between 1 and 100000.")
    if not (1.0 <= args.speed_factor <= 4.0):
        parser.error("--speed-factor must be between 1.0 and 4.0.")
    if not (-60 <= args.voice_gain <= 12 and -60 <= args.rain_gain <= 12):
        parser.error("gain values must be between -60 and +12 dB.")
    if not (80 <= args.wpm <= 350):
        parser.error("--wpm must be between 80 and 350.")
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1.")

    missing = [tool for tool in ("ffmpeg", "ffprobe", "espeak-ng") if not shutil.which(tool)]
    if missing:
        print(f"[ERROR] Missing required program(s): {', '.join(missing)}")
        print("        Install with: sudo apt install ffmpeg espeak-ng")
        return 1

    affirmations = load_affirmations(Path(args.affirmations_file).expanduser())
    if not affirmations:
        print("[ERROR] No affirmation sentences found.")
        return 1

    duration_seconds = int(args.minutes * 60)
    output = Path(args.output).expanduser().resolve()
    dub_output = Path(args.dub_output).expanduser().resolve()
    rain_path = Path(args.rain_file).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    dub_output.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("SENTENCE-LEVEL AFFIRMATION AUDIO GENERATOR")
    print("=" * 72)
    print(f"[INFO] Output duration:      {args.minutes:g} minutes")
    print(f"[INFO] Sentence tracks:      {len(affirmations)}")
    print(f"[INFO] Repeats per sentence: {args.repeats:,}")
    print(f"[INFO] Total repetitions:    {len(affirmations) * args.repeats:,}")
    print(f"[INFO] Minimum speed factor: {args.speed_factor:g}x")

    with tempfile.TemporaryDirectory(prefix="sentence_affirmations_") as temp_name:
        temp_dir = Path(temp_name)
        voice_paths: list[Path] = []
        print("\n[1/4] Generating one WAV per sentence...")
        for i, sentence in enumerate(affirmations, start=1):
            voice_path = temp_dir / f"voice_{i:04d}.wav"
            make_voice(sentence, voice_path, args.voice, args.wpm, i, len(affirmations))
            voice_paths.append(voice_path)

        if rain_path.exists():
            selected_rain = rain_path
            print(f"\n[2/4] Using rain background: {selected_rain}")
        else:
            selected_rain = temp_dir / "generated_pink_noise.wav"
            print(f"\n[WARN] Rain file not found: {rain_path}")
            print("[INFO] Creating a pink-noise fallback. For realistic rain, add audio/rain.mp3.")
            run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"anoisesrc=color=pink:sample_rate=44100:duration={duration_seconds}",
                "-af", "highpass=f=350,lowpass=f=9000", "-ac", "2", str(selected_rain)
            ], "creating fallback noise")

        print("\n[3/4] Building sentence repetition and mixing filters...")
        voice_filters = []
        labels = []
        for i, voice_path in enumerate(voice_paths):
            sample_count, sample_rate = wav_info(voice_path)
            source_seconds = sample_count / sample_rate
            required_factor = (source_seconds * args.repeats) / duration_seconds
            effective_factor = max(args.speed_factor, required_factor)
            remaining = effective_factor
            tempo_filters = []
            while remaining > 2.0:
                tempo_filters.append("atempo=2.0")
                remaining /= 2.0
            tempo_filters.append(f"atempo={remaining:.6f}")
            label = f"v{i}"
            print(f"[LAYER {i + 1}/{len(voice_paths)}] {source_seconds:.2f}s source; {effective_factor:.2f}x effective speed")
            voice_filters.append(
                f"[{i}:a]aloop=loop={args.repeats - 1}:size={sample_count},"
                f"{','.join(tempo_filters)},atrim=duration={duration_seconds},"
                f"asetpts=PTS-STARTPTS,volume={args.voice_gain}dB,"
                f"aresample=44100,aformat=channel_layouts=stereo[{label}]"
            )
            labels.append(f"[{label}]")

        def export_audio(include_rain: bool, destination: Path) -> None:
            batch_size = max(1, args.batch_size)
            current_mix: Path | None = None
            for batch_index, start in enumerate(range(0, len(voice_paths), batch_size)):
                batch = voice_paths[start:start + batch_size]
                temp_output = temp_dir / f"mix_{'rain' if include_rain else 'dub'}_{batch_index:03d}.wav"
                command = ["ffmpeg", "-hide_banner", "-y"]
                if current_mix is not None:
                    command += ["-i", str(current_mix)]
                if include_rain and current_mix is None:
                    command += ["-stream_loop", "-1", "-i", str(selected_rain)]
                for voice_path in batch:
                    command += ["-i", str(voice_path)]

                filters = []
                mix_labels = []
                next_input = 0
                if include_rain and current_mix is None:
                    filters.append(f"[0:a]atrim=duration={duration_seconds},asetpts=PTS-STARTPTS,volume={args.rain_gain}dB,aresample=44100,aformat=channel_layouts=stereo[rain]")
                    mix_labels.append("[rain]")
                    next_input = 1
                if current_mix is not None:
                    filters.append(f"[{next_input}:a]atrim=duration={duration_seconds},asetpts=PTS-STARTPTS,aresample=44100,aformat=channel_layouts=stereo[prev]")
                    mix_labels.append("[prev]")
                    next_input += 1

                for i, voice_path in enumerate(batch):
                    sample_count, sample_rate = wav_info(voice_path)
                    source_seconds = sample_count / sample_rate
                    required_factor = (source_seconds * args.repeats) / duration_seconds
                    effective_factor = max(args.speed_factor, required_factor)
                    remaining = effective_factor
                    tempos = []
                    while remaining > 2.0:
                        tempos.append("atempo=2.0")
                        remaining /= 2.0
                    tempos.append(f"atempo={remaining:.6f}")
                    label = f"v{i}"
                    filters.append(
                        f"[{next_input + i}:a]aloop=loop={args.repeats - 1}:size={sample_count},"
                        f"{','.join(tempos)},atrim=duration={duration_seconds},"
                        f"asetpts=PTS-STARTPTS,volume={args.voice_gain}dB,"
                        f"aresample=44100,aformat=channel_layouts=stereo[{label}]"
                    )
                    mix_labels.append(f"[{label}]")

                filters.append("".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0,alimiter=limit=0.95,atrim=duration={duration_seconds}[out]")
                command += [
                    "-filter_complex", ";".join(filters), "-map", "[out]",
                    "-t", str(duration_seconds), "-c:a", "pcm_s16le", str(temp_output)
                ]
                run(command, f"mixing batch {batch_index + 1} for {destination.name}")
                current_mix = temp_output

            if current_mix is None:
                raise SystemExit("No audio batches were produced.")

            if current_mix != destination:
                run([
                    "ffmpeg", "-hide_banner", "-y", "-i", str(current_mix),
                    "-c:a", "libmp3lame", "-b:a", "192k",
                    "-metadata", f"title={'Layered Affirmations - Rain' if include_rain else 'Affirmations Only'}",
                    str(destination)
                ], f"encoding final {destination.name}")

        print("[INFO] Exporting voice-only track...")
        export_audio(False, dub_output)
        print("[INFO] Exporting rain + affirmation mix...")
        export_audio(True, output)

        print("\n[4/4] Verifying output files...")
        for file_path in (dub_output, output):
            probe = run([
                "ffprobe", "-v", "error", "-show_entries", "format=duration,size",
                "-of", "default=noprint_wrappers=1", str(file_path)
            ], f"verifying {file_path.name}")
            print(f"[FILE] {file_path}")
            print(probe.stdout.strip())

    print("\n[SUCCESS] Audio export completed.")
    print(f"[MIXED] {output}")
    print(f"[DUB]   {dub_output}")
    print(f"[TRACKS] {len(affirmations)} sentence tracks")
    print(f"[LOOPS]  {args.repeats:,} repeats per sentence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
