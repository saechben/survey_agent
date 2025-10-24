from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, List, Sequence, Tuple

from app.API.survey_data_provider import SurveyDataProvider
from app.models.analysis import QuestionInsight, SurveyAnalysisSnapshot


class ChartType(str, Enum):
    """Supported chart shapes for survey visualisations."""

    BAR = "bar"
    PIE = "pie"


@dataclass(frozen=True)
class ChartData:
    """Structured payload describing a chart for the UI layer."""

    chart_type: ChartType
    labels: Tuple[str, ...]
    values: Tuple[float, ...]
    title: str
    question_index: int | None = None
    question_text: str | None = None
    description: str | None = None
    metadata: dict[str, int | float | str] = field(default_factory=dict)

    def to_series(self) -> List[Tuple[str, float]]:
        """Return data as a list of (label, value) tuples."""

        return list(zip(self.labels, self.values))

    def as_dict(self) -> dict[str, float]:
        """Return data as a simple label -> value mapping."""

        return {label: value for label, value in zip(self.labels, self.values)}


class SurveyChartBuilder:
    """Prepare chart-ready data derived from survey responses."""

    def __init__(
        self,
        data_provider: SurveyDataProvider,
        *,
        default_survey_id: str | None = None,
        max_terms: int = 10,
    ) -> None:
        if data_provider is None:
            raise ValueError("data_provider must be provided")
        if max_terms <= 0:
            raise ValueError("max_terms must be a positive integer")

        self._provider = data_provider
        self._default_survey_id = default_survey_id
        self._max_terms = max_terms

    def completion_summary(self, survey_id: str | None = None) -> ChartData:
        """Return a chart describing answered vs unanswered questions."""

        snapshot = self._snapshot(survey_id)
        answered = snapshot.answered_count
        unanswered = max(snapshot.total_questions - answered, 0)
        labels = ("Answered", "Unanswered")
        values = (float(answered), float(unanswered))
        title = "Survey completion overview"
        description = "Shows how many questions include a primary response."
        metadata = {
            "total_questions": snapshot.total_questions,
            "answered": answered,
            "unanswered": unanswered,
        }
        return ChartData(
            chart_type=ChartType.BAR,
            labels=labels,
            values=values,
            title=title,
            question_index=None,
            question_text=None,
            description=description,
            metadata=metadata,
        )

    def question_chart(
        self,
        index: int,
        *,
        chart_type: ChartType | str | None = None,
        survey_id: str | None = None,
    ) -> ChartData:
        """Return chart data for a single survey question."""

        question = self._provider.get_question_response(index, survey_id or self._default_survey_id)
        resolved_type = self._resolve_chart_type(chart_type, question)
        if resolved_type == ChartType.BAR:
            return self._build_bar_chart(question)
        if resolved_type == ChartType.PIE:
            return self._build_pie_chart(question)
        raise ValueError(f"Unsupported chart type: {resolved_type}")

    def all_question_charts(
        self,
        *,
        chart_type: ChartType | str | None = None,
        survey_id: str | None = None,
    ) -> List[ChartData]:
        """Return chart data for each question with at least one recorded response."""

        snapshot = self._snapshot(survey_id)
        charts: List[ChartData] = []
        for question in snapshot.questions:
            if not question.has_primary_response and not question.has_follow_up_response:
                continue
            charts.append(self.question_chart(question.index, chart_type=chart_type, survey_id=survey_id))
        return charts

    def _snapshot(self, survey_id: str | None) -> SurveyAnalysisSnapshot:
        target = survey_id or self._default_survey_id
        return self._provider.get_survey_snapshot(target)

    def _resolve_chart_type(
        self,
        chart_type: ChartType | str | None,
        question: QuestionInsight,
    ) -> ChartType:
        if chart_type is None:
            if question.answer_type == "categorical":
                return ChartType.BAR
            return ChartType.BAR

        if isinstance(chart_type, str):
            try:
                resolved = ChartType(chart_type)
            except ValueError as exc:
                raise ValueError(f"Unknown chart type: {chart_type}") from exc
        else:
            resolved = chart_type

        if resolved == ChartType.PIE and question.answer_type != "categorical":
            raise ValueError("Pie charts are only supported for categorical questions.")

        return resolved

    def _build_bar_chart(self, question: QuestionInsight) -> ChartData:
        if question.answer_type == "categorical":
            labels, values = self._categorical_distribution(question)
            description = "Choice distribution for the recorded response."
        else:
            labels, values = self._textual_term_frequency(question)
            description = "Most common terms found in the recorded response."

        return ChartData(
            chart_type=ChartType.BAR,
            labels=labels,
            values=values,
            title=f"Responses for question {question.index + 1}",
            question_index=question.index,
            question_text=question.question,
            description=description,
            metadata={"answer_type": question.answer_type},
        )

    def _build_pie_chart(self, question: QuestionInsight) -> ChartData:
        labels, values = self._categorical_distribution(question)
        return ChartData(
            chart_type=ChartType.PIE,
            labels=labels,
            values=values,
            title=f"Responses for question {question.index + 1}",
            question_index=question.index,
            question_text=question.question,
            description="Choice distribution for the recorded response.",
            metadata={"answer_type": question.answer_type},
        )

    def _categorical_distribution(self, question: QuestionInsight) -> Tuple[Tuple[str, ...], Tuple[float, ...]]:
        if question.answer_type != "categorical":
            raise ValueError("Categorical distribution requested for non-categorical question.")

        labels: List[str] = []
        values: List[float] = []
        recorded_choice = (question.response or "").strip()
        for choice in question.choices:
            labels.append(choice)
            values.append(1.0 if choice == recorded_choice else 0.0)

        if not labels:
            labels.append("No choices configured")
            values.append(0.0)

        if not recorded_choice:
            labels.append("No response recorded")
            values.append(1.0)

        return tuple(labels), tuple(values)

    def _textual_term_frequency(self, question: QuestionInsight) -> Tuple[Tuple[str, ...], Tuple[float, ...]]:
        response = (question.response or "").strip()
        if not response:
            return ("No response recorded",), (1.0,)

        tokens = self._tokenise(response)
        if not tokens:
            return ("No tokens extracted",), (1.0,)

        counts = Counter(tokens)
        most_common = counts.most_common(self._max_terms)
        labels = tuple(label for label, _ in most_common)
        values = tuple(float(value) for _, value in most_common)
        return labels, values

    @staticmethod
    def _tokenise(text: str) -> Iterable[str]:
        for token in re.findall(r"[A-Za-z0-9']+", text.lower()):
            if token:
                yield token


__all__ = [
    "ChartData",
    "ChartType",
    "SurveyChartBuilder",
]
