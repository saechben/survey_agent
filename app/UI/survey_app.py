from __future__ import annotations

import time
from typing import List

import streamlit as st

from app.core.config import settings
from app.models.survey import SurveyQuestion
from app.services.LLM import LLM
from app.services.survey_loader import SurveyLoader

_PLACEHOLDER_OPTION = "Select an option..."
_FOLLOW_UP_LABEL = "**Follow-up question:** "
_FOLLOW_UP_RESPONSE_PREFIX = "followup_response_"
_STREAM_DELAY_SECONDS = 0.05


@st.cache_resource
def _get_llm() -> LLM:
    """Create the shared LLM client instance."""

    return LLM()


def _reset_state() -> None:
    """Reset all survey-related session state."""

    st.session_state.current_index = 0
    st.session_state.responses = {}
    st.session_state.survey_complete = False
    st.session_state.followups = {}
    st.session_state.followup_responses = {}
    st.session_state.generating_followup = False

    for key in [key for key in st.session_state.keys() if key.startswith("response_")]:
        del st.session_state[key]


def _ensure_session_defaults(total_questions: int) -> None:
    """Initialise session state defaults if they are missing."""

    if "current_index" not in st.session_state:
        st.session_state.current_index = 0
    if "responses" not in st.session_state:
        st.session_state.responses = {}
    if "survey_complete" not in st.session_state:
        st.session_state.survey_complete = False
    if "followups" not in st.session_state:
        st.session_state.followups = {}
    if "followup_responses" not in st.session_state:
        st.session_state.followup_responses = {}
    if "generating_followup" not in st.session_state:
        st.session_state.generating_followup = False

    if total_questions == 0:
        st.session_state.current_index = 0
    elif st.session_state.current_index >= total_questions:
        st.session_state.current_index = total_questions - 1


def _build_follow_up_prompt(question: str, answer: str) -> str:
    """Craft the prompt sent to the LLM."""

    return (
        "You are a thoughtful survey assistant. Given the original survey question and "
        "the respondent's answer, generate exactly one concise follow-up question that "
        "encourages them to elaborate further. Do not include any preamble or commentary.\n"
        f"Original question: {question}\n"
        f"Respondent answer: {answer}\n"
        "Follow-up question:"
    )


def _maybe_generate_followup(question_text: str, index: int, answer_text: str) -> None:
    """Generate and cache a follow-up question for a free-text response."""

    if not answer_text:
        st.session_state.followups.pop(index, None)
        st.session_state.followup_responses.pop(index, None)
        return

    entry = st.session_state.followups.get(index)
    if entry and entry.get("answer") == answer_text:
        return

    prompt = _build_follow_up_prompt(question_text, answer_text)

    try:
        st.session_state.generating_followup = True
        with st.spinner("Generating follow-up question..."):
            followup_text = _get_llm()(prompt).strip()
    except Exception as exc:  # pragma: no cover - UI feedback path
        st.session_state.followups.pop(index, None)
        st.session_state.followup_responses.pop(index, None)
        st.error(f"Could not generate a follow-up question: {exc}")
    else:
        st.session_state.followups[index] = {
            "answer": answer_text,
            "text": followup_text,
            "displayed": False,
        }
    finally:
        st.session_state.generating_followup = False


def _display_followup(index: int) -> None:
    """Display the follow-up question, animating it the first time."""

    entry = st.session_state.followups.get(index)
    if not entry or not entry.get("text"):
        return

    placeholder = st.container().empty()

    if entry.get("displayed"):
        placeholder.markdown(_FOLLOW_UP_LABEL + entry["text"])
        return

    words = entry["text"].split()
    accumulated = ""
    for word in words:
        accumulated = (accumulated + " " + word).strip()
        placeholder.markdown(_FOLLOW_UP_LABEL + accumulated)
        time.sleep(_STREAM_DELAY_SECONDS)

    entry["displayed"] = True
    st.session_state.followups[index] = entry


def _handle_free_text_change(question_text: str, index: int, widget_key: str) -> None:
    """Callback triggered whenever the free-text input changes."""

    raw_value = st.session_state.get(widget_key, "")
    cleaned = raw_value.strip()
    if cleaned:
        st.session_state.responses[index] = cleaned
        _maybe_generate_followup(question_text, index, cleaned)
    else:
        st.session_state.responses.pop(index, None)
        st.session_state.followups.pop(index, None)
        st.session_state.followup_responses.pop(index, None)


