"""Download Roboto Regular font (Apache 2.0) for FFmpeg drawtext.

Run during Docker build: python /app/scripts/install_font.py
"""
import os
import urllib.request

FONT_URL = (
    "https://github.com/googlefonts/roboto/raw/main/src/hinted/Roboto-Regular.ttf"
)
FONT_DEST = "/usr/local/share/fonts/Roboto-Regular.ttf"


def main() -> None:
    os.makedirs(os.path.dirname(FONT_DEST), exist_ok=True)
    print(f"Downloading Roboto Regular from GitHub...", flush=True)
    req = urllib.request.Request(FONT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r, open(FONT_DEST, "wb") as f:
        data = r.read()
        f.write(data)
    print(f"Font installed: {FONT_DEST} ({len(data)} bytes)", flush=True)


if __name__ == "__main__":
    main()
