from __future__ import annotations

from textwrap import dedent

from pydantic import BaseModel, Field
from pydantic_ai import Agent, exceptions as ai_exceptions
from pydantic_ai.settings import ModelSettings

from app.core.config import settings


class FollowUpDecision(BaseModel):
    """Structured result returned by the follow-up agent."""

    should_ask: bool = Field(
        ...,
        description="Whether the respondent should be asked an additional follow-up question.",
    )
    follow_up_question: str | None = Field(
        default=None,
        description="The follow-up question text when one should be asked.",
    )
    rationale: str | None = Field(
        default=None,
        description="Short reasoning that explains the recommendation.",
    )


class FollowUpAgent:
    """Thin wrapper around a PydanticAI agent for deciding follow-up questions."""

    _agent: Agent[None, FollowUpDecision]

    def __init__(self) -> None:
        model_name = settings.llm_model
        provider_spec = f"openai:{model_name}"
        try:
            self._agent = Agent(
                provider_spec,
                output_type=FollowUpDecision,
                instructions=dedent(
                    """
                    You are a professional survey assistant tasked with judging whether a follow-up question is needed.
                    Consider the original survey question and the respondent's answer.

                    - Return `should_ask = true` when you need more detail to understand the answer.
                      Include a concise follow_up_question that invites elaboration.
                    - Return `should_ask = false` when the answer is already specific enough or a follow up question would not make sense.
                      Set follow_up_question to null in that case.

                    Avoid repeating the original question verbatim and keep follow-up questions single-sentence and neutral.
                    """
                ).strip(),
                model_settings=ModelSettings(temperature=0.2),
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to initialize follow-up agent: {exc}") from exc

    def decide(self, question: str, response: str) -> FollowUpDecision:
        """Run the agent and return its structured recommendation."""

        if not question or not response:
            raise ValueError("Both question and response must be provided.")

        prompt = dedent(
            f"""
            Survey question: {question}
            Respondent answer: {response}

            Provide your recommendation.
            """
        ).strip()

        try:
            run_result = self._agent.run_sync(prompt)
        except (ai_exceptions.AgentRunError, ai_exceptions.UserError) as exc:  # pragma: no cover - runtime path
            raise RuntimeError(f"Follow-up agent failed: {exc}") from exc
        except Exception as exc:  # pragma: no cover - runtime path
            raise RuntimeError(f"Follow-up agent encountered an unexpected error: {exc}") from exc

        return run_result.output
