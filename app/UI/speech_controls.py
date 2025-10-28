from __future__ import annotations

import base64
import hashlib
import time
from typing import Any, Dict

import streamlit as st
import streamlit.components.v1 as components

from app.core.config import settings
from app.services.speech import OpenAISpeechService, SpeechServiceError

_AUDIO_CACHE_KEY = "speech_audio_cache"
_SUPPORTED_UPLOAD_TYPES = ["mp3", "wav", "m4a", "ogg", "webm"]
_AUTO_TTS_STATE_KEY = "speech_auto_tts_enabled"
_AUTO_TTS_BUTTON_KEY = "speech_auto_tts_button"
_QUESTION_INDEX_TRACK_KEY = "speech_last_question_index"
_AUDIO_EVENT_STATE_KEY = "speech_audio_events"
_TYPEWRITER_DONE_KEY = "speech_typewriter_complete"
_TYPEWRITER_DELAY_SECONDS = 0.085
_SESSION_VERSION_KEY = "speech_audio_session_version"


@st.cache_resource
def get_speech_service() -> OpenAISpeechService:
    """Instantiate and cache the OpenAI-backed speech service."""

    return OpenAISpeechService(api_key=settings.llm_api_key, settings=settings.speech)


def render_tts_toggle(*, help_text: str | None = None) -> bool:
    """Render the auto-text-to-speech toggle button."""

    enabled = bool(st.session_state.get(_AUTO_TTS_STATE_KEY, False))
    label = "🔊 Auto speech on" if enabled else "🔈 Auto speech off"
    button_type = "primary" if enabled else "secondary"
    clicked = st.button(
        label,
        key=_AUTO_TTS_BUTTON_KEY,
        type=button_type,
        use_container_width=True,
        help=help_text or "Toggle automatic text-to-speech playback.",
    )
    if clicked:
        enabled = not enabled
        st.session_state[_AUTO_TTS_STATE_KEY] = enabled
        _clear_speech_states()
    else:
        st.session_state.setdefault(_AUTO_TTS_STATE_KEY, enabled)

    return bool(st.session_state[_AUTO_TTS_STATE_KEY])


def is_auto_tts_enabled() -> bool:
    """Return True when automatic TTS playback is active."""

    return bool(st.session_state.get(_AUTO_TTS_STATE_KEY, False))


def prepare_question_render(current_index: int) -> str:
    """Reset per-question state when navigating to a new survey question."""

    cache_id = f"question_{current_index}"
    last_index = st.session_state.get(_QUESTION_INDEX_TRACK_KEY)
    if last_index != current_index:
        st.session_state[_QUESTION_INDEX_TRACK_KEY] = current_index
        _playback_state().pop(cache_id, None)
        _typewriter_state().pop(cache_id, None)
        _reset_followup_states()
    return cache_id


def autoplay_question(text: str, *, cache_id: str, enabled: bool) -> bool:
    """Play the spoken version of ``text`` when auto TTS is enabled."""

    entry = _playback_state().setdefault(cache_id, {"started": False, "rendered": False})

    cleaned = (text or "").strip()
    version = _text_version(cleaned)
    if entry.get("version") != version:
        entry.update({"text": cleaned, "version": version, "started": False, "rendered": False})
        entry.pop("error", None)
        _typewriter_state().pop(cache_id, None)

    if not enabled:
        return entry.get("started", False)

    if not cleaned:
        entry["started"] = True
        return True

    try:
        audio_bytes = _synthesize_with_cache(cache_id, cleaned)
    except SpeechServiceError as exc:  # pragma: no cover - UI feedback path
        st.error(f"Speech synthesis failed: {exc}")
        entry["error"] = True
        entry["started"] = True
        return True
    except Exception as exc:  # pragma: no cover - UI feedback path
        st.error(f"Unexpected speech synthesis error: {exc}")
        entry["error"] = True
        entry["started"] = True
        return True

    should_autoplay = enabled and not entry.get("rendered", False)
    _render_autoplay_audio(
        audio_bytes,
        cache_id,
        autoplay=should_autoplay,
        text_version=version,
    )
    entry["rendered"] = True
    entry["started"] = True

    return True


