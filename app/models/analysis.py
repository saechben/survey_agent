from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class QuestionInsight(BaseModel):
    """Represents a survey question paired with captured responses."""

    index: int
    question: str
    answer_type: Literal["categorical", "free_text"]
    choices: List[str] = Field(default_factory=list)
    response: str | None = None
    follow_up_question: str | None = None
    follow_up_response: str | None = None

    model_config = {"extra": "forbid"}

    @property
    def has_primary_response(self) -> bool:
        """Return True when the main survey question has a response."""

        return bool(self.response and self.response.strip())

    @property
    def has_follow_up_response(self) -> bool:
        """Return True when a follow-up reply exists."""

        return bool(self.follow_up_response and self.follow_up_response.strip())


class SurveyAnalysisSnapshot(BaseModel):
    """Container describing the state of a survey for analysis purposes."""

    survey_id: str
    title: str | None = None
    questions: List[QuestionInsight] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @property
    def total_questions(self) -> int:
        """Return the number of questions represented in the snapshot."""

        return len(self.questions)

    @property
    def answered_count(self) -> int:
        """Count how many questions include a primary response."""

        return sum(1 for question in self.questions if question.has_primary_response)
