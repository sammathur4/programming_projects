"""Generate the mala-completion bell as a 16-bit mono WAV.

A temple bell is not a sine: it is a struck metal shell, so it has a strong
fundamental plus inharmonic partials (1.0, 2.0, 2.76, 5.4, 8.9 ...) that decay
at different rates, and a fast attack. Everything is synthesised here so the
app ships one small asset and no recorded audio.

    python3 make_bell.py assets/sounds/bell.wav
"""
import math
import struct
import sys
import wave

SAMPLE_RATE = 44100
DURATION = 2.2

# (frequency ratio, amplitude, decay rate) — a struck bell spectrum.
# The upper partials die away faster, which is what makes it read as "bell"
# rather than "tone".
PARTIALS = [
    (1.000, 1.00, 1.6),    # hum / fundamental
    (2.000, 0.62, 2.1),    # prime
    (2.756, 0.42, 2.6),    # tierce (the characteristic bell "strike")
    (4.164, 0.24, 3.2),    # quint
    (5.404, 0.16, 4.0),    # nominal
    (6.796, 0.10, 5.0),    # upper
    (8.933, 0.06, 6.2),    # very upper
]


def build(freq=432.0):
    n = int(SAMPLE_RATE * DURATION)
    out = []
    for i in range(n):
        t = i / SAMPLE_RATE
        s = 0.0
        for ratio, amp, decay in PARTIALS:
            s += amp * math.sin(2 * math.pi * freq * ratio * t) * math.exp(-decay * t)
        # fast attack (3 ms) so it reads as struck, not bowed
        attack = min(1.0, t / 0.003)
        # gentle overall fade so the tail cannot click at the end
        tail = 1.0 if t < DURATION - 0.25 else max(0.0, (DURATION - t) / 0.25)
        s = s * attack * tail
        out.append(s)
    peak = max(abs(v) for v in out) or 1.0
    # normalise to -1.5 dBFS so it is loud but never clips
    scale = 0.84 / peak
    return [max(-1.0, min(1.0, v * scale)) for v in out]


def main(path):
    samples = build()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        frames = b"".join(struct.pack("<h", int(v * 32767)) for v in samples)
        w.writeframes(frames)
    print(f"wrote {path} ({len(samples)} samples, {DURATION}s, {SAMPLE_RATE}Hz)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bell.wav")
