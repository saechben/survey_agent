from __future__ import annotations

import streamlit as st

from . import state


def render(total_questions: int) -> None:
    """Render navigation controls for moving through the survey."""

    current_index = state.get_current_index()
    prev_disabled = current_index == 0
    next_disabled = current_index >= max(total_questions - 1, 0)
    finish_disabled = current_index != max(total_questions - 1, 0)

    followup_entry = state.get_followups().get(current_index)
    followup_pending = state.is_generating_followup() or (
        followup_entry
        and followup_entry.get("text")
        and not followup_entry.get("displayed")
    )

    if followup_pending:
        next_disabled = True
        finish_disabled = True

    def _go_previous() -> None:
        if state.get_current_index() > 0:
            state.decrement_index()
        state.mark_complete(False)

    def _go_next() -> None:
        if state.get_current_index() < total_questions - 1:
            state.increment_index(total_questions)
        state.mark_complete(False)

    def _finish() -> None:
        state.mark_complete(True)

    prev_col, next_col, finish_col = st.columns(3)
    with prev_col:
        st.button("Previous", on_click=_go_previous, disabled=prev_disabled)
    with next_col:
        st.button("Next", on_click=_go_next, disabled=next_disabled)
    with finish_col:
        st.button("Finish Survey", on_click=_finish, disabled=finish_disabled)
