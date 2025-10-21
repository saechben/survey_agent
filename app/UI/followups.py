from __future__ import annotations

import time
from typing import Dict, Optional

import streamlit as st

from app.models.survey import SurveyQuestion
from app.services.LLM import LLM

from . import state

FOLLOW_UP_LABEL = "**Follow-up question:** "
FOLLOW_UP_RESPONSE_PREFIX = "followup_response_"
_STREAM_DELAY_SECONDS = 0.05


@st.cache_resource
def _get_llm() -> LLM:
    """Return the shared LLM client instance."""

    return LLM()


def _build_prompt(question: str, answer: str) -> str:
    """Craft the prompt used for the follow-up generation."""

    return (
        "You are a thoughtful survey assistant. Given the original survey question and "
        "the respondent's answer, generate exactly one concise follow-up question that "
        "encourages them to elaborate further. Do not include any preamble or commentary.\n"
        f"Original question: {question}\n"
        f"Respondent answer: {answer}\n"
        "Follow-up question:"
    )


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

    prompt = _build_prompt(question.question, cleaned)

    try:
        state.set_generating_followup(True)
        with st.spinner("Generating follow-up question..."):
            followup_text = _get_llm()(prompt).strip()
    except Exception as exc:  # pragma: no cover - UI feedback path
        fallback_text = _build_fallback_follow_up(question.question, cleaned)
        state.set_followup(
            index,
            {
                "answer": cleaned,
                "text": fallback_text,
                "displayed": False,
                "source": "fallback",
            },
        )
        st.warning("Using a fallback follow-up question while the AI helper is unavailable.")
        st.caption(f"Follow-up generation error: {exc}")
    else:
        state.set_followup(
            index,
            {
                "answer": cleaned,
                "text": followup_text,
                "displayed": False,
            },
        )
    finally:
        state.set_generating_followup(False)


def render_followup_question(index: int) -> None:
    """Render the follow-up question, animating the text on first display."""

    entry = get_entry(index)
    if not entry or not entry.get("text"):
        return

    placeholder = st.container().empty()

    if entry.get("displayed"):
        placeholder.markdown(FOLLOW_UP_LABEL + str(entry["text"]))
        return

    words = str(entry["text"]).split()
    accumulated = ""
    for word in words:
        accumulated = (accumulated + " " + word).strip()
        placeholder.markdown(FOLLOW_UP_LABEL + accumulated)
        time.sleep(_STREAM_DELAY_SECONDS)

    entry["displayed"] = True
    state.set_followup(index, entry)


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
    existing = state.get_followup_responses().get(index, "")

    response = placeholder.text_area(
        "Your follow-up answer",
        key=response_key,
        placeholder="Share more details here...",
        value=existing,
        height=100,
    )

    cleaned = response.strip()
    if cleaned:
        state.set_followup_response(index, cleaned)
    else:
        state.clear_followup_response(index)

