from __future__ import annotations

import types

import pytest

from app.core.config import SpeechSettings
from app.services.speech import google_service
from app.services.speech.base import SpeechServiceError

pytestmark = pytest.mark.skipif(
    google_service.speech is None or google_service.texttospeech is None,
    reason="Google Cloud speech dependencies not installed",
)

GoogleSpeechService = google_service.GoogleSpeechService


class _StubSpeechClient:
    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def recognize(self, *, config: object, audio: object) -> object:
        self.calls.append({"config": config, "audio": audio})
        return self._response


class _StubTTSClient:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.calls: list[dict[str, object]] = []

    def synthesize_speech(self, *, input: object, voice: object, audio_config: object) -> object:
        self.calls.append({"input": input, "voice": voice, "audio_config": audio_config})
        return types.SimpleNamespace(audio_content=self._payload)


def _build_service(
    *,
    speech_response: object | None = None,
    tts_payload: bytes = b"audio-bytes",
) -> GoogleSpeechService:
    speech_client = _StubSpeechClient(
        speech_response
        or types.SimpleNamespace(
            results=[
                types.SimpleNamespace(
                    alternatives=[types.SimpleNamespace(transcript="sample transcript")],
                )
            ]
        )
    )
    tts_client = _StubTTSClient(tts_payload)
    return GoogleSpeechService(
        settings=SpeechSettings(
            provider="gcp",
            stt_model="latest_long",
            tts_model="",
            tts_voice="en-US-Neural2-C",
            tts_format="mp3",
            language="en-US",
        ),
        speech_client=speech_client,
        tts_client=tts_client,
    )


def test_transcribe_returns_text_string() -> None:
    service = _build_service()

    assert service.transcribe(b"\x00\x01") == "sample transcript"


def test_transcribe_raises_when_response_empty() -> None:
    empty_response = types.SimpleNamespace(results=[types.SimpleNamespace(alternatives=[])])
    service = _build_service(speech_response=empty_response)

    with pytest.raises(SpeechServiceError):
        service.transcribe(b"\x01\x02")


def test_synthesize_returns_audio_bytes() -> None:
    service = _build_service(tts_payload=b"audio-bytes")

    result = service.synthesize("Hello world")

    assert result == b"audio-bytes"


def test_synthesize_raises_when_empty_response() -> None:
    service = _build_service(tts_payload=b"")

    with pytest.raises(SpeechServiceError):
        service.synthesize("Hello world")
