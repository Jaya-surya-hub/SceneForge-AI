"""Generate synthetic audio test fixtures using only stdlib (no ffmpeg needed).

Run once to create the fixture files:
    python tests/fixtures/make_fixtures.py

Files created:
    silence_5s.wav          — 5 s of digital silence (PCM 16-bit 22050 Hz mono)
    tone_440hz_5s.wav       — 5 s of 440 Hz sine tone (music-only heuristic)
    short_speech_2s.wav     — 2 s of silence (placeholder for STT tests)
    corrupted.bin           — truncated/invalid bytes (not a valid audio file)
    empty.wav               — 0-byte file
    wrong_type.txt          — text file with .txt extension
"""

from __future__ import annotations

import math
import os
import struct
import sys

OUT = os.path.dirname(__file__)


def write_wav(path: str, samples: list[int], sample_rate: int = 22050) -> None:
    """Write a 16-bit mono PCM WAV file."""
    data = struct.pack(f"<{len(samples)}h", *samples)
    data_size = len(data)
    with open(path, "wb") as f:
        f.write(struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + data_size, b"WAVE",
            b"fmt ", 16, 1, 1,
            sample_rate, sample_rate * 2, 2, 16,
            b"data", data_size,
        ))
        f.write(data)


def silence(duration: float, rate: int = 22050) -> list[int]:
    return [0] * int(duration * rate)


def sine(freq: float, duration: float, rate: int = 22050, amp: int = 16000) -> list[int]:
    n = int(duration * rate)
    return [int(amp * math.sin(2 * math.pi * freq * i / rate)) for i in range(n)]


if __name__ == "__main__":
    write_wav(os.path.join(OUT, "silence_5s.wav"), silence(5.0))
    print("Created silence_5s.wav")

    write_wav(os.path.join(OUT, "tone_440hz_5s.wav"), sine(440.0, 5.0))
    print("Created tone_440hz_5s.wav")

    write_wav(os.path.join(OUT, "short_speech_2s.wav"), silence(2.0))
    print("Created short_speech_2s.wav")

    with open(os.path.join(OUT, "corrupted.bin"), "wb") as f:
        f.write(b"RIFF\x00\x00\x00\x00WAVE")  # valid header start, truncated body
    print("Created corrupted.bin")

    with open(os.path.join(OUT, "empty.wav"), "wb") as f:
        pass
    print("Created empty.wav")

    with open(os.path.join(OUT, "wrong_type.txt"), "w") as f:
        f.write("This is a plain text file, not audio.\n")
    print("Created wrong_type.txt")

    print("All fixtures written to", OUT)
