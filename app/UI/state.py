from __future__ import annotations

from typing import Any, Dict, Optional

import streamlit as st

CURRENT_INDEX_KEY = "current_index"
RESPONSES_KEY = "responses"
SURVEY_COMPLETE_KEY = "survey_complete"
SURVEY_STARTED_KEY = "survey_started"
FOLLOWUPS_KEY = "followups"
FOLLOWUP_RESPONSES_KEY = "followup_responses"
GENERATING_FOLLOWUP_KEY = "generating_followup"
FOLLOWUP_REQUIRED_KEY = "followup_required"
ANALYSIS_VISIBLE_KEY = "analysis_visible"


def reset() -> None:
    """Reset all survey-related session state values."""

    st.session_state[CURRENT_INDEX_KEY] = 0
    st.session_state[RESPONSES_KEY] = {}
    st.session_state[SURVEY_COMPLETE_KEY] = False
    st.session_state[SURVEY_STARTED_KEY] = False
    st.session_state[FOLLOWUPS_KEY] = {}
    st.session_state[FOLLOWUP_RESPONSES_KEY] = {}
    st.session_state[GENERATING_FOLLOWUP_KEY] = False
    st.session_state[FOLLOWUP_REQUIRED_KEY] = {}
    st.session_state[ANALYSIS_VISIBLE_KEY] = False

    for key in [name for name in st.session_state.keys() if name.startswith("response_")]:
        del st.session_state[key]

    for key in [name for name in st.session_state.keys() if name.startswith("analysis_agent_")]:
        del st.session_state[key]


def ensure_defaults(total_questions: int) -> None:
    """Ensure the expected session state keys exist with sensible defaults."""

    st.session_state.setdefault(CURRENT_INDEX_KEY, 0)
    st.session_state.setdefault(RESPONSES_KEY, {})
    st.session_state.setdefault(SURVEY_COMPLETE_KEY, False)
    st.session_state.setdefault(SURVEY_STARTED_KEY, False)
    st.session_state.setdefault(FOLLOWUPS_KEY, {})
    st.session_state.setdefault(FOLLOWUP_RESPONSES_KEY, {})
    st.session_state.setdefault(GENERATING_FOLLOWUP_KEY, False)
    st.session_state.setdefault(FOLLOWUP_REQUIRED_KEY, {})
    st.session_state.setdefault(ANALYSIS_VISIBLE_KEY, False)

    if total_questions == 0:
        st.session_state[CURRENT_INDEX_KEY] = 0
        return

    if st.session_state[CURRENT_INDEX_KEY] >= total_questions:
        st.session_state[CURRENT_INDEX_KEY] = total_questions - 1


def get_current_index() -> int:
    """Return the active question index."""

    return int(st.session_state[CURRENT_INDEX_KEY])


def set_current_index(value: int) -> None:
    """Persist the active question index."""

    st.session_state[CURRENT_INDEX_KEY] = max(0, value)


def increment_index(total_questions: int) -> None:
    """Move to the next question if available."""

    next_index = min(get_current_index() + 1, max(total_questions - 1, 0))
    set_current_index(next_index)


def decrement_index() -> None:
    """Move to the previous question if available."""

    set_current_index(max(get_current_index() - 1, 0))


def mark_complete(is_complete: bool = True) -> None:
    """Mark whether the survey was completed."""

    st.session_state[SURVEY_COMPLETE_KEY] = is_complete
    if not is_complete:
        st.session_state[ANALYSIS_VISIBLE_KEY] = False


def is_complete() -> bool:
    """Return True when the survey has been marked complete."""

    return bool(st.session_state[SURVEY_COMPLETE_KEY])


def mark_started(is_started: bool = True) -> None:
    """Persist whether the survey has left the start screen."""

    st.session_state[SURVEY_STARTED_KEY] = bool(is_started)


def is_started() -> bool:
    """Return True when the start screen has been dismissed."""

    return bool(st.session_state[SURVEY_STARTED_KEY])


def get_responses() -> Dict[int, str]:
    """Return all stored responses keyed by question index."""

    return st.session_state[RESPONSES_KEY]


def get_response(index: int) -> Optional[str]:
    """Fetch a single response for the given question index."""

    return get_responses().get(index)


def set_response(index: int, value: str) -> None:
    """Persist a response for the given question index."""

    st.session_state[RESPONSES_KEY][index] = value


def clear_response(index: int, *, forget_widget: bool = True) -> None:
    """Remove any recorded response for the given question index.

    Parameters
    ----------
    index:
        Question index whose stored response should be cleared.
    forget_widget:
        When True, also remove the widget's value from ``st.session_state`` so the input
        resets visually. Keep this False for widgets (e.g. radio buttons) where we want
        the placeholder value to persist across reruns.
    """

    st.session_state[RESPONSES_KEY].pop(index, None)
    if forget_widget:
        st.session_state.pop(f"response_{index}", None)


def responses_count() -> int:
    """Return how many questions have recorded responses."""

    return len(get_responses())


def get_followups() -> Dict[int, Dict[str, Any]]:
    """Return the map of generated follow-up questions."""

    return st.session_state[FOLLOWUPS_KEY]


def set_followup(index: int, value: Dict[str, Any]) -> None:
    """Store follow-up question metadata."""

    st.session_state[FOLLOWUPS_KEY][index] = value


def clear_followup(index: int) -> None:
    """Remove cached follow-up question details for a given index."""

    st.session_state[FOLLOWUPS_KEY].pop(index, None)
    clear_followup_requirement(index)


def get_followup_responses() -> Dict[int, str]:
    """Return the map of follow-up answers keyed by question index."""

    return st.session_state[FOLLOWUP_RESPONSES_KEY]


def set_followup_response(index: int, value: str) -> None:
    """Persist the user's follow-up response."""

    st.session_state[FOLLOWUP_RESPONSES_KEY][index] = value


def clear_followup_response(index: int) -> None:
    """Clear any recorded follow-up response."""

    st.session_state[FOLLOWUP_RESPONSES_KEY].pop(index, None)


def set_generating_followup(is_generating: bool) -> None:
    """Track whether the app is currently generating a follow-up question."""

    st.session_state[GENERATING_FOLLOWUP_KEY] = is_generating


def is_generating_followup() -> bool:
    """Return True when a follow-up question is being generated."""

    return bool(st.session_state[GENERATING_FOLLOWUP_KEY])


def mark_followup_required(index: int) -> None:
    """Flag that a question requires a follow-up answer before navigating on."""

    st.session_state[FOLLOWUP_REQUIRED_KEY][index] = True


def clear_followup_requirement(index: int) -> None:
    """Remove any follow-up requirement for the given question."""

    st.session_state[FOLLOWUP_REQUIRED_KEY].pop(index, None)


def is_followup_requirement_pending(index: int) -> bool:
    """Return True when a follow-up answer is still required for a question."""

    return bool(st.session_state[FOLLOWUP_REQUIRED_KEY].get(index))


def set_analysis_visible(is_visible: bool) -> None:
    """Persist whether the analysis section should be displayed."""

    st.session_state[ANALYSIS_VISIBLE_KEY] = bool(is_visible)


def is_analysis_visible() -> bool:
    """Return True when the analysis section should be shown."""

    return bool(st.session_state[ANALYSIS_VISIBLE_KEY])
