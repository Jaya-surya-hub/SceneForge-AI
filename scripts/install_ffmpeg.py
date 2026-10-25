"""Docker build helper: download and install static FFmpeg binary.

Run inside the Docker build (RUN python /app/scripts/install_ffmpeg.py).
Downloads from BtbN/FFmpeg-Builds (GPL build) on GitHub via HTTPS.
"""
import os
import shutil
import sys
import tarfile
import urllib.request


FFMPEG_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-linux64-gpl.tar.xz"
)


def main() -> int:
    print("Downloading FFmpeg static build from GitHub...", flush=True)
    req = urllib.request.Request(
        FFMPEG_URL, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp, open(
        "/tmp/ffmpeg.tar.xz", "wb"
    ) as f:
        total = 0
        while True:
            chunk = resp.read(1024 * 1024)  # 1 MB chunks
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
            if total % (10 * 1024 * 1024) < 1024 * 1024:
                print(f"  downloaded {total // (1024*1024)} MB...", flush=True)
    print(f"Download complete: {total // (1024*1024)} MB", flush=True)

    print("Extracting...", flush=True)
    with tarfile.open("/tmp/ffmpeg.tar.xz", "r:xz") as tf:
        tf.extractall("/tmp/ffmpeg_extracted")

    extracted_dirs = [
        d for d in os.listdir("/tmp/ffmpeg_extracted")
        if os.path.isdir(f"/tmp/ffmpeg_extracted/{d}")
    ]
    if not extracted_dirs:
        print("ERROR: no top-level directory found in archive", flush=True)
        return 1
    extracted = extracted_dirs[0]

    for binary in ("ffmpeg", "ffprobe"):
        src = f"/tmp/ffmpeg_extracted/{extracted}/bin/{binary}"
        dst = f"/usr/local/bin/{binary}"
        if not os.path.isfile(src):
            print(f"ERROR: {binary} not found at {src}", flush=True)
            return 1
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
        print(f"Installed {binary} -> {dst}", flush=True)

    os.remove("/tmp/ffmpeg.tar.xz")
    shutil.rmtree("/tmp/ffmpeg_extracted")
    print("FFmpeg installation complete.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
