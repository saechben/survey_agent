from __future__ import annotations

import re
from typing import Any

try:  # pragma: no cover - optional dependency
    from google.cloud import speech
    from google.cloud import texttospeech
except ImportError:  # pragma: no cover - optional dependency
    speech = None
    texttospeech = None

from app.core.config import SpeechSettings

from .base import SpeechService, SpeechServiceError

_DEFAULT_LANGUAGE = "en-US"
_DEFAULT_TTS_VOICE = "en-US-Neural2-C"
_DEFAULT_STT_MODEL = "latest_long"


class GoogleSpeechService(SpeechService):
    """Speech-to-text and text-to-speech service backed by Google Cloud APIs."""

    def __init__(
        self,
        *,
        settings: SpeechSettings,
        speech_client: Any | None = None,
        tts_client: Any | None = None,
    ) -> None:
        if speech is None or texttospeech is None:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "google-cloud-speech and google-cloud-texttospeech are required for GoogleSpeechService."
            )
        if settings is None:
            raise ValueError("Speech settings must be provided.")

        self._language = settings.language or _DEFAULT_LANGUAGE
        self._stt_model = settings.stt_model or _DEFAULT_STT_MODEL
        self._default_voice = settings.tts_voice or _DEFAULT_TTS_VOICE
        self._response_format = (settings.tts_format or "mp3").lower()

        self._stt_client = speech_client or speech.SpeechClient()
        self._tts_client = tts_client or texttospeech.TextToSpeechClient()

    def transcribe(self, audio: bytes, *, mime_type: str | None = None, language: str | None = None) -> str:
        if not audio:
            raise ValueError("Audio bytes must be provided for transcription.")

        target_language = (language or self._language or _DEFAULT_LANGUAGE).strip()
        if not target_language:
            raise ValueError("A language code must be provided for transcription.")

        recognition_config = speech.RecognitionConfig(
            language_code=target_language,
            enable_automatic_punctuation=True,
            model=self._stt_model,
            encoding=_resolve_recognition_encoding(mime_type),
        )
        recognition_audio = speech.RecognitionAudio(content=audio)

        response = self._stt_client.recognize(config=recognition_config, audio=recognition_audio)

        transcripts: list[str] = []
        for result in getattr(response, "results", []):
            alternatives = getattr(result, "alternatives", None) or []
            if not alternatives:
                continue
            transcript = getattr(alternatives[0], "transcript", "") or ""
            cleaned = transcript.strip()
            if cleaned:
                transcripts.append(cleaned)

        combined = " ".join(transcripts).strip()
        if not combined:
            raise SpeechServiceError("Google transcription response did not include text.")

        return combined

    def synthesize(self, text: str, *, voice: str | None = None, response_format: str | None = None) -> bytes:
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValueError("Text must be provided for synthesis.")

        target_voice = (voice or self._default_voice or "").strip()
        language_code = self._language or _DEFAULT_LANGUAGE
        encoding = _resolve_tts_encoding(response_format or self._response_format)

        synthesis_input = texttospeech.SynthesisInput(text=cleaned)
        voice_params = texttospeech.VoiceSelectionParams(language_code=language_code)
        if target_voice:
            voice_params.name = target_voice

        audio_config = texttospeech.AudioConfig(audio_encoding=encoding)

        response = self._tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )

        audio_content = getattr(response, "audio_content", None)
        if not audio_content:
            raise SpeechServiceError("Google text-to-speech request returned no audio bytes.")

        return audio_content


def _resolve_recognition_encoding(mime_type: str | None) -> "speech.RecognitionConfig.AudioEncoding":
    if speech is None:  # pragma: no cover - optional dependency
        raise RuntimeError("google-cloud-speech is required to resolve encodings.")

    default = speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED
    if not mime_type:
        return default

    normalized = mime_type.split(";")[0].strip().lower()
    mapping = {
        "audio/wav": speech.RecognitionConfig.AudioEncoding.LINEAR16,
        "audio/x-wav": speech.RecognitionConfig.AudioEncoding.LINEAR16,
        "audio/pcm": speech.RecognitionConfig.AudioEncoding.LINEAR16,
        "audio/flac": speech.RecognitionConfig.AudioEncoding.FLAC,
        "audio/mpeg": speech.RecognitionConfig.AudioEncoding.MP3,
        "audio/mp3": speech.RecognitionConfig.AudioEncoding.MP3,
        "audio/ogg": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
        "audio/ogg;codecs=opus": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
        "audio/webm": speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
    }
    return mapping.get(normalized, default)


def _resolve_tts_encoding(fmt: str | None) -> "texttospeech.AudioEncoding":
    if texttospeech is None:  # pragma: no cover - optional dependency
        raise RuntimeError("google-cloud-texttospeech is required to resolve encodings.")

    key = (fmt or "mp3").strip().lower()
    key = re.split(r"[+;/]", key)[0]
    mapping = {
        "mp3": texttospeech.AudioEncoding.MP3,
        "wav": texttospeech.AudioEncoding.LINEAR16,
        "pcm": texttospeech.AudioEncoding.LINEAR16,
        "flac": texttospeech.AudioEncoding.FLAC,
        "ogg": texttospeech.AudioEncoding.OGG_OPUS,
        "opus": texttospeech.AudioEncoding.OGG_OPUS,
    }
    return mapping.get(key, texttospeech.AudioEncoding.MP3)
