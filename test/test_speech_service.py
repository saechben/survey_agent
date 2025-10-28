from __future__ import annotations

import types

import pytest

from app.core.config import SpeechSettings
from app.services.speech.base import SpeechServiceError
from app.services.speech.openai_service import OpenAISpeechService


class _DummySpeechResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.closed = False

    def read(self) -> bytes:
        return self._payload

    def close(self) -> None:
        self.closed = True


def _build_service() -> OpenAISpeechService:
    return OpenAISpeechService(
        api_key="test-key",
        settings=SpeechSettings(
            provider="openai",
            stt_model="whisper-1",
            tts_model="gpt-4o-mini-tts",
            tts_voice="alloy",
            tts_format="mp3",
        ),
    )


def test_transcribe_returns_text_string(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service()

    monkeypatch.setattr(service._client.audio.transcriptions, "create", lambda **_: "  sample  ")

    assert service.transcribe(b"\x00\x01") == "sample"


def test_transcribe_uses_response_object_text(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service()

    captured_filename: dict[str, str] = {}

    def _fake_create(**kwargs: object) -> object:
        file_obj = kwargs["file"]
        captured_filename["value"] = getattr(file_obj, "name", "")
        return types.SimpleNamespace(text="example output")

    monkeypatch.setattr(service._client.audio.transcriptions, "create", _fake_create)

    result = service.transcribe(b"\x02\x03", mime_type="audio/mpeg")

    assert result == "example output"
    assert captured_filename["value"].endswith(".mp3")


def test_transcribe_raises_when_response_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service()

    monkeypatch.setattr(service._client.audio.transcriptions, "create", lambda **_: types.SimpleNamespace(text=None))

    with pytest.raises(SpeechServiceError):
        service.transcribe(b"\x01\x02")


def test_synthesize_returns_audio_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service()

    dummy_response = _DummySpeechResponse(b"audio-bytes")
    monkeypatch.setattr(service._client.audio.speech, "create", lambda **_: dummy_response)

    result = service.synthesize("Hello world")

    assert result == b"audio-bytes"
    assert dummy_response.closed is True


def test_synthesize_raises_when_empty_response(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service()

    dummy_response = _DummySpeechResponse(b"")
    monkeypatch.setattr(service._client.audio.speech, "create", lambda **_: dummy_response)

    with pytest.raises(SpeechServiceError):
        service.synthesize("Hello world")