def _render_answer_widget(question: SurveyQuestion, index: int) -> None:
    """Render the appropriate input widget for the given question."""

    answer = question.answer
    widget_key = f"response_{index}"

    if answer.type == "categorical":
        options = [_PLACEHOLDER_OPTION, *answer.choices]

        if widget_key not in st.session_state:
            default = st.session_state.responses.get(index, _PLACEHOLDER_OPTION)
            st.session_state[widget_key] = default if default in options else _PLACEHOLDER_OPTION

        selection = st.radio(
            "Select an answer",
            options=options,
            key=widget_key,
        )
        if selection == _PLACEHOLDER_OPTION:
            st.session_state.responses.pop(index, None)
        else:
            st.session_state.responses[index] = selection
    else:
        if widget_key not in st.session_state:
            st.session_state[widget_key] = st.session_state.responses.get(index, "")

        response = st.text_area(
            "Your answer",
            key=widget_key,
            placeholder="Type your answer here...",
            on_change=_handle_free_text_change,
            args=(question.question, index, widget_key),
        )
        cleaned = response.strip()
        if cleaned:
            st.session_state.responses[index] = cleaned
            _maybe_generate_followup(question.question, index, cleaned)
        else:
            st.session_state.responses.pop(index, None)
            st.session_state.followups.pop(index, None)
            st.session_state.followup_responses.pop(index, None)

        _display_followup(index)
        _render_followup_response_input(index)


def _render_summary(questions: List[SurveyQuestion]) -> None:
    """Display a summary of the captured survey responses."""

    st.success("Thank you for completing the survey!")
    st.markdown("### Your responses")

    followups = st.session_state.get("followups", {})
    followup_answers = st.session_state.get("followup_responses", {})

    for idx, question in enumerate(questions):
        st.markdown(f"**{question.question}**")
        response = st.session_state.responses.get(idx)
        if response:
            st.write(response)
        else:
            st.markdown("_No response recorded._")

        followup_entry = followups.get(idx)
        if followup_entry and followup_entry.get("text"):
            st.markdown(f"{_FOLLOW_UP_LABEL}{followup_entry['text']}")
            followup_response = followup_answers.get(idx)
            if followup_response:
                st.write(followup_response)
            else:
                st.markdown("_No follow-up response recorded._")

    st.divider()
    st.button("Restart survey", on_click=_reset_state)


def run_app() -> None:
    """Entry point for the Streamlit-based survey UI."""

    st.set_page_config(page_title="Survey Assistant", page_icon="📝", layout="centered")

    try:
        survey = SurveyLoader(settings.survey_file_path).survey
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    questions = survey.questions
    total_questions = len(questions)

    _ensure_session_defaults(total_questions)

    if total_questions == 0:
        st.info("No survey questions available.")
        return

    if st.session_state.survey_complete:
        _render_summary(questions)
        return

    current_index = st.session_state.current_index
    question = questions[current_index]

    st.progress((current_index + 1) / total_questions)
    st.markdown(f"### Question {current_index + 1} of {total_questions}")
    st.write(question.question)

    _render_answer_widget(question, current_index)

    answered_count = len(st.session_state.responses)
    st.caption(f"Answered {answered_count} of {total_questions} questions")

    def _go_previous() -> None:
        if st.session_state.current_index > 0:
            st.session_state.current_index -= 1
        st.session_state.survey_complete = False

    def _go_next() -> None:
        if st.session_state.current_index < total_questions - 1:
            st.session_state.current_index += 1
        st.session_state.survey_complete = False

    def _finish() -> None:
        st.session_state.survey_complete = True

    prev_col, next_col, finish_col = st.columns(3)
    with prev_col:
        st.button("Previous", on_click=_go_previous, disabled=current_index == 0)
    with next_col:
        st.button("Next", on_click=_go_next, disabled=current_index >= total_questions - 1)
    with finish_col:
        st.button("Finish Survey", on_click=_finish, disabled=current_index != total_questions - 1)


def _render_followup_response_input(index: int) -> None:
    """Render an input for the user to answer the follow-up question."""

    entry = st.session_state.followups.get(index)
    if not entry or not entry.get("text"):
        return

    placeholder = st.container()

    if st.session_state.followups[index].get("displayed") is False:
        # Delay rendering of the input until the follow-up has fully animated
        placeholder.empty()
        return

    response_key = f"{_FOLLOW_UP_RESPONSE_PREFIX}{index}"
    existing_response = st.session_state.followup_responses.get(index, "")

    response = placeholder.text_area(
        "Your follow-up answer",
        key=response_key,
        placeholder="Share more details here...",
        value=existing_response,
        height=100,
    )

    cleaned = response.strip()
    if cleaned:
        st.session_state.followup_responses[index] = cleaned
    else:
        st.session_state.followup_responses.pop(index, None)
