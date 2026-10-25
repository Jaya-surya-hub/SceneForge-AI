import os
import json
import urllib.request
import subprocess

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
base_url = "http://localhost:8000"

# Target directories
video_pack_dir = os.path.join(root_dir, "video_pack")
test_pack_dir = os.path.join(root_dir, "test_pack")
evidence_dir = os.path.join(root_dir, "evidence")

os.makedirs(video_pack_dir, exist_ok=True)
os.makedirs(test_pack_dir, exist_ok=True)
os.makedirs(evidence_dir, exist_ok=True)

# Selected jobs for video_pack
jobs_map = {
    "job_16x9_script_pixabay": "a89874ff-b596-43d5-b95e-6cec68a7d441",
    "job_16x9_audio_only_stt": "c6e7e5b1-42ac-4f55-bb1a-98f43fc5f301",
    "job_9x16_portrait": "ca9aa9d4-9769-4fda-963e-a77e8ac984e3",
    "job_1x1_square": "1d7b1d2d-9932-408e-b75f-ffaa5199572d",
    "job_16x9_alpine_lake": "8ce5ae31-f3e4-4856-b951-201baabcffd9",
}

artifacts = [
    "output.mp4",
    "captions.srt",
    "timeline.json",
    "rights.json",
    "manifest.json",
    "metrics.json",
    "job.log",
]

print("1. Downloading artifacts to video_pack...")
for pack_name, jid in jobs_map.items():
    dest_dir = os.path.join(video_pack_dir, pack_name)
    os.makedirs(dest_dir, exist_ok=True)
    for art in artifacts:
        url = f"{base_url}/files/sceneforge-artifacts/jobs/{jid}/{art}"
        dest_file = os.path.join(dest_dir, art)
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                content = resp.read()
                with open(dest_file, "wb") as f:
                    f.write(content)
            print(f"  [OK] {pack_name}/{art} ({len(content)} bytes)")
        except Exception as exc:
            print(f"  [WARN] Failed {pack_name}/{art}: {exc}")

print("2. Packaging test_pack...")
# Copy batch cases and report
batch_cases_src = os.path.join(root_dir, "tests", "fixtures", "batch_cases.json")
if os.path.exists(batch_cases_src):
    with open(batch_cases_src, "rb") as f:
        cases_content = f.read()
    with open(os.path.join(test_pack_dir, "batch_cases.json"), "wb") as f:
        f.write(cases_content)

batch_report_src = os.path.join(root_dir, "batch_report.json")
if os.path.exists(batch_report_src):
    with open(batch_report_src, "rb") as f:
        report_content = f.read()
    with open(os.path.join(test_pack_dir, "batch_report.json"), "wb") as f:
        f.write(report_content)

print("3. Capturing live evidence...")
# Health check
try:
    with urllib.request.urlopen(f"{base_url}/api/v1/health") as resp:
        health_data = json.loads(resp.read().decode())
    with urllib.request.urlopen(f"{base_url}/api/v1/ready") as resp:
        ready_data = json.loads(resp.read().decode())
    with open(os.path.join(evidence_dir, "health_and_ready.json"), "wb") as f:
        f.write(json.dumps({"health": health_data, "ready": ready_data}, indent=2).encode())
    print("  [OK] health_and_ready.json")
except Exception as exc:
    print("  [WARN] Health check evidence failed:", exc)

# OpenAPI schema summary
try:
    with urllib.request.urlopen(f"{base_url}/openapi.json") as resp:
        schema = json.loads(resp.read().decode())
    summary = {
        "openapi": schema.get("openapi"),
        "info": schema.get("info"),
        "paths": list(schema.get("paths", {}).keys()),
    }
    with open(os.path.join(evidence_dir, "openapi_summary.json"), "wb") as f:
        f.write(json.dumps(summary, indent=2).encode())
    print("  [OK] openapi_summary.json")
except Exception as exc:
    print("  [WARN] OpenAPI summary evidence failed:", exc)

print("Build packs complete!")
