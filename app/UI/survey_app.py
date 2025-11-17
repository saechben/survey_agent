from __future__ import annotations

import streamlit as st

from app.UI import components, navigation, speech_controls, state
from app.core.config import settings
from app.models.survey import Survey
from app.services.survey_loader import SurveyLoader


def run_app() -> None:
    """Entry point for the Streamlit-based survey UI."""

    st.set_page_config(page_title="Survey Assistant", page_icon="📝", layout="centered")

    try:
        default_survey = SurveyLoader(settings.survey_file_path).survey
    except FileNotFoundError as exc:
        default_survey = None
        if state.get_custom_survey() is None:
            st.error(str(exc))
            return

    active_survey: Survey | None = state.get_custom_survey() or default_survey
    if active_survey is None:
        st.error("No survey questions available. Please generate a survey to continue.")
        state.set_builder_active(True)
        components.render_survey_builder(
            on_cancel=lambda: state.set_builder_active(False),
            on_start=_build_custom_survey,
        )
        return

    questions = active_survey.questions
    total_questions = len(questions)

    prefetch_state = speech_controls.prefetch_question_audio([question.question for question in questions])
    components.render_prefetch_indicator(prefetch_state)

    state.ensure_defaults(total_questions)

    if total_questions == 0:
        st.info("No survey questions available.")
        return

    if not state.is_started():
        if state.is_builder_active():
            components.render_survey_builder(
                on_cancel=lambda: state.set_builder_active(False),
                on_start=_build_custom_survey,
            )
        else:
            components.render_start_page(
                on_start=_start_default_survey,
                on_generate=lambda: state.set_builder_active(True),
            )
        return

    components.render_fixed_logo()

    if state.is_complete():
        components.render_summary(questions)
        return

    current_index = state.get_current_index()
    question = questions[current_index]

    components.render_question_header(current_index, total_questions, question.question)
    components.render_answer_widget(question, current_index)

    answered_count = state.responses_count()
    st.caption(f"Answered {answered_count} of {total_questions} questions")

    navigation.render(question, total_questions)


def _start_default_survey() -> None:
    state.clear_custom_survey()
    state.reset()
    state.set_builder_active(False)
    state.mark_started(True)


def _build_custom_survey(survey: Survey) -> None:
    state.set_custom_survey(survey)
    state.reset()
    state.set_builder_active(False)
    state.mark_started(True)
