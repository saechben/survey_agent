from __future__ import annotations

import base64
import hashlib
import time
from typing import Any, Dict, Sequence

import streamlit as st
import streamlit.components.v1 as components

from app.core.config import settings
from app.services.speech import OpenAISpeechService, SpeechServiceError

_AUDIO_CACHE_KEY = "speech_audio_cache"
_AUTO_TTS_STATE_KEY = "speech_auto_tts_enabled"
_AUTO_TTS_BUTTON_KEY = "speech_auto_tts_button"
_QUESTION_INDEX_TRACK_KEY = "speech_last_question_index"
_AUDIO_EVENT_STATE_KEY = "speech_audio_events"
_TYPEWRITER_DONE_KEY = "speech_typewriter_complete"
_TYPEWRITER_DELAY_SECONDS = 0.085
_SESSION_VERSION_KEY = "speech_audio_session_version"
_RECORDING_STATE_SUFFIX = "_recording_active"
_AUDIO_WIDGET_SUFFIX = "_audio_input"
_AUDIO_CACHE_META_KEY = "speech_audio_cache_meta"
_PREFETCH_STATE_KEY = "speech_question_prefetch_state"


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


def render_audio_record_button(form_key: str, *, help_text: str | None = None) -> None:
    """Render a microphone toggle button used to capture audio with Streamlit."""

    active_key = f"{form_key}{_RECORDING_STATE_SUFFIX}"
    audio_key = f"{form_key}{_AUDIO_WIDGET_SUFFIX}"
    is_active = bool(st.session_state.get(active_key, False))

    label = "⏹️" if is_active else "🎤"
    button_type = "primary" if is_active else "secondary"
    tooltip = help_text or (
        "Stop recording" if is_active else "Record your answer using your microphone."
    )

    clicked = st.button(
        label,
        key=f"{form_key}_record_button",
        type=button_type,
        use_container_width=True,
        help=tooltip,
    )

    if clicked:
        is_active = not is_active
        st.session_state[active_key] = is_active
        st.session_state.pop(audio_key, None)


def process_audio_recording(
    form_key: str,
    *,
    prompt: str,
) -> str | None:
    """Display the native audio recorder and return the transcript when available."""

    active_key = f"{form_key}{_RECORDING_STATE_SUFFIX}"
    audio_key = f"{form_key}{_AUDIO_WIDGET_SUFFIX}"

    if not st.session_state.get(active_key):
        return None

    st.caption("Recording active — use the control below to speak your answer.")
    audio_file = st.audio_input(prompt, key=audio_key)
    if not audio_file:
        return None

    audio_bytes = audio_file.getvalue()
    if not audio_bytes:
        st.warning("No audio captured. Try recording again.")
        return None

    try:
        with st.spinner("Transcribing audio..."):
            transcript = get_speech_service().transcribe(audio_bytes, mime_type=getattr(audio_file, "type", None))
    except SpeechServiceError as exc:  # pragma: no cover - UI feedback path
        st.error(f"Transcription failed: {exc}")
        st.session_state[active_key] = False
        st.session_state.pop(audio_key, None)
        return None
    except Exception as exc:  # pragma: no cover - UI feedback path
        st.error(f"Unexpected transcription error: {exc}")
        st.session_state[active_key] = False
        st.session_state.pop(audio_key, None)
        return None

    st.session_state[active_key] = False
    st.session_state.pop(audio_key, None)

    cleaned = (transcript or "").strip()
    if not cleaned:
        st.warning("No speech detected in the recording.")
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
    meta = _get_audio_cache_meta()
    version = _text_version(text)
    cached_bytes = cache.get(cache_id)
    if cached_bytes is not None and meta.get(cache_id) == version:
        return cached_bytes

    audio_bytes = get_speech_service().synthesize(text)
    cache[cache_id] = audio_bytes
    meta[cache_id] = version
    return audio_bytes


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


def _get_audio_cache_meta() -> Dict[str, str]:
    return st.session_state.setdefault(_AUDIO_CACHE_META_KEY, {})


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


def prefetch_question_audio(question_texts: Sequence[str]) -> Dict[str, Any]:
    """Eagerly synthesize audio for the main survey questions."""

    state = _prefetch_state()
    digest = _questions_digest(question_texts)
    total = len(question_texts)

    if state.get("digest") != digest:
        _reset_question_audio_cache()
        state.update(
            {
                "status": "idle",
                "completed": 0,
                "total": total,
                "errors": [],
                "digest": digest,
            }
        )
    else:
        state.setdefault("total", total)
        state.setdefault("errors", [])

    if (
        state.get("status") == "complete"
        and state.get("completed", 0) >= total
        and _question_audio_ready(question_texts)
    ):
        return state
    if state.get("status") == "complete" and not _question_audio_ready(question_texts):
        state.update({"status": "idle", "completed": 0})

    if total == 0:
        state.update({"status": "complete", "completed": 0})
        return state

    state["status"] = "running"

    completed = state.get("completed", 0)
    errors: list[Dict[str, Any]] = []

    for index, raw_text in enumerate(question_texts):
        cache_id = f"question_{index}"
        cleaned = (raw_text or "").strip()
        if not cleaned:
            completed = min(completed + 1, total)
            state["completed"] = completed
            continue

        try:
            _synthesize_with_cache(cache_id, cleaned)
        except SpeechServiceError as exc:
            errors.append({"index": index, "message": str(exc)})
        except Exception as exc:
            errors.append({"index": index, "message": str(exc)})

        completed = min(index + 1, total)
        state["completed"] = completed

    state["errors"] = errors
    state["status"] = "complete" if not errors else "partial"

    return state


def _prefetch_state() -> Dict[str, Any]:
    return st.session_state.setdefault(
        _PREFETCH_STATE_KEY,
        {"status": "idle", "completed": 0, "total": 0, "errors": [], "digest": ""},
    )


def _reset_question_audio_cache() -> None:
    cache = _get_audio_cache()
    meta = _get_audio_cache_meta()
    question_keys = [key for key in list(cache.keys()) if key.startswith("question_")]
    for key in question_keys:
        cache.pop(key, None)
        meta.pop(key, None)


def _question_audio_ready(question_texts: Sequence[str]) -> bool:
    cache = _get_audio_cache()
    meta = _get_audio_cache_meta()
    for index, raw_text in enumerate(question_texts):
        cleaned = (raw_text or "").strip()
        if not cleaned:
            continue
        cache_id = f"question_{index}"
        version = _text_version(cleaned)
        cached_version = meta.get(cache_id)
        audio_bytes = cache.get(cache_id)
        if cached_version != version or audio_bytes is None:
            return False
    return True


def _questions_digest(question_texts: Sequence[str]) -> str:
    normalized = "\n".join((value or "").strip() for value in question_texts)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()
