from __future__ import annotations

from typing import List

import streamlit as st

from app.models.survey import SurveyQuestion

from . import followups, state

PLACEHOLDER_OPTION = "Select an option..."


def render_question_header(current_index: int, total_questions: int, question_text: str) -> None:
    """Render progress information and the active question text."""

    st.progress((current_index + 1) / total_questions)
    st.markdown(f"### Question {current_index + 1} of {total_questions}")
    st.write(question_text)


def render_answer_widget(question: SurveyQuestion, index: int) -> None:
    """Render the appropriate Streamlit widget for the survey question."""

    answer = question.answer
    widget_key = f"response_{index}"

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

    response = st.text_area(
        "Your answer",
        key=widget_key,
        value=state.get_response(index) or "",
        placeholder="Type your answer here...",
    )

    cleaned = response.strip()
    if cleaned:
        if state.get_response(index) != cleaned:
            state.set_response(index, cleaned)
    else:
        state.clear_response(index)
        followups.clear(index)

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
    st.button("Restart survey", on_click=state.reset)
