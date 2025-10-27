from __future__ import annotations

from typing import Any, List, Sequence
from app.models.analysis import QuestionInsight, SurveyAnalysisSnapshot
from app.models.survey import SurveyQuestion
from app.services.survey_database import SurveyDatabaseInterface, get_survey_database

DEFAULT_SURVEY_ID = "active"


class SurveyDataProvider:
    """Expose survey data through an interchangeable API layer."""

    def __init__(
        self,
        questions: Sequence[SurveyQuestion],
        *,
        survey_id: str = DEFAULT_SURVEY_ID,
        database: SurveyDatabaseInterface | None = None,
    ) -> None:
        self._questions = list(questions)
        self._survey_id = survey_id
        self._database = database or get_survey_database()

    def get_survey_snapshot(self, survey_id: str | None = None) -> SurveyAnalysisSnapshot:
        """Return an immutable snapshot for the requested survey."""

        target_id = survey_id or self._survey_id
        if target_id != self._survey_id:
            raise KeyError(f"Unknown survey id: {target_id}")

        record = self._database.load_survey_results(target_id) if self._database else None
        if record is None:
            responses: dict[int, str] = {}
            followups: dict[int, dict[str, Any]] = {}
            followup_responses: dict[int, str] = {}
        else:
            responses = dict(record.responses)
            followups = {index: dict(value) for index, value in record.followups.items()}
            followup_responses = dict(record.followup_responses)

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



def _clean_str(value: Any) -> str | None:
    """Return a trimmed string representation or ``None``."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None
