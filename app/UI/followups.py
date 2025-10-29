from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

from app.models.survey import SurveyQuestion
from app.services.followup_agent import FollowUpAgent

from . import speech_controls, state

FOLLOW_UP_LABEL = "**Follow-up question:** "
FOLLOW_UP_RESPONSE_PREFIX = "followup_response_"


@st.cache_resource
def _get_agent() -> FollowUpAgent:
    """Return the shared follow-up decision agent."""

    return FollowUpAgent()


def _build_fallback_follow_up(question: str, answer: str) -> str:
    """Generate a deterministic follow-up question when the LLM is unavailable."""

    snippet = answer if len(answer) <= 120 else f"{answer[:117]}..."
    return (
        f"You mentioned '{snippet}' when asked '{question}'. "
        "Could you share a bit more detail?"
    )


def get_entry(index: int) -> Optional[Dict[str, object]]:
    """Return the follow-up metadata for a question index, if available."""

    return state.get_followups().get(index)


def clear(index: int) -> None:
    """Remove cached follow-up question and response data for a question."""

    state.clear_followup(index)
    state.clear_followup_response(index)
    state.clear_followup_requirement(index)
    st.session_state.pop(f"{FOLLOW_UP_RESPONSE_PREFIX}{index}", None)


def maybe_generate(question: SurveyQuestion, index: int, answer_text: str) -> None:
    """Generate and cache a follow-up question for a free-text response."""

    cleaned = answer_text.strip()
    if not cleaned:
        clear(index)
        return

    entry = get_entry(index)
    if entry and entry.get("answer") == cleaned:
        return

    state.clear_followup_response(index)
    state.mark_followup_required(index)

    try:
        state.set_generating_followup(True)
        with st.spinner("Generating follow-up question..."):
            decision = _get_agent().decide(question.question, cleaned)
    except Exception as exc:  # pragma: no cover - UI feedback path
        fallback_text = _build_fallback_follow_up(question.question, cleaned)
        state.set_followup(
            index,
            {
                "answer": cleaned,
                "text": fallback_text,
                "displayed": False,
                "source": "fallback",
                "should_ask": True,
                "rationale": None,
            },
        )
        st.warning("Using a fallback follow-up question while the AI helper is unavailable.")
        st.caption(f"Follow-up generation error: {exc}")
    else:
        rationale = getattr(decision, "rationale", None)
        if not getattr(decision, "should_ask", False):
            state.set_followup(
                index,
                {
                    "answer": cleaned,
                    "text": None,
                    "displayed": True,
                    "source": "agent_skip",
                    "should_ask": False,
                    "rationale": rationale,
                },
            )
            state.clear_followup_requirement(index)
        else:
            followup_text = (decision.follow_up_question or "").strip()
            if not followup_text:
                followup_text = _build_fallback_follow_up(question.question, cleaned)
                source = "fallback_empty"
            else:
                source = "agent"
            state.set_followup(
                index,
                {
                    "answer": cleaned,
                    "text": followup_text,
                    "displayed": False,
                    "source": source,
                    "should_ask": True,
                    "rationale": rationale,
                },
            )
    finally:
        state.set_generating_followup(False)

    entry = get_entry(index)
    if entry and entry.get("should_ask") is False:
        state.clear_followup_requirement(index)


def render_followup_question(index: int) -> None:
    """Render the follow-up question, animating the text on first display."""

    entry = get_entry(index)
    if not entry or not entry.get("text"):
        return

    text_value = str(entry["text"])

    cache_id = f"followup_{index}"
    auto_enabled = speech_controls.is_auto_tts_enabled()

    if entry.get("displayed") is False:
        entry["displayed"] = True
        state.set_followup(index, entry)

    speech_controls.maybe_autoplay_followup(
        text_value,
        cache_id=cache_id,
    )
    speech_controls.render_question_text(
        text_value,
        cache_id=cache_id,
        animate=auto_enabled,
        prefix_markdown=FOLLOW_UP_LABEL,
    )


def render_followup_response_input(index: int) -> None:
    """Render a text area to capture the user's follow-up response."""

    entry = get_entry(index)
    if not entry or not entry.get("text"):
        return

    placeholder = st.container()
    if entry.get("displayed") is False:
        placeholder.empty()
        return

    response_key = f"{FOLLOW_UP_RESPONSE_PREFIX}{index}"
    voice_key = f"{response_key}_voice_response"
    existing = state.get_followup_responses().get(index, "")

    if response_key not in st.session_state:
        st.session_state[response_key] = existing

    with placeholder:
        text_col, mic_col = st.columns([12, 1], vertical_alignment="bottom")
        with mic_col:
            speech_controls.render_audio_record_button(
                form_key=f"followup_{index}",
                help_text="Record your follow-up answer with your microphone.",
            )
        with text_col:
            transcript = speech_controls.process_audio_recording(
                form_key=f"followup_{index}",
                prompt="Record your follow-up answer",
            )

            typed_value = str(st.session_state.get(response_key, "")).strip()
            voice_value = st.session_state.get(voice_key)

            if transcript:
                cleaned_transcript = transcript.strip()
                if cleaned_transcript:
                    st.session_state[voice_key] = cleaned_transcript
                    voice_value = cleaned_transcript
                else:
                    st.session_state.pop(voice_key, None)
                    voice_value = None

            if typed_value:
                final_value = typed_value
                if voice_value is not None:
                    st.session_state.pop(voice_key, None)
                    voice_value = None
            else:
                final_value = voice_value or ""

            if final_value:
                state.set_followup_response(index, final_value)
                state.clear_followup_requirement(index)
            else:
                st.session_state.pop(voice_key, None)
                state.clear_followup_response(index)
                if entry and entry.get("text"):
                    state.mark_followup_required(index)

            display_value = typed_value if typed_value else (voice_value or "")
            st.session_state[response_key] = display_value

            st.text_area(
                "Your follow-up answer",
                key=response_key,
                placeholder="Share more details here...",
                height=100,
            )
            transcript_placeholder = st.empty()

            preview_text = st.session_state.get(voice_key)
            if preview_text:
                transcript_placeholder.markdown(f"_Recorded follow-up answer:_ {preview_text}")
            else:
                transcript_placeholder.empty()