def render_question_text(text: str, *, cache_id: str, animate: bool, prefix_markdown: str | None = None) -> None:
    """Display the question text, syncing a typewriter effect with playback."""

    placeholder = st.empty()

    def _render_output(body: str) -> None:
        content = f"{prefix_markdown or ''}{body}"
        if prefix_markdown:
            placeholder.markdown(content)
        else:
            placeholder.write(content)

    cleaned = (text or "").strip()
    if not cleaned:
        _render_output("")
        return

    if not animate:
        _render_output(cleaned)
        _typewriter_state()[cache_id] = True
        return

    playback_entry = _playback_state().get(cache_id, {})
    if playback_entry.get("error"):
        _render_output(cleaned)
        _typewriter_state()[cache_id] = True
        return

    if not playback_entry.get("started"):
        _render_output("_Preparing audio..._")
        return

    if _typewriter_state().get(cache_id):
        _render_output(cleaned)
        return

    accumulated = ""
    for word in cleaned.split():
        accumulated = (accumulated + " " + word).strip()
        _render_output(accumulated)
        time.sleep(_TYPEWRITER_DELAY_SECONDS)

    _typewriter_state()[cache_id] = True


def render_playback_button(text: str, *, label: str, cache_id: str) -> None:
    """Render a manual playback button when auto TTS is disabled."""

    if is_auto_tts_enabled():
        return

    cleaned = (text or "").strip()
    if not cleaned:
        return

    button_key = f"{cache_id}_play_button"
    audio_state_key = f"{cache_id}_audio_bytes"

    if st.button(label, key=button_key):
        try:
            audio_bytes = _synthesize_with_cache(cache_id, cleaned)
            st.session_state[audio_state_key] = audio_bytes
        except SpeechServiceError as exc:  # pragma: no cover - UI feedback path
            st.error(f"Speech synthesis failed: {exc}")
        except Exception as exc:  # pragma: no cover - UI feedback path
            st.error(f"Unexpected speech synthesis error: {exc}")

    audio_bytes = st.session_state.get(audio_state_key)
    if audio_bytes:
        st.audio(audio_bytes, format=_format_to_mime(settings.speech.tts_format))


def maybe_autoplay_followup(text: str, *, cache_id: str) -> None:
    """Automatically play follow-up questions once when auto TTS is enabled."""

    if not is_auto_tts_enabled():
        return

    cleaned = (text or "").strip()
    if not cleaned:
        return

    entry = _playback_state().setdefault(cache_id, {"started": False, "rendered": False})
    version = _text_version(cleaned)
    if entry.get("version") != version:
        entry.update({"text": cleaned, "version": version, "started": False, "rendered": False})
        entry.pop("error", None)
        _typewriter_state().pop(cache_id, None)

    try:
        audio_bytes = _synthesize_with_cache(cache_id, cleaned)
    except SpeechServiceError as exc:  # pragma: no cover - UI feedback path
        st.error(f"Speech synthesis failed: {exc}")
        entry["error"] = True
        return
    except Exception as exc:  # pragma: no cover - UI feedback path
        st.error(f"Unexpected speech synthesis error: {exc}")
        entry["error"] = True
        return

    should_autoplay = not entry.get("rendered", False)
    _render_autoplay_audio(
        audio_bytes,
        cache_id,
        autoplay=should_autoplay,
        text_version=version,
    )
    entry["rendered"] = True
    entry["started"] = True


def render_transcription_controls(form_key: str, *, title: str) -> str | None:
    """Render an expander that accepts audio input and returns the transcribed text."""

    with st.expander(title, expanded=False):
        upload_key = f"{form_key}_audio_upload"
        uploaded = st.file_uploader(
            "Upload an audio recording",
            key=upload_key,
            type=_SUPPORTED_UPLOAD_TYPES,
            accept_multiple_files=False,
        )

        transcribe_key = f"{form_key}_transcribe_button"
        transcribe_clicked = st.button(
            "Transcribe audio",
            key=transcribe_key,
            disabled=uploaded is None,
        )

        st.caption("Supported formats: mp3, wav, m4a, ogg, webm.")

        if not uploaded or not transcribe_clicked:
            return None

        audio_bytes = uploaded.read()
        uploaded.seek(0)

        try:
            with st.spinner("Transcribing audio..."):
                transcript = get_speech_service().transcribe(audio_bytes, mime_type=getattr(uploaded, "type", None))
        except SpeechServiceError as exc:  # pragma: no cover - UI feedback path
            st.error(f"Transcription failed: {exc}")
            return None
        except Exception as exc:  # pragma: no cover - UI feedback path
            st.error(f"Unexpected transcription error: {exc}")
            return None

        cleaned = (transcript or "").strip()
        if not cleaned:
            st.warning("No speech detected in the uploaded audio.")
            return None

        st.success("Transcription completed.")
        return cleaned


