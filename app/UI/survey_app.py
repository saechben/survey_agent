from __future__ import annotations

import streamlit as st

from app.UI import components, navigation, state
from app.core.config import settings
from app.services.survey_loader import SurveyLoader


def run_app() -> None:
    """Entry point for the Streamlit-based survey UI."""

    st.set_page_config(page_title="Survey Assistant", page_icon="📝", layout="centered")
    components.render_fixed_logo()

    try:
        survey = SurveyLoader(settings.survey_file_path).survey
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

    questions = survey.questions
    total_questions = len(questions)

    state.ensure_defaults(total_questions)

    if total_questions == 0:
        st.info("No survey questions available.")
        return

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
