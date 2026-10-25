#!/usr/bin/env python3
"""Batch runner CLI for SceneForge AI (IS-06).

Submits jobs to the API, polls for completion, downloads artifacts,
and produces a machine-readable JSON report.

Usage:
  python scripts/batch_runner.py --cases tests/fixtures/batch_cases.json --base-url http://localhost:8000 --output report.json

Exit code: 0 = all pass, 1 = any failure
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BatchCaseResult:
    case_id: str
    script: str
    job_id: Optional[str] = None
    status: str = "PENDING"
    error: Optional[str] = None
    duration_seconds: float = 0.0
    artifacts: list[str] = field(default_factory=list)


def api_get(base_url: str, path: str) -> dict:
    url = f"{base_url}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def api_post(base_url: str, path: str, body: dict, headers: dict) -> dict:
    url = f"{base_url}{path}"
    data = json.dumps(body).encode("utf-8")
    all_headers = {"Content-Type": "application/json", **headers}
    req = urllib.request.Request(url, data=data, headers=all_headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def run_case(base_url: str, case: dict, poll_interval: int = 5, max_wait: int = 120) -> BatchCaseResult:
    """Submit a single test case and poll until terminal status."""
    case_id = case.get("id", f"case-{case.get('script', '')[:20]}")
    result = BatchCaseResult(
        case_id=case_id,
        script=case.get("script", ""),
    )

    # Submit job
    idem_key = case.get("idempotency_key", f"batch-{case_id}-{int(time.time())}")
    headers = {"Idempotency-Key": idem_key}
    body = {
        "script": case.get("script", ""),
        "aspect_ratio": case.get("aspect_ratio", "16:9"),
        "tts_adapter": case.get("tts_adapter", "mock"),
        "stock_provider": case.get("stock_provider", "mock"),
    }
    if case.get("callback_url"):
        body["callback_url"] = case["callback_url"]

    t0 = time.perf_counter()
    try:
        resp = api_post(base_url, "/jobs", body, headers)
        result.job_id = resp.get("job_id")
        result.status = resp.get("status", "QUEUED")
    except Exception as exc:
        result.status = "FAILED"
        expected = case.get("expected_status", "COMPLETED")
        if expected == "FAILED":
            result.error = None
        else:
            result.error = f"Submit failed: {exc}"
        return result

    # Poll for completion
    deadline = time.perf_counter() + max_wait
    while time.perf_counter() < deadline:
        time.sleep(poll_interval)
        try:
            status_resp = api_get(base_url, f"/jobs/{result.job_id}")
            result.status = status_resp.get("status", "UNKNOWN")
            if result.status in ("COMPLETED", "FAILED", "CANCELLED"):
                break
        except Exception as exc:
            result.status = "FAILED"
            result.error = f"Poll failed: {exc}"
            break

    result.duration_seconds = round(time.perf_counter() - t0, 2)

    # Get artifacts if completed
    if result.status == "COMPLETED":
        try:
            arts = api_get(base_url, f"/jobs/{result.job_id}/artifacts")
            result.artifacts = arts.get("artifacts", [])
        except Exception:
            pass

    # Check expected status
    expected = case.get("expected_status", "COMPLETED")
    if result.status != expected:
        if not result.error:
            result.error = f"Expected {expected}, got {result.status}"
    else:
        # If the case expected failure, encountering expected error is a passing test
        if expected == "FAILED":
            result.error = None

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="SceneForge batch runner")
    parser.add_argument("--cases", required=True, help="Path to JSON test cases file or directory of test cases")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="API base URL")
    parser.add_argument("--output", default="batch_report.json",
                        help="Output report path (JSON)")
    parser.add_argument("--output-dir", default=None,
                        help="Optional folder to download all case artifacts into")
    parser.add_argument("--poll-interval", type=int, default=5,
                        help="Poll interval in seconds")
    parser.add_argument("--max-wait", type=int, default=120,
                        help="Max wait per case in seconds")
    args = parser.parse_args()

    # Load test cases from file or directory
    cases = []
    if os.path.isdir(args.cases):
        for fname in sorted(os.listdir(args.cases)):
            fpath = os.path.join(args.cases, fname)
            if fname.endswith(".json"):
                with open(fpath, "r", encoding="utf-8") as f:
                    cdata = json.load(f)
                    if isinstance(cdata, list):
                        cases.extend(cdata)
                    else:
                        cases.append(cdata)
            elif fname.endswith(".txt"):
                with open(fpath, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                if text:
                    cases.append({
                        "id": os.path.splitext(fname)[0],
                        "script": text,
                        "aspect_ratio": "16:9",
                        "expected_status": "COMPLETED",
                    })
    else:
        with open(args.cases, "r", encoding="utf-8") as f:
            cases = json.load(f)
        if not isinstance(cases, list):
            cases = [cases]

    print(f"Running {len(cases)} test cases against {args.base_url}")

    results: list[BatchCaseResult] = []
    for i, case in enumerate(cases):
        print(f"  [{i+1}/{len(cases)}] {case.get('id', case.get('script','')[:30])}...", end=" ", flush=True)
        result = run_case(args.base_url, case, args.poll_interval, args.max_wait)
        results.append(result)
        passed = result.status == case.get("expected_status", "COMPLETED")
        print(f"{'PASS' if passed else 'FAIL'} ({result.status}, {result.duration_seconds}s)")

    # Build report
    report = {
        "base_url": args.base_url,
        "total_cases": len(cases),
        "passed": sum(1 for r in results if not r.error),
        "failed": sum(1 for r in results if r.error),
        "cases": [
            {
                "case_id": r.case_id,
                "job_id": r.job_id,
                "status": r.status,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
                "artifacts": r.artifacts,
            }
            for r in results
        ],
    }

    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        for r in results:
            if r.status == "COMPLETED" and r.job_id:
                case_dir = os.path.join(args.output_dir, r.case_id)
                os.makedirs(case_dir, exist_ok=True)
                for art in r.artifacts:
                    art_url = f"{args.base_url}/files/sceneforge-artifacts/jobs/{r.job_id}/{art}"
                    try:
                        with urllib.request.urlopen(art_url, timeout=30) as uresp:
                            with open(os.path.join(case_dir, art), "wb") as af:
                                af.write(uresp.read())
                    except Exception as exc:
                        print(f"Warning: could not download {art} for {r.case_id}: {exc}")

    try:
        data_bytes = json.dumps(report, indent=2).encode("utf-8")
        with open(args.output, "wb") as f:
            f.write(data_bytes)
        print(f"\nReport written to {args.output}")
    except OSError as exc:
        print(f"\nWarning: could not write {args.output} directly ({exc}). Output JSON summary:")
        print(json.dumps(report, indent=2))
    print(f"Passed: {report['passed']}/{report['total_cases']}")
    print(f"Failed: {report['failed']}/{report['total_cases']}")

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
