from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_openai import ChatOpenAI

from app.core.config import settings


class LLMInterface(ABC):
    """Defines the expected behaviour for language model wrappers."""

    @abstractmethod
    def __call__(self, prompt: str) -> str:
        """Execute the language model with the provided prompt."""
        raise NotImplementedError


class LLM(LLMInterface):
    """Stateless LangChain wrapper around the configured OpenAI chat model."""

    def __init__(self) -> None:
        self._client = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            temperature=0.2,
        )

    def __call__(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")

        result = self._client.invoke(prompt)
        if isinstance(result, str):
            return result

        content = getattr(result, "content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            return "".join(parts)

        return str(result)
