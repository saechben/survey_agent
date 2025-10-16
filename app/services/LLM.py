from __future__ import annotations

from abc import ABC, abstractmethod

from langchain.llms import OpenAI

from app.core.config import settings


class LLMInterface(ABC):
    """Defines the expected behaviour for language model wrappers."""

    @abstractmethod
    def __call__(self, prompt: str) -> str:
        """Execute the language model with the provided prompt."""
        raise NotImplementedError


class LLM(LLMInterface):
    """Stateless LangChain wrapper around the configured OpenAI model."""

    def __init__(self) -> None:
        self._client = OpenAI(
            model_name=settings.llm_model,
            openai_api_key=settings.llm_api_key,
        )

    def __call__(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")

        return self._client.predict(prompt)
