from __future__ import annotations

from typing import List

import streamlit as st

from app.API.survey_data_provider import SurveyDataProvider
from app.models.analysis import SurveyAnalysisSnapshot
from app.models.survey import SurveyQuestion
from app.services.analysis_agent import SurveyAnalysisAgent
from app.services.LLM import LLM

from . import followups, state

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
    followup_responses = state.get_followup_responses()
    total_questions = len(questions)
    answered = len(responses)

    provider = SurveyDataProvider(questions)
    snapshot = provider.get_survey_snapshot()

    if total_questions == 0:
        st.info("No survey questions available.")
        agent = SurveyAnalysisAgent(provider, llm=_get_analysis_llm())
        _render_agent_interface(agent, snapshot, enabled=False)
        return

    st.header("Survey Overview")
    st.metric("Answered questions", f"{answered}/{total_questions}")

    if answered == 0:
        st.info("Complete the survey to see insights once responses are recorded.")
        agent = SurveyAnalysisAgent(provider, llm=_get_analysis_llm())
        _render_agent_interface(agent, snapshot, enabled=False)
        return

    _render_question_breakdowns(questions, responses, followup_responses)

    st.divider()

    agent = SurveyAnalysisAgent(provider, llm=_get_analysis_llm())
    _render_agent_interface(agent, snapshot, enabled=True)


def _render_question_breakdowns(
    questions: List[SurveyQuestion],
    responses: dict[int, str],
    followup_responses: dict[int, str],
) -> None:
    """Render per-question charts and summaries."""

    st.header("Per Question Details")

    for index, question in enumerate(questions):
        st.subheader(question.question)
        response = responses.get(index)

        if question.answer.type == "categorical" and response:
            st.markdown(f"**Selected answer:** {response}")
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


def _render_textual_summary(text: str, label: str = "Response summary") -> None:
    """Render a quick summary for free-text responses."""

    word_count = len(text.split())
    char_count = len(text)
    st.markdown(f"**{label}:**")
    st.write(text)
    st.caption(f"Characters: {char_count} • Words: {word_count}")


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
