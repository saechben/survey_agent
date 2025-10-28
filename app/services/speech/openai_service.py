from __future__ import annotations

import io
import mimetypes
from typing import Any, Dict, Optional

from openai import OpenAI

from app.core.config import SpeechSettings

from .base import SpeechService, SpeechServiceError

_FALLBACK_EXTENSION = ".wav"


class OpenAISpeechService(SpeechService):
    """Speech service backed by OpenAI Whisper (STT) and GPT-4o mini TTS."""

    def __init__(self, *, api_key: str, settings: SpeechSettings) -> None:
        if not api_key:
            raise ValueError("An OpenAI API key is required for the speech service.")
        self._client = OpenAI(api_key=api_key)
        self._stt_model = settings.stt_model
        self._tts_model = settings.tts_model
        self._default_voice = settings.tts_voice or "alloy"
        self._response_format = settings.tts_format or "mp3"
        self._language = settings.language

    def transcribe(self, audio: bytes, *, mime_type: str | None = None, language: str | None = None) -> str:
        if not audio:
            raise ValueError("Audio bytes must be provided for transcription.")

        language_code = language or self._language
        filename = f"input{self._resolve_extension(mime_type)}"

        audio_stream = io.BytesIO(audio)
        audio_stream.name = filename  # type: ignore[attr-defined]

        request_args: Dict[str, Any] = {"model": self._stt_model, "file": audio_stream}
        if language_code:
            request_args["language"] = language_code

        response = self._client.audio.transcriptions.create(**request_args)

        if isinstance(response, str):
            return response.strip()

        text = getattr(response, "text", None)
        if not text:
            raise SpeechServiceError("OpenAI transcription response did not include text.")
        return text.strip()

    def synthesize(self, text: str, *, voice: str | None = None, response_format: str | None = None) -> bytes:
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValueError("Text must be provided for synthesis.")

        target_voice = voice or self._default_voice
        if not target_voice:
            raise ValueError("A target voice must be configured for text-to-speech synthesis.")

        target_format = response_format or self._response_format or "mp3"

        speech_response = self._client.audio.speech.create(
            model=self._tts_model,
            voice=target_voice,
            input=cleaned,
            response_format=target_format,
        )

        audio_bytes = speech_response.read()
        speech_response.close()

        if not audio_bytes:
            raise SpeechServiceError("OpenAI text-to-speech request returned no audio bytes.")

        return audio_bytes

    @staticmethod
    def _resolve_extension(mime_type: Optional[str]) -> str:
        if not mime_type:
            return _FALLBACK_EXTENSION

        guessed = mimetypes.guess_extension(mime_type)
        if guessed:
            return guessed

        if mime_type == "audio/mpeg":
            return ".mp3"

        return _FALLBACK_EXTENSION
