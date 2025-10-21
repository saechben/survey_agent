from __future__ import annotations

import streamlit as st

from app.UI import analysis, state
from app.core.config import settings
from app.services.survey_loader import SurveyLoader

st.set_page_config(page_title="Survey Analysis", page_icon="📊", layout="wide")


def _load_questions():
    try:
        survey = SurveyLoader(settings.survey_file_path).survey
    except FileNotFoundError as exc:
        st.error(str(exc))
        return []
    return survey.questions


questions = _load_questions()
state.ensure_defaults(len(questions))
analysis.render_analysis(questions)
