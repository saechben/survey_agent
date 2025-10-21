from __future__ import annotations

from collections import Counter
from typing import Dict, List

import matplotlib.pyplot as plt
import streamlit as st

from app.models.survey import SurveyQuestion

from . import followups, state


def render_analysis(questions: List[SurveyQuestion]) -> None:
    """Render static analysis charts for the captured survey responses."""

    responses = state.get_responses()
    total_questions = len(questions)
    answered = len(responses)

    if total_questions == 0:
        st.info("No survey questions available.")
        return

    st.header("Survey Overview")
    st.metric("Answered questions", f"{answered}/{total_questions}")

    if answered == 0:
        st.info("Complete the survey to see charts and insights.")
        return

    _render_answer_completion_chart(answered, total_questions)

    followup_responses = state.get_followup_responses()
    _render_question_breakdowns(questions, responses, followup_responses)


def _render_answer_completion_chart(answered: int, total_questions: int) -> None:
    """Render a simple bar chart showing answered vs remaining questions."""

    remaining = max(total_questions - answered, 0)
    fig, ax = plt.subplots()
    ax.bar(["Answered", "Remaining"], [answered, remaining], color=["#4b9cd3", "#d3d3d3"])
    ax.set_ylabel("Questions")
    ax.set_title("Completion Progress")
    for i, value in enumerate([answered, remaining]):
        ax.text(i, value + 0.05, str(value), ha="center", va="bottom")
    st.pyplot(fig)
    plt.close(fig)


def _render_question_breakdowns(
    questions: List[SurveyQuestion],
    responses: Dict[int, str],
    followup_responses: Dict[int, str],
) -> None:
    """Render per-question charts and summaries."""

    st.header("Per Question Details")

    for index, question in enumerate(questions):
        st.subheader(question.question)
        response = responses.get(index)

        if question.answer.type == "categorical" and response:
            _render_categorical_chart(question, response)
        elif response:
            _render_textual_summary(response)
        else:
            st.markdown("_No response recorded._")

        followup_entry = followups.get_entry(index)
        if followup_entry and followup_entry.get("text"):
            st.markdown(f"{followups.FOLLOW_UP_LABEL}{followup_entry['text']}")
            followup_answer = followup_responses.get(index)
            if followup_answer:
                _render_textual_summary(followup_answer, label="Follow-up answer")
            else:
                st.markdown("_No follow-up response recorded._")


def _render_categorical_chart(question: SurveyQuestion, response: str) -> None:
    """Render a bar chart showing the chosen categorical option."""

    counts = Counter({choice: 0 for choice in question.answer.choices})
    if response in counts:
        counts[response] += 1

    fig, ax = plt.subplots()
    labels = list(counts.keys())
    values = [counts[label] for label in labels]
    ax.bar(labels, values, color="#4b9cd3")
    ax.set_ylabel("Selections")
    ax.set_ylim(0, max(values + [1]))
    ax.set_title("Selected Answer")
    for idx, value in enumerate(values):
        ax.text(idx, value + 0.05, str(value), ha="center", va="bottom")
    st.pyplot(fig)
    plt.close(fig)


def _render_textual_summary(text: str, label: str = "Response summary") -> None:
    """Render a quick summary for free-text responses."""

    word_count = len(text.split())
    char_count = len(text)

    st.markdown(f"**{label}:**")
    st.write(text)
    st.caption(f"Characters: {char_count} • Words: {word_count}")

