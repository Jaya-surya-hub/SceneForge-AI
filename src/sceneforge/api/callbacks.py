"""IS-02 — HMAC-SHA256 callback signing and verification.

Outbound webhooks:
    Headers added:
        X-SceneForge-Signature: sha256=<hex>
        X-SceneForge-Timestamp: <unix_timestamp_int>

    Signature = HMAC-SHA256(key=SECRET, msg=f"{timestamp}.{body_bytes}")

Inbound verification:
    1. Parse X-SceneForge-Timestamp (reject if missing).
    2. Reject if |now - timestamp| > CALLBACK_TIMESTAMP_TOLERANCE seconds.
    3. Compute expected = HMAC-SHA256(key=SECRET, msg=f"{timestamp}.{body_bytes}").
    4. Compare using hmac.compare_digest (constant-time) — reject on mismatch.

Never use == for signature comparison; always use hmac.compare_digest.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Optional

from sceneforge.schemas.exceptions import CallbackAuthError

_HMAC_HEADER_SIG = "X-SceneForge-Signature"
_HMAC_HEADER_TS = "X-SceneForge-Timestamp"
_SIG_PREFIX = "sha256="


def _get_secret() -> bytes:
    secret = os.getenv("CALLBACK_HMAC_SECRET", "")
    if not secret:
        raise RuntimeError(
            "CALLBACK_HMAC_SECRET is not configured. "
            "Set it in .env before using callback signing."
        )
    return secret.encode()


def sign_payload(body: bytes) -> dict[str, str]:
    """Return the HMAC headers to attach to an outbound webhook request.

    Args:
        body: Raw request body bytes.

    Returns:
        Dict with X-SceneForge-Signature and X-SceneForge-Timestamp headers.
    """
    timestamp = str(int(time.time()))
    message = f"{timestamp}.".encode() + body
    signature = hmac.new(_get_secret(), message, hashlib.sha256).hexdigest()
    sig_val = f"{_SIG_PREFIX}{signature}"
    return {
        _HMAC_HEADER_SIG: sig_val,
        _HMAC_HEADER_TS: timestamp,
        "X-IncuBrix-Signature": sig_val,
        "X-IncuBrix-Timestamp": timestamp,
    }


def verify_signature(
    *,
    body: bytes,
    signature_header: Optional[str],
    timestamp_header: Optional[str],
    tolerance_seconds: Optional[int] = None,
) -> None:
    """Verify an inbound callback request.

    Args:
        body:             Raw request body bytes.
        signature_header: Value of X-SceneForge-Signature header.
        timestamp_header: Value of X-SceneForge-Timestamp header.
        tolerance_seconds: Max allowed age in seconds (default from env).

    Raises:
        CallbackAuthError: If verification fails for any reason.
    """
    if tolerance_seconds is None:
        tolerance_seconds = int(os.getenv("CALLBACK_TIMESTAMP_TOLERANCE", "300"))

    # --- Timestamp present and within tolerance ---
    if not timestamp_header:
        raise CallbackAuthError()

    try:
        ts = int(timestamp_header)
    except ValueError:
        raise CallbackAuthError()

    now = int(time.time())
    if abs(now - ts) > tolerance_seconds:
        raise CallbackAuthError()

    # --- Signature present and well-formed ---
    if not signature_header or not signature_header.startswith(_SIG_PREFIX):
        raise CallbackAuthError()

    provided_hex = signature_header[len(_SIG_PREFIX):]

    # --- Compute expected ---
    message = f"{ts}.".encode() + body
    expected_hex = hmac.new(_get_secret(), message, hashlib.sha256).hexdigest()

    # --- Constant-time comparison (IS-02 requirement) ---
    if not hmac.compare_digest(expected_hex, provided_hex):
        raise CallbackAuthError()


# ---------------------------------------------------------------------------
# Async outbound webhook sender (used by worker after job completion)
# ---------------------------------------------------------------------------

async def send_callback(
    callback_url: str,
    payload: dict,
    job_id: str,
) -> None:
    """Send a signed webhook to the registered callback URL.

    Failures are logged but do not affect job status — the job is already
    in a terminal state when callbacks are fired.
    """
    import json

    import httpx

    from sceneforge.observability.logging import get_logger

    log = get_logger(__name__)

    body = json.dumps(payload).encode()
    headers = sign_payload(body)
    headers["Content-Type"] = "application/json"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(callback_url, content=body, headers=headers)
            log.info(
                "callback_sent",
                job_id=job_id,
                url=callback_url,
                status_code=response.status_code,
            )
    except Exception as exc:
        log.warning(
            "callback_failed",
            job_id=job_id,
            url=callback_url,
            error=str(exc),
        )
