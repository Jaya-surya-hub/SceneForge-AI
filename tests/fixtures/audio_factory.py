"""In-memory audio fixture factory for tests.

Generates synthetic WAV bytes using only stdlib — no ffmpeg, no disk writes,
no network calls. Import this module in tests instead of reading fixture files.

All fixtures are deterministic and reproducible.
"""

from __future__ import annotations

import math
import struct


def _build_wav(samples: list[int], sample_rate: int = 22050) -> bytes:
    """Build a 16-bit mono PCM WAV from a list of integer samples."""
    data = struct.pack(f"<{len(samples)}h", *samples)
    data_size = len(data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,           # PCM
        1,           # mono
        sample_rate,
        sample_rate * 2,
        2,           # block align
        16,          # bits per sample
        b"data",
        data_size,
    )
    return header + data


def silence_wav(duration: float = 5.0, sample_rate: int = 22050) -> bytes:
    """Return WAV bytes containing digital silence (all zeros).

    This represents an audio file with no signal whatsoever — used for HC-09.
    """
    n = int(duration * sample_rate)
    return _build_wav([0] * n, sample_rate)


def tone_wav(
    freq: float = 440.0,
    duration: float = 5.0,
    sample_rate: int = 22050,
    amplitude: int = 16000,
) -> bytes:
    """Return WAV bytes containing a pure sine tone.

    Represents a continuous music/tone signal with no speech dynamics (HC-10).
    The silence ratio will be very low, triggering the music-only heuristic.
    """
    n = int(duration * sample_rate)
    samples = [
        int(amplitude * math.sin(2 * math.pi * freq * i / sample_rate))
        for i in range(n)
    ]
    return _build_wav(samples, sample_rate)


def speech_like_wav(duration: float = 3.0, sample_rate: int = 22050) -> bytes:
    """Return WAV bytes simulating speech dynamics.

    Alternates between bursts of tone and silence to approximate the
    pause patterns of natural speech.
    """
    samples: list[int] = []
    burst_duration = 0.3   # seconds of "speech"
    pause_duration = 0.15  # seconds of silence between bursts

    t = 0.0
    while t < duration:
        # Burst
        burst_samples = int(burst_duration * sample_rate)
        for i in range(burst_samples):
            samples.append(int(8000 * math.sin(2 * math.pi * 200 * i / sample_rate)))
        t += burst_duration
        # Pause
        pause_samples = int(pause_duration * sample_rate)
        samples.extend([0] * pause_samples)
        t += pause_duration

    # Trim to exact duration
    target = int(duration * sample_rate)
    samples = samples[:target]
    if len(samples) < target:
        samples.extend([0] * (target - len(samples)))

    return _build_wav(samples, sample_rate)


def corrupted_bytes() -> bytes:
    """Return bytes that start like a WAV header but are then truncated/invalid."""
    return b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00"


def empty_bytes() -> bytes:
    """Return empty bytes (zero-length upload)."""
    return b""


def wrong_type_bytes() -> bytes:
    """Return plain text bytes (wrong file type — not audio)."""
    return b"This is plain text content, not an audio file.\n"


def mp3_magic_bytes() -> bytes:
    """Return bytes starting with the MP3 ID3 magic header (minimal)."""
    # ID3 tag header + enough padding to pass size check
    return b"ID3\x03\x00\x00" + b"\x00" * 100


def ogg_magic_bytes() -> bytes:
    """Return bytes starting with the OGG magic header."""
    return b"OggS" + b"\x00" * 100
