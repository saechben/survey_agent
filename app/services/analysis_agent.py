from __future__ import annotations

from textwrap import dedent

from app.API.survey_data_provider import SurveyDataProvider
from app.models.analysis import QuestionInsight, SurveyAnalysisSnapshot
from app.services.LLM import LLM, LLMInterface


class SurveyAnalysisAgent:
    """LLM-backed agent that answers questions about the captured survey data."""

    def __init__(
        self,
        data_provider: SurveyDataProvider,
        *,
        llm: LLMInterface | None = None,
    ) -> None:
        if data_provider is None:
            raise ValueError("data_provider must be provided")

        self._provider = data_provider
        self._llm = llm or LLM()

    def answer(self, query: str, survey_id: str | None = None) -> str:
        """Return an LLM-generated answer grounded in survey responses."""

        cleaned_query = (query or "").strip()
        if not cleaned_query:
            raise ValueError("query must be a non-empty string")

        snapshot = self._provider.get_survey_snapshot(survey_id)
        if snapshot.total_questions == 0:
            return "No survey questions are available to analyse."
        if snapshot.answered_count == 0:
            return "No responses have been recorded for this survey yet."

        prompt = self._build_prompt(cleaned_query, snapshot)
        try:
            response = self._llm(prompt).strip()
        except Exception as exc:  # pragma: no cover - delegated to runtime
            return f"I couldn't generate an answer right now: {exc}"

        return response or "I couldn't find relevant information to answer that question."

    def _build_prompt(self, query: str, snapshot: SurveyAnalysisSnapshot) -> str:
        """Create the LLM prompt using the provided snapshot and user query."""

        answered_sections = [
            self._format_question_section(question)
            for question in snapshot.questions
            if question.has_primary_response or question.has_follow_up_response
        ]
        context_block = "\n\n".join(answered_sections) if answered_sections else "No answered questions."

        return dedent(
            f"""
            You are a survey analysis assistant. You will receive a collection of survey questions
            along with the participant's primary answers and optional follow-up discussions that are not necessarily the same for each survey.
            Use only this information to answer the user's question. Do not invent data and make clear
            when the available responses are insufficient.

            Survey overview:
              - Survey id: {snapshot.survey_id}
              - Answered questions: {snapshot.answered_count} / {snapshot.total_questions}

            Survey responses:
            {context_block}

            User question: {query}

            The format of the answer should be structured in bullet points and concise
            """
        ).strip()

    def _format_question_section(self, question: QuestionInsight) -> str:
        """Format a single question's context for the LLM prompt."""

        lines = [
            f"Question {question.index + 1}: {question.question}",
            f"Primary answer: {question.response or 'No response provided.'}",
        ]
        if question.follow_up_question:
            lines.append(f"Follow-up question: {question.follow_up_question}")
        if question.follow_up_response:
            lines.append(f"Follow-up answer: {question.follow_up_response}")
        elif question.follow_up_question:
            lines.append("Follow-up answer: Not provided.")

        return "\n".join(lines)
