from __future__ import annotations

from typing import Any, List, MutableMapping, Sequence

import streamlit as st

from app.UI import state as ui_state
from app.models.analysis import QuestionInsight, SurveyAnalysisSnapshot
from app.models.survey import SurveyQuestion

RESPONSES_KEY = ui_state.RESPONSES_KEY
FOLLOWUPS_KEY = ui_state.FOLLOWUPS_KEY
FOLLOWUP_RESPONSES_KEY = ui_state.FOLLOWUP_RESPONSES_KEY

DEFAULT_SURVEY_ID = "active"


class SurveyDataProvider:
    """Expose survey data through an interchangeable API layer."""

    def __init__(
        self,
        questions: Sequence[SurveyQuestion],
        *,
        survey_id: str = DEFAULT_SURVEY_ID,
        session_state: MutableMapping[str, Any] | None = None,
    ) -> None:
        self._questions = list(questions)
        self._survey_id = survey_id
        self._session_state = session_state

    @property
    def _session(self) -> MutableMapping[str, Any]:
        if self._session_state is not None:
            return self._session_state
        return st.session_state

    def list_surveys(self) -> List[str]:
        """Return all available survey identifiers."""

        if not self._questions:
            return []
        return [self._survey_id]

    def get_survey_snapshot(self, survey_id: str | None = None) -> SurveyAnalysisSnapshot:
        """Return an immutable snapshot for the requested survey."""

        target_id = survey_id or self._survey_id
        if target_id != self._survey_id:
            raise KeyError(f"Unknown survey id: {target_id}")

        session = self._session
        responses = dict(session.get(RESPONSES_KEY, {}))
        followups = dict(session.get(FOLLOWUPS_KEY, {}))
        followup_responses = dict(session.get(FOLLOWUP_RESPONSES_KEY, {}))

        question_insights: List[QuestionInsight] = []
        for index, question in enumerate(self._questions):
            answer_type = question.answer.type
            choices: List[str] = []
            if answer_type == "categorical":
                choices = list(getattr(question.answer, "choices", []))

            followup_entry = followups.get(index) or {}
            question_insights.append(
                QuestionInsight(
                    index=index,
                    question=question.question,
                    answer_type=answer_type,
                    choices=choices,
                    response=_clean_str(responses.get(index)),
                    follow_up_question=_clean_str(followup_entry.get("text")),
                    follow_up_response=_clean_str(followup_responses.get(index)),
                )
            )

        return SurveyAnalysisSnapshot(
            survey_id=target_id,
            title=None,
            questions=question_insights,
        )

    def list_question_responses(self, survey_id: str | None = None) -> List[QuestionInsight]:
        """Return ordered question insights for the requested survey."""

        snapshot = self.get_survey_snapshot(survey_id)
        return snapshot.questions

    def get_question_response(self, index: int, survey_id: str | None = None) -> QuestionInsight:
        """Return a single question insight for the requested survey."""

        snapshot = self.get_survey_snapshot(survey_id)
        try:
            return snapshot.questions[index]
        except IndexError as exc:  # pragma: no cover - defensive branch
            raise IndexError(f"Invalid question index: {index}") from exc


def _clean_str(value: Any) -> str | None:
    """Return a trimmed string representation or ``None``."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None
