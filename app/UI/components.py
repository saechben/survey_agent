from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import List

import streamlit as st

from app.models.survey import SurveyQuestion

from . import analysis, followups, speech_controls, state

PLACEHOLDER_OPTION = "Select an option..."
_LOGO_PATH = Path(__file__).parent / "images" / "deloitte.jpg"


@lru_cache(maxsize=1)
def _load_logo_base64() -> str | None:
    if not _LOGO_PATH.exists():
        return None
    return base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")


def render_fixed_logo() -> None:
    """Render the Deloitte logo fixed to the top-left corner."""

    encoded = _load_logo_base64()
    if not encoded:
        return

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"]::before {{
            content: "";
            position: fixed;
            top: 3rem;
            left: 0.75rem;
            display: block;
            width: 280px;
            height: 160px;
            background-image: url("data:image/jpeg;base64,{encoded}");
            background-size: contain;
            background-repeat: no-repeat;
            background-position: top left;
            z-index: 1000;
            pointer-events: none;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_question_header(current_index: int, total_questions: int, question_text: str) -> None:
    """Render progress information and the active question text."""

    st.progress((current_index + 1) / total_questions)
    header_col, toggle_col = st.columns([3, 1])
    with header_col:
        st.markdown(f"### Question {current_index + 1} of {total_questions}")
    with toggle_col:
        auto_enabled = speech_controls.render_tts_toggle()

    question_cache_id = speech_controls.prepare_question_render(current_index)
    speech_controls.autoplay_question(
        question_text,
        cache_id=question_cache_id,
        enabled=auto_enabled,
    )
    speech_controls.render_question_text(
        question_text,
        cache_id=question_cache_id,
        animate=auto_enabled,
    )
    speech_controls.render_playback_button(
        question_text,
        label="🔊 Play question audio",
        cache_id=question_cache_id,
    )


def render_answer_widget(question: SurveyQuestion, index: int) -> None:
    """Render the appropriate Streamlit widget for the survey question."""

    answer = question.answer
    widget_key = f"response_{index}"
    form_key = f"question_{index}"

    if answer.type == "categorical":
        options = [PLACEHOLDER_OPTION, *answer.choices]

        if widget_key not in st.session_state:
            default = state.get_response(index) or PLACEHOLDER_OPTION
            st.session_state[widget_key] = default if default in options else PLACEHOLDER_OPTION

        selection = st.radio("Select an answer", options=options, key=widget_key)
        if selection == PLACEHOLDER_OPTION:
            state.clear_response(index, forget_widget=False)
            followups.clear(index)
        else:
            state.set_response(index, selection)
            followups.clear(index)
        return

    voice_key = f"{form_key}_voice_response"

    text_col, mic_col = st.columns([12, 1], vertical_alignment="bottom")
    with mic_col:
        speech_controls.render_audio_record_button(
            form_key=form_key,
            help_text="Record your answer with your microphone.",
        )

    with text_col:
        transcript = speech_controls.process_audio_recording(
            form_key=form_key,
            prompt="Record your answer",
        )

        if widget_key not in st.session_state:
            st.session_state[widget_key] = state.get_response(index) or ""

        typed_value = str(st.session_state.get(widget_key, "")).strip()
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
            if state.get_response(index) != final_value:
                state.set_response(index, final_value)
        else:
            st.session_state.pop(voice_key, None)
            state.clear_response(index)
            followups.clear(index)

        display_value = typed_value if typed_value else (voice_value or "")
        st.session_state[widget_key] = display_value

        st.text_area(
            "Your answer",
            key=widget_key,
            placeholder="Type your answer here...",
        )
        transcript_placeholder = st.empty()

        preview_text = st.session_state.get(voice_key)
        if preview_text:
            transcript_placeholder.markdown(f"_Recorded answer:_ {preview_text}")
        else:
            transcript_placeholder.empty()

    followups.render_followup_question(index)
    followups.render_followup_response_input(index)


def render_summary(questions: List[SurveyQuestion]) -> None:
    """Display a summary view of collected responses and follow-ups."""

    st.success("Thank you for completing the survey!")
    st.markdown("### Your responses")

    followups_map = state.get_followups()
    followup_answers = state.get_followup_responses()

    for idx, question in enumerate(questions):
        st.markdown(f"**{question.question}**")
        response = state.get_response(idx)
        if response:
            st.write(response)
        else:
            st.markdown("_No response recorded._")

        entry = followups_map.get(idx)
        if entry and entry.get("text"):
            st.markdown(f"{followups.FOLLOW_UP_LABEL}{entry['text']}")
            followup_response = followup_answers.get(idx)
            if followup_response:
                st.write(followup_response)
            else:
                st.markdown("_No follow-up response recorded._")

    st.divider()

    analyze_clicked = st.button(
        "Analyze results",
        key="analyze_results_button",
        type="primary",
        disabled=state.is_analysis_visible(),
    )
    if analyze_clicked:
        state.set_analysis_visible(True)

    if state.is_analysis_visible():
        analysis.render_analysis(questions)
        st.divider()

    if st.button("Restart survey", key="restart_survey_button"):
        state.reset()
