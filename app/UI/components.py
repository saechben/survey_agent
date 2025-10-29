from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List

import streamlit as st

from app.models.survey import SurveyQuestion

from . import analysis, followups, speech_controls, state

PLACEHOLDER_OPTION = "Select an option..."
_LOGO_PATH = Path(__file__).parent / "images" / "deloitte.jpg"
_PACMAN_PATH = Path(__file__).parent / "images" / "pacman.gif"


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


def render_prefetch_indicator(prefetch_state: Dict[str, Any] | None) -> None:
    """Display a floating progress indicator while question audio is warming up."""

    if not prefetch_state:
        return

    status = str(prefetch_state.get("status", "idle"))
    total = int(prefetch_state.get("total", 0) or 0)
    completed = int(prefetch_state.get("completed", 0) or 0)
    errors = prefetch_state.get("errors") or []

    show_indicator = False
    message = "Preparing survey"

    if status in {"idle", "running"}:
        show_indicator = total > 0
    elif status == "partial":
        show_indicator = True
        if errors:
            message = "Retrying audio prep"
    elif errors and status == "complete":
        show_indicator = True
        message = "Audio prep issues"

    if not show_indicator:
        return

    progress_ratio = 0.0
    if total > 0:
        progress_ratio = max(0.0, min(completed / total, 1.0))
    progress_percent = int(progress_ratio * 100)
    spinner_color = "#ffda1f" if not errors else "#ff4d4f"

    extra_detail = ""
    if total > 0:
        extra_detail = f"{completed}/{total}"
    if errors and status != "partial":
        message = "Audio prep needs attention"

    st.markdown(
        f"""
        <style>
        #survey-prefetch-indicator {{
            position: fixed;
            top: 1.5rem;
            right: 1.5rem;
            z-index: 2000;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.6rem 0.9rem;
            border-radius: 999px;
            background: rgba(20, 0, 33, 0.85);
            box-shadow: 0 0 16px rgba(255, 122, 201, 0.38);
            color: #faf5ff;
            font-size: 0.85rem;
            backdrop-filter: blur(6px);
            min-width: 210px;
        }}
        #survey-prefetch-indicator .spinner {{
            width: 18px;
            height: 18px;
            border-radius: 50%;
            border: 3px solid rgba(255, 255, 255, 0.25);
            border-top-color: {spinner_color};
            animation: survey-spin 0.9s linear infinite;
        }}
        #survey-prefetch-indicator .content {{
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            flex: 1;
        }}
        #survey-prefetch-indicator .label {{
            font-weight: 600;
            line-height: 1.2;
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
        }}
        #survey-prefetch-indicator .progress-track {{
            position: relative;
            width: 100%;
            height: 6px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.18);
            overflow: hidden;
        }}
        #survey-prefetch-indicator .progress-fill {{
            position: absolute;
            inset: 0;
            width: {progress_percent}%;
            background: linear-gradient(135deg, #ff007f, #ffda1f);
        }}
        @keyframes survey-spin {{
            to {{ transform: rotate(360deg); }}
        }}
        </style>
        <div id="survey-prefetch-indicator">
            <div class="spinner"></div>
            <div class="content">
                <div class="label">
                    <span>{message}</span>
                    <span>{extra_detail}</span>
                </div>
                <div class="progress-track">
                    <div class="progress-fill"></div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@lru_cache(maxsize=1)
def _load_pacman_background_base64() -> str | None:
    if not _PACMAN_PATH.exists():
        return None
    return base64.b64encode(_PACMAN_PATH.read_bytes()).decode("ascii")


def render_start_page(on_start: Callable[[], None]) -> None:
    """Display the introductory screen shown before the survey begins."""

    encoded = _load_pacman_background_base64()
    pacman_overlay = ""
    if encoded:
        pacman_overlay = f"""
        [data-testid="stAppViewContainer"]::after {{
            content: "";
            position: fixed;
            inset: 0;
            background-image: url("data:image/gif;base64,{encoded}");
            background-repeat: no-repeat;
            background-position: center 120%;
            background-size: min(35vmin, 260px);
            opacity: 0.8;
            pointer-events: none;
            image-rendering: pixelated;
            z-index: 0;
        }}
        """

    st.markdown(
        f"""
        <style>
        body {{
            background-color: #000;
        }}
        [data-testid="stAppViewContainer"] {{
            background-color: #000;
        }}
        [data-testid="stAppViewContainer"]::before {{
            display: none !important;
        }}
        {pacman_overlay}
        [data-testid="stAppViewContainer"] > .main {{
            position: relative;
            z-index: 1;
            background: transparent;
        }}
        [data-testid="stAppViewContainer"] > .main .block-container {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 0;
            background: transparent;
            gap: 2rem;
            text-align: center;
        }}
        .start-page-title {{
            font-size: 3rem;
            color: #fff;
            text-align: center;
            margin-bottom: 1.5rem;
            text-shadow: 0 0 24px rgba(255, 255, 255, 0.3);
        }}
        .start-page-subtitle {{
            color: #d5d5d5;
            font-size: 1.1rem;
            text-align: center;
            margin-bottom: 2.5rem;
        }}
        .stButton>button {{
            background: linear-gradient(135deg, #ff007f, #ffda1f 55%, #05f2f2);
            color: #140021;
            font-size: 1.2rem;
            padding: 1rem 3rem;
            border-radius: 999px;
            border: none;
            box-shadow: 0 0 30px rgba(255, 122, 201, 0.55);
            font-weight: 700;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
            position: relative;
            z-index: 1;
        }}
        .stButton>button:hover {{
            transform: translateY(-3px) scale(1.04);
            box-shadow: 0 0 46px rgba(255, 122, 201, 0.8);
        }}
        .stButton>button:focus {{
            outline: none;
            box-shadow: 0 0 0 0.25rem rgba(255, 0, 163, 0.45);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="start-page-title">Welcome to the survey</div>', unsafe_allow_html=True)
    st.markdown('<div class="start-page-subtitle">Take a breath, then press the button when you are ready.</div>', unsafe_allow_html=True)

    button_left, button_center, button_right = st.columns([1, 1, 1])
    with button_center:
        if st.button("Start survey", key="start_survey_button", type="primary"):
            on_start()


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
