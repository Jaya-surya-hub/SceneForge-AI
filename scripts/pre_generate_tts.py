#!/usr/bin/env python3
"""Pre-generate TTS audio on the host for use inside Docker.

Edge-tts may be blocked inside Docker due to NAT restrictions.
This script runs on the host (where edge-tts works) and writes the
audio to a path accessible from Docker (e.g. the shared storage volume).

Usage:
  python scripts/pre_generate_tts.py --text "Innovation drives progress." --output /path/audio.mp3
  python scripts/pre_generate_tts.py --text "..." --output ./storage/tts/audio.mp3

The generated file is a real MP3 with audible speech — not a mock.
"""

import argparse
import asyncio
import io
import os
import sys


async def generate_tts(text: str, voice: str, output_path: str) -> int:
    """Generate TTS audio and write to output_path. Returns byte count."""
    import edge_tts

    buf = io.BytesIO()
    comm = edge_tts.Communicate(text, voice)
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])

    data = buf.getvalue()
    if not data:
        print("ERROR: edge-tts produced 0 bytes", file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)

    print(f"OK: {len(data)} bytes written to {output_path}")
    print(f"Voice: {voice}")
    print(f"Text: {text[:80]}{'...' if len(text) > 80 else ''}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-generate TTS audio")
    parser.add_argument("--text", required=True, help="Narration text")
    parser.add_argument("--output", required=True, help="Output MP3 path")
    parser.add_argument("--voice", default="en-US-AriaNeural",
                        help="Voice name (default: en-US-AriaNeural)")
    args = parser.parse_args()

    return asyncio.run(generate_tts(args.text, args.voice, args.output))


if __name__ == "__main__":
    sys.exit(main())
