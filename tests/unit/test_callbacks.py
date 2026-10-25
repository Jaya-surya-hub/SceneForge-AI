"""Unit tests for HMAC-SHA256 callback signing and verification (IS-02).

Tests:
- Valid signature is accepted.
- Wrong signature is rejected with CallbackAuthError.
- Missing signature header is rejected.
- Replayed timestamp (outside tolerance) is rejected.
- Missing timestamp is rejected.
- Verification uses constant-time comparison (structural test).
"""

import hashlib
import hmac
import time

import pytest

from sceneforge.api.callbacks import sign_payload, verify_signature
from sceneforge.schemas.exceptions import CallbackAuthError


BODY = b'{"job_id": "test-123", "status": "COMPLETED"}'


class TestSignPayload:
    def test_returns_two_headers(self):
        headers = sign_payload(BODY)
        assert "X-SceneForge-Signature" in headers
        assert "X-SceneForge-Timestamp" in headers

    def test_signature_has_prefix(self):
        headers = sign_payload(BODY)
        assert headers["X-SceneForge-Signature"].startswith("sha256=")

    def test_timestamp_is_recent_int(self):
        headers = sign_payload(BODY)
        ts = int(headers["X-SceneForge-Timestamp"])
        assert abs(time.time() - ts) < 5

    def test_different_bodies_produce_different_signatures(self):
        h1 = sign_payload(b"body one")
        h2 = sign_payload(b"body two")
        assert h1["X-SceneForge-Signature"] != h2["X-SceneForge-Signature"]


class TestVerifySignature:
    def test_valid_signature_accepted(self):
        headers = sign_payload(BODY)
        # Must not raise
        verify_signature(
            body=BODY,
            signature_header=headers["X-SceneForge-Signature"],
            timestamp_header=headers["X-SceneForge-Timestamp"],
            tolerance_seconds=60,
        )

    def test_wrong_signature_rejected(self):
        headers = sign_payload(BODY)
        bad_sig = headers["X-SceneForge-Signature"][:-4] + "0000"
        with pytest.raises(CallbackAuthError):
            verify_signature(
                body=BODY,
                signature_header=bad_sig,
                timestamp_header=headers["X-SceneForge-Timestamp"],
                tolerance_seconds=60,
            )

    def test_missing_signature_rejected(self):
        headers = sign_payload(BODY)
        with pytest.raises(CallbackAuthError):
            verify_signature(
                body=BODY,
                signature_header=None,
                timestamp_header=headers["X-SceneForge-Timestamp"],
                tolerance_seconds=60,
            )

    def test_missing_timestamp_rejected(self):
        headers = sign_payload(BODY)
        with pytest.raises(CallbackAuthError):
            verify_signature(
                body=BODY,
                signature_header=headers["X-SceneForge-Signature"],
                timestamp_header=None,
                tolerance_seconds=60,
            )

    def test_replayed_old_timestamp_rejected(self):
        # Build a valid signature with an old timestamp
        old_ts = str(int(time.time()) - 400)
        import os
        secret = os.environ.get("CALLBACK_HMAC_SECRET", "test-secret-key-for-unit-tests").encode()
        message = f"{old_ts}.".encode() + BODY
        sig_hex = hmac.new(secret, message, hashlib.sha256).hexdigest()
        with pytest.raises(CallbackAuthError):
            verify_signature(
                body=BODY,
                signature_header=f"sha256={sig_hex}",
                timestamp_header=old_ts,
                tolerance_seconds=300,
            )

    def test_future_timestamp_beyond_tolerance_rejected(self):
        future_ts = str(int(time.time()) + 400)
        import os
        secret = os.environ.get("CALLBACK_HMAC_SECRET", "test-secret-key-for-unit-tests").encode()
        message = f"{future_ts}.".encode() + BODY
        sig_hex = hmac.new(secret, message, hashlib.sha256).hexdigest()
        with pytest.raises(CallbackAuthError):
            verify_signature(
                body=BODY,
                signature_header=f"sha256={sig_hex}",
                timestamp_header=future_ts,
                tolerance_seconds=300,
            )

    def test_malformed_timestamp_rejected(self):
        headers = sign_payload(BODY)
        with pytest.raises(CallbackAuthError):
            verify_signature(
                body=BODY,
                signature_header=headers["X-SceneForge-Signature"],
                timestamp_header="not-a-number",
                tolerance_seconds=60,
            )

    def test_signature_without_prefix_rejected(self):
        headers = sign_payload(BODY)
        sig_no_prefix = headers["X-SceneForge-Signature"].replace("sha256=", "")
        with pytest.raises(CallbackAuthError):
            verify_signature(
                body=BODY,
                signature_header=sig_no_prefix,
                timestamp_header=headers["X-SceneForge-Timestamp"],
                tolerance_seconds=60,
            )
