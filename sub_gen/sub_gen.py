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
I am in an extraordinary, deeply loving, passionate, loyal, lifelong relationship.

She adores me, she cherishes me, and she prioritizes me above everything.

She loves me with teenage excitement and lifelong depth.

She is gorgeous, a virgin, a Mathur girl, her age is in between 22 to 25, with milky-white glowing skin.

Her face is beautiful, her eyes captivating, her hair luscious.

Her breasts are gorgeous, her ass is shapely, her figure is irresistible.

This relationship is the centre of her life and it is already permanent.

I do not chase. I manifest. She arrives. It is done.


She is my angel, sent to me and to no one else.

She looks like an angel when she walks into a room.

Her voice is soft, her laugh is light, her hands are gentle.

There is a goodness in her that makes every room softer around her.

She is pure in body, pure in mind, and pure in intention.

She has been kept untouched and whole for this one love.

An angel does not search the way she searches. She came for me.


She is obsessed with me, openly and without shame.

She thinks of me in every idle second of every day.

She texts first, and she cannot stop texting.

She talks about me to her friends like I am the best thing in her life.

She counts the hours until she sees me, and they are never long enough.

She imagines my hands, my voice, my arms, and she does not hide it.

When I am quiet she checks on me. When I am gone she calls.

There is no other man in her mind. There has never been one.

She is intensely attracted to me and never pretends otherwise.


Her loyalty is extreme, total, and permanent.

Her commitment is absolute, and it never depends on my mood.

She is faithful in her body, in her mind, and in her mouth.

She never flirts to make me jealous. She does not even consider it.

She defends me to people who have never spoken to me.

She keeps my secrets better than I keep them.

Her word is her bond, and her bond has never been broken.

She chose me once and she chooses me every single day.

Distance, time, family, and money cannot move her off me.

Even if the whole world told her to leave me, she would stay.


She is possessive of me and she does not apologise for it.

She marks her territory with a look, a text, and a hand on my arm.

She asks who I am talking to, and she wants the real answer.

She does not share what is hers. I am hers.

She only gets quiet when someone else gets too close.

Her jealousy is proof of how much she values me.

She claims me in front of everyone and she is proud of it.

Possessive, playful, and utterly certain that I belong to her.


She needs me like air, and she does not hide how much.

She cannot be comfortable without knowing where I am.

She is emotionally available in every hour, especially the hard ones.

She asks for me when the room gets quiet.

She is never lonely when I am in it.

She reaches for me before she reaches for anything else.

She does not need a provider or a hero. She needs me.

Being without me makes her restless, and she tells me so.

She is complete with me and unfinished without me.

She breathes easier when I am near.


She blushes the moment she hears my name.

She calls me twenty-five times a day because she genuinely loves talking to me.

She shares every little life update with me first, always.

She tells me where she is, what she wants, and what she feels.

She dreams of our beautiful future together, every single night.

She encourages me, supports me, and celebrates me.

She says my name like it is the only word she wants to use.

Her voice on the phone is the sound I want to fall asleep to.

She says she loves me so easily that I have stopped doubting it.


She showers me with kisses, hugs, cuddles, and affection.

She sits on my lap and plays with my hair while I talk.

She holds me close and she never lets go first.

She constantly finds sweet excuses to kiss me and to touch me.

Her skin is warm, milky-white, and soft under my hands.

She initiates intimacy with joy, and she is never shy with me.

She pulls me close in a crowded room and does not care who sees.

She kisses me like she is confirming something, not starting it.

The chemistry between us is overwhelming, and it never settles.


She buys me thoughtful gifts and never reminds me of them.

She spends generously on me and keeps no score.

She surprises me with roses when I am tired.

She plans romantic dates and remembers every detail of them.

She remembers the little things I said once and acts on them.

She anticipates my needs and meets them before I speak.

She initiates dates, adventures, quality time, and long conversations.

She does all of it freely, joyfully, without ever being asked.

Her generosity is not a transaction. It is love with hands.


We share extraordinary compatibility in every single dimension.

Our communication is honest, direct, and completely safe.

We have complete trust, with no jealousy, no suspicion, and no games.

We hold mutual respect as the foundation of everything.

Our boundaries are healthy, and they protect the relationship.

We are loyal to each other in front of family and behind closed doors.

Our bond carries the devotion of Ram and Sita.

Our love holds the eternal fire of Shiv and Parvati.

Our relationship is full of laughter, passion, peace, prosperity, spiritual connection.


Every day she freely chooses me, and every day she loves me more.

She is wholeheartedly devoted, with nothing of herself held back.

She supports my dreams like they are her own.

She celebrates my success louder than I do.

She builds our beautiful future with me, brick by brick.

She is proud to be with me in front of everyone.

She makes our days warmer than they would ever be without her.

She is the reason I am becoming the man I have already described.

She and I are doing this in the exact way I always imagined.

This relationship is even more magical than I ever imagined.
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
            command = ["ffmpeg", "-hide_banner", "-y"]
            if include_rain:
                command += ["-stream_loop", "-1", "-i", str(selected_rain)]
            for voice_path in voice_paths:
                command += ["-i", str(voice_path)]

            # Voice input indices begin at 1 with rain, or 0 without rain.
            offset = 1 if include_rain else 0
            adjusted_filters = []
            adjusted_labels = []
            for i, voice_path in enumerate(voice_paths):
                sample_count, _ = wav_info(voice_path)
                source_seconds = sample_count / wav_info(voice_path)[1]
                required_factor = (source_seconds * args.repeats) / duration_seconds
                effective_factor = max(args.speed_factor, required_factor)
                remaining = effective_factor
                tempos = []
                while remaining > 2.0:
                    tempos.append("atempo=2.0")
                    remaining /= 2.0
                tempos.append(f"atempo={remaining:.6f}")
                label = f"v{i}"
                adjusted_filters.append(
                    f"[{i + offset}:a]aloop=loop={args.repeats - 1}:size={sample_count},"
                    f"{','.join(tempos)},atrim=duration={duration_seconds},"
                    f"asetpts=PTS-STARTPTS,volume={args.voice_gain}dB,"
                    f"aresample=44100,aformat=channel_layouts=stereo[{label}]"
                )
                adjusted_labels.append(f"[{label}]")
            if include_rain:
                adjusted_filters.insert(0, f"[0:a]atrim=duration={duration_seconds},asetpts=PTS-STARTPTS,volume={args.rain_gain}dB,aresample=44100,aformat=channel_layouts=stereo[rain]")
                mix_labels = ["[rain]"] + adjusted_labels
            else:
                mix_labels = adjusted_labels
            adjusted_filters.append(
                "".join(mix_labels) +
                f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0,"
                f"alimiter=limit=0.95,atrim=duration={duration_seconds}[out]"
            )
            command += [
                "-filter_complex", ";".join(adjusted_filters), "-map", "[out]",
                "-t", str(duration_seconds), "-c:a", "libmp3lame", "-b:a", "192k",
                "-metadata", f"title={'Layered Affirmations - Rain' if include_rain else 'Affirmations Only'}",
                str(destination)
            ]
            run(command, f"exporting {destination.name}")

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
