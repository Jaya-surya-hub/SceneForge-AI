"""Domain exception hierarchy for SceneForge AI.

Every domain error carries:
- code:      SCREAMING_SNAKE_CASE machine-readable string
- message:   Human-readable description (safe for external exposure)
- retryable: Whether a client retry may succeed
- http_status: Suggested HTTP status code for the API layer
"""

from __future__ import annotations

from typing import Any, Optional


class SceneForgeError(Exception):
    """Base class for all SceneForge domain errors."""

    code: str = "INTERNAL_ERROR"
    retryable: bool = False
    http_status: int = 500

    def __init__(
        self,
        message: str = "An unexpected error occurred.",
        *,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


# ---------------------------------------------------------------------------
# Validation errors (400)
# ---------------------------------------------------------------------------

class ValidationError(SceneForgeError):
    code = "VALIDATION_ERROR"
    retryable = False
    http_status = 422


class EmptyScriptError(ValidationError):
    code = "EMPTY_SCRIPT"

    def __init__(self) -> None:
        super().__init__("Script must not be empty.")


class UnsupportedAudioFormatError(ValidationError):
    code = "UNSUPPORTED_AUDIO_FORMAT"

    def __init__(self, fmt: str = "") -> None:
        msg = f"Audio format not supported: {fmt}" if fmt else "Audio format not supported."
        super().__init__(msg)


class CorruptedAudioError(ValidationError):
    code = "CORRUPTED_AUDIO"

    def __init__(self) -> None:
        super().__init__("The supplied audio file is corrupted or unreadable.")


class FileTooLargeError(ValidationError):
    code = "FILE_TOO_LARGE"
    http_status = 413

    def __init__(self, max_bytes: int) -> None:
        super().__init__(f"Upload exceeds maximum size of {max_bytes} bytes.")


class SpeechNotDetectedError(ValidationError):
    code = "SPEECH_NOT_DETECTED"

    def __init__(self) -> None:
        super().__init__("Speech could not be reliably detected in the supplied audio.")


class AudioDurationExceededError(ValidationError):
    code = "AUDIO_DURATION_EXCEEDED"

    def __init__(self, duration_s: float, max_s: float = 600.0) -> None:
        super().__init__(
            f"Audio duration ({duration_s:.1f}s) exceeds maximum permitted limit of {max_s:.0f}s (10 minutes)."
        )


# ---------------------------------------------------------------------------
# Not found (404)
# ---------------------------------------------------------------------------

class NotFoundError(SceneForgeError):
    code = "NOT_FOUND"
    retryable = False
    http_status = 404

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(f"{resource} not found.")


# ---------------------------------------------------------------------------
# Conflict (409)
# ---------------------------------------------------------------------------

class IdempotencyConflictError(SceneForgeError):
    code = "IDEMPOTENCY_CONFLICT"
    retryable = False
    http_status = 409

    def __init__(self) -> None:
        super().__init__(
            "A job was already created with this idempotency key but a different payload."
        )


class InvalidTransitionError(SceneForgeError):
    code = "INVALID_STATE_TRANSITION"
    retryable = False
    http_status = 409

    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Cannot transition job from {from_status!r} to {to_status!r}.",
            details={"from": from_status, "to": to_status},
        )


# ---------------------------------------------------------------------------
# Provider errors (502 / 503)
# ---------------------------------------------------------------------------

class ProviderError(SceneForgeError):
    code = "PROVIDER_ERROR"
    retryable = True
    http_status = 502


class MediaProviderUnavailableError(ProviderError):
    code = "MEDIA_PROVIDER_UNAVAILABLE"

    def __init__(self, provider: str = "") -> None:
        msg = (
            f"Media provider {provider!r} is unavailable."
            if provider
            else "The media provider is unavailable."
        )
        super().__init__(msg)


class TTSProviderError(ProviderError):
    code = "TTS_PROVIDER_ERROR"

    def __init__(self, detail: str = "") -> None:
        super().__init__(f"TTS provider error: {detail}" if detail else "TTS provider error.")


class STTProviderError(ProviderError):
    code = "STT_PROVIDER_ERROR"

    def __init__(self, detail: str = "") -> None:
        super().__init__(f"STT provider error: {detail}" if detail else "STT provider error.")


# ---------------------------------------------------------------------------
# Rights / licence errors
# ---------------------------------------------------------------------------

class LicenceVerificationError(SceneForgeError):
    code = "LICENCE_VERIFICATION_FAILED"
    retryable = False
    http_status = 422

    def __init__(self, asset_id: str = "") -> None:
        msg = (
            f"Licence for asset {asset_id!r} could not be verified."
            if asset_id
            else "Asset licence could not be verified."
        )
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Rendering errors
# ---------------------------------------------------------------------------

class RenderError(SceneForgeError):
    code = "RENDER_ERROR"
    retryable = True
    http_status = 500

    def __init__(self, detail: str = "") -> None:
        super().__init__(f"Rendering failed: {detail}" if detail else "Rendering failed.")


# ---------------------------------------------------------------------------
# Callback auth
# ---------------------------------------------------------------------------

class CallbackAuthError(SceneForgeError):
    code = "CALLBACK_AUTH_FAILED"
    retryable = False
    http_status = 401

    def __init__(self) -> None:
        super().__init__("Callback signature verification failed.")
