from __future__ import annotations

from typing import List

import streamlit as st

from app.API.survey_data_provider import SurveyDataProvider
from app.models.analysis import SurveyAnalysisSnapshot
from app.models.survey import SurveyQuestion
from app.services.analysis_agent import SurveyAnalysisAgent
from app.services.LLM import LLM

from . import state

_AGENT_HISTORY_KEY = "analysis_agent_history"
_AGENT_PROMPT_KEY = "analysis_agent_prompt"
_AGENT_FORM_KEY = "analysis_agent_form"
_MAX_AGENT_HISTORY = 5


@st.cache_resource
def _get_analysis_llm() -> LLM:
    """Return a shared LLM instance for the analysis agent."""

    return LLM()


def render_analysis(questions: List[SurveyQuestion]) -> None:
    """Render analysis details and the interactive agent for survey insights."""

    responses = state.get_responses()
    total_questions = len(questions)
    answered = len(responses)

    provider = SurveyDataProvider(questions)
    snapshot = provider.get_survey_snapshot()

    if total_questions == 0:
        st.info("No survey questions available.")
        agent = SurveyAnalysisAgent(provider, llm=_get_analysis_llm())
        _render_agent_interface(agent, snapshot, enabled=False)
        return

    if answered == 0:
        st.info("Complete the survey to see insights once responses are recorded.")
        agent = SurveyAnalysisAgent(provider, llm=_get_analysis_llm())
        _render_agent_interface(agent, snapshot, enabled=False)
        return

    agent = SurveyAnalysisAgent(provider, llm=_get_analysis_llm())
    _render_agent_interface(agent, snapshot, enabled=True)


def _render_agent_interface(
    agent: SurveyAnalysisAgent,
    snapshot: SurveyAnalysisSnapshot,
    *,
    enabled: bool,
) -> None:
    """Render the interactive interface for the analysis agent."""

    st.header("Ask the Analysis Agent")

    if not enabled:
        st.info("Complete the survey first to chat with the analysis agent.")
        return

    history: List[dict[str, str]] = st.session_state.setdefault(_AGENT_HISTORY_KEY, [])

    with st.form(_AGENT_FORM_KEY, clear_on_submit=True):
        prompt = st.text_area(
            "Enter a question about this survey",
            key=_AGENT_PROMPT_KEY,
            placeholder="Example: What themes did respondents mention the most?",
            height=120,
        )
        submitted = st.form_submit_button("Ask agent")

    if submitted:
        cleaned_prompt = (prompt or "").strip()
        if not cleaned_prompt:
            st.warning("Please provide a question for the analysis agent.")
        else:
            status_container = st.container()
            progress_placeholder = status_container.empty()
            message_placeholder = status_container.empty()

            status_steps = [
                ("fetching", "Fetching survey data..."),
                ("reading", "Reading survey responses..."),
                ("thinking", "Thinking through insights..."),
            ]
            step_order = [step for step, _ in status_steps]
            completed_steps: set[str] = set()
            current_step: str | None = None

            def render_status(current: str | None) -> None:
                lines = []
                for step, label in status_steps:
                    if step in completed_steps:
                        prefix = "[x]"
                    elif step == current:
                        prefix = "[>]"
                    else:
                        prefix = "[ ]"
                    lines.append(f"- {prefix} {label}")
                progress_placeholder.markdown("\n".join(lines))

            def handle_status(step: str, message: str) -> None:
                nonlocal current_step
                if step == "completed":
                    completed_steps.update(step_order)
                    current_step = None
                    render_status(current_step)
                    if "complete" in message.lower():
                        message_placeholder.success(message)
                    else:
                        message_placeholder.info(message)
                    return

                if step not in step_order:
                    message_placeholder.info(message)
                    return

                step_index = step_order.index(step)
                completed_steps.update(step_order[:step_index])
                current_step = step
                render_status(current_step)
                message_placeholder.info(message)

            render_status(current_step)
            answer = agent.answer(
                cleaned_prompt,
                survey_id=snapshot.survey_id,
                status_callback=handle_status,
            )
            history.append({"question": cleaned_prompt, "answer": answer})
            if len(history) > _MAX_AGENT_HISTORY:
                del history[: len(history) - _MAX_AGENT_HISTORY]
            st.session_state[_AGENT_HISTORY_KEY] = history

    if history:
        st.subheader("Recent agent answers")
        for index, entry in enumerate(reversed(history), start=1):
            st.markdown(f"**Question:** {entry['question']}")
            st.write(entry["answer"])
            if index < len(history):
                st.markdown("---")