def _render_autoplay_audio(
    audio_bytes: bytes,
    cache_id: str,
    *,
    autoplay: bool,
    text_version: str,
) -> None:
    mime = _format_to_mime(settings.speech.tts_format)
    b64_content = base64.b64encode(audio_bytes).decode("ascii")
    audio_id = f"audio_{cache_id}"
    auto_flag = "true" if autoplay else "false"
    version_js = text_version
    html = f"""
        <audio id="{audio_id}" style="display:none;">
            <source src="data:{mime};base64,{b64_content}" type="{mime}">
            Your browser does not support the audio element.
        </audio>
        <script>
            const audioEl = document.getElementById("{audio_id}");
            const shouldAutoPlay = {auto_flag};
            const version = "{version_js}";
            window.__speechPlayback = window.__speechPlayback || {{}};
            const state = window.__speechPlayback["{cache_id}"] || {{}};
            if (state.version !== version) {{
                state.version = version;
                state.played = false;
                state.completed = false;
                state.position = 0;
            }}

            const resumePosition = state.position || 0;
            const shouldResume = state.played && !state.completed && resumePosition > 0.05;
            const wantPlay = shouldAutoPlay || shouldResume;

            function attemptPlay() {{
                if (!wantPlay) {{
                    return;
                }}
                if (shouldResume) {{
                    audioEl.currentTime = resumePosition;
                }} else {{
                    audioEl.currentTime = 0;
                }}
                const playPromise = audioEl.play();
                if (playPromise !== undefined) {{
                    playPromise.then(() => {{
                        state.played = true;
                        window.__speechPlayback["{cache_id}"] = state;
                    }}).catch(() => {{
                        /* Autoplay might be blocked */
                    }});
                }} else {{
                    state.played = true;
                }}
            }}

            if (audioEl.readyState >= 2) {{
                attemptPlay();
            }} else {{
                audioEl.addEventListener("loadeddata", attemptPlay, {{ once: true }});
            }}

            audioEl.addEventListener("timeupdate", () => {{
                state.position = audioEl.currentTime;
                window.__speechPlayback["{cache_id}"] = state;
            }});

            audioEl.addEventListener("ended", () => {{
                state.completed = true;
                state.position = audioEl.duration || 0;
                window.__speechPlayback["{cache_id}"] = state;
            }});

            audioEl.addEventListener("pause", () => {{
                window.__speechPlayback["{cache_id}"] = state;
            }});

            window.__speechPlayback["{cache_id}"] = state;
        </script>
    """
    components.html(html, height=0)


def _synthesize_with_cache(cache_id: str, text: str) -> bytes:
    cache = _get_audio_cache()
    if cache_id not in cache:
        cache[cache_id] = get_speech_service().synthesize(text)
    return cache[cache_id]


def _playback_state() -> Dict[str, Dict[str, Any]]:
    return st.session_state.setdefault(_AUDIO_EVENT_STATE_KEY, {})


def _typewriter_state() -> Dict[str, bool]:
    return st.session_state.setdefault(_TYPEWRITER_DONE_KEY, {})


def _clear_speech_states() -> None:
    _playback_state().clear()
    _typewriter_state().clear()
    st.session_state[_SESSION_VERSION_KEY] = st.session_state.get(_SESSION_VERSION_KEY, 0) + 1
    st.session_state.pop(_QUESTION_INDEX_TRACK_KEY, None)


def _reset_followup_states() -> None:
    playback = _playback_state()
    keys_to_remove = [key for key in playback if key.startswith("followup_")]
    for key in keys_to_remove:
        playback.pop(key, None)


def _text_version(text: str) -> str:
    if not text:
        base = "empty"
    else:
        base = hashlib.md5(text.encode("utf-8")).hexdigest()
    session_version = st.session_state.get(_SESSION_VERSION_KEY, 0)
    return f"{base}_{session_version}"


def _get_audio_cache() -> Dict[str, bytes]:
    return st.session_state.setdefault(_AUDIO_CACHE_KEY, {})


def _format_to_mime(fmt: str) -> str:
    lookup = {
        "mp3": "audio/mpeg",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "wav": "audio/wav",
        "ogg": "audio/ogg",
        "opus": "audio/ogg",
        "pcm": "audio/wav",
    }
    return lookup.get((fmt or "mp3").lower(), "audio/mpeg")
