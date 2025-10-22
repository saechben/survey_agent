from __future__ import annotations

import streamlit as st

from app.models.survey import SurveyQuestion

from . import followups, state


def render(question: SurveyQuestion, total_questions: int) -> None:
    """Render navigation controls for moving through the survey."""

    current_index = state.get_current_index()
    prev_disabled = current_index == 0
    next_disabled = current_index >= max(total_questions - 1, 0)
    finish_disabled = current_index != max(total_questions - 1, 0)

    followup_entry = state.get_followups().get(current_index) or {}
    is_generating = state.is_generating_followup()

    if question.answer.type != "free_text":
        state.clear_followup_requirement(current_index)

    followup_required = (
        question.answer.type == "free_text"
        and state.is_followup_requirement_pending(current_index)
    )

    reminder_message: str | None = None
    reminder_level = "info"

    if is_generating:
        reminder_message = "Generating a follow-up question—please wait."
        next_disabled = True
        finish_disabled = True
    elif followup_required:
        if followup_entry.get("text"):
            if followup_entry.get("displayed"):
                reminder_message = "Please answer the follow-up question before moving on."
                reminder_level = "warning"
                finish_disabled = True
            else:
                reminder_message = "Preparing the follow-up question..."
                next_disabled = True
                finish_disabled = True
        else:
            reminder_message = "Generating a follow-up question—please wait."
            next_disabled = True
            finish_disabled = True

    if reminder_message:
        if reminder_level == "warning":
            st.warning(reminder_message)
        else:
            st.info(reminder_message)

    def _ensure_followup_completed() -> bool:
        if question.answer.type != "free_text":
            state.clear_followup_requirement(current_index)
            return True

        response = state.get_response(current_index)
        if not response:
            state.clear_followup_requirement(current_index)
            return True

        entry = state.get_followups().get(current_index) or {}
        followup_question = entry.get("text")
        followup_answer = state.get_followup_responses().get(current_index)

        if not followup_question:
            if not state.is_generating_followup():
                followups.maybe_generate(question, current_index, response)
            state.mark_followup_required(current_index)
            return False

        if not followup_answer or not followup_answer.strip():
            raw_widget_value = st.session_state.get(f"{followups.FOLLOW_UP_RESPONSE_PREFIX}{current_index}", "")
            cleaned_widget_value = str(raw_widget_value).strip()
            if cleaned_widget_value:
                state.set_followup_response(current_index, cleaned_widget_value)
                followup_answer = cleaned_widget_value

        if not followup_answer or not followup_answer.strip():
            state.mark_followup_required(current_index)
            return False

        state.clear_followup_requirement(current_index)
        return True

    def _go_previous() -> None:
        if state.get_current_index() > 0:
            state.decrement_index()
        state.mark_complete(False)

    def _go_next() -> None:
        if not _ensure_followup_completed():
            return
        if state.get_current_index() < total_questions - 1:
            state.increment_index(total_questions)
        state.mark_complete(False)

    def _finish() -> None:
        if not _ensure_followup_completed():
            return
        state.mark_complete(True)

    prev_col, next_col, finish_col = st.columns(3)
    with prev_col:
        st.button("Previous", on_click=_go_previous, disabled=prev_disabled)
    with next_col:
        st.button("Next", on_click=_go_next, disabled=next_disabled)
    with finish_col:
        st.button("Finish Survey", on_click=_finish, disabled=finish_disabled)
