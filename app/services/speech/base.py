from __future__ import annotations

from typing import Protocol, runtime_checkable


class SpeechServiceError(RuntimeError):
    """Raised when the speech service fails to complete a request."""


@runtime_checkable
class SpeechService(Protocol):
    """Abstraction over speech-to-text and text-to-speech capabilities."""

    def transcribe(self, audio: bytes, *, mime_type: str | None = None, language: str | None = None) -> str:
        """Convert raw audio bytes into text."""

    def synthesize(self, text: str, *, voice: str | None = None, response_format: str | None = None) -> bytes:
        """Convert text into audio bytes ready for playback."""
