from __future__ import annotations

from abc import ABC, abstractmethod
import os
from typing import Any

try:  # pragma: no cover - optional dependency
    from google import genai
except ImportError:  # pragma: no cover - optional dependency
    genai = None

from app.core.config import settings


class LLMInterface(ABC):
    """Defines the expected behaviour for language model wrappers."""

    @abstractmethod
    def __call__(self, prompt: str) -> str:
        """Execute the language model with the provided prompt."""
        raise NotImplementedError


class GeminiLLM(LLMInterface):
    """Stateless wrapper around Google's Gemini/Vertex SDK."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        temperature: float = 0.2,
        api_key: str | None = None,
        use_vertex: bool | None = None,
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        if genai is None:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "The google-genai package is required for GeminiLLM. "
                "Install it to enable Gemini/Vertex support."
            )

        self._model_name = model_name or settings.llm_model or "gemini-pro"
        self._temperature = temperature

        client_kwargs: dict[str, Any] = {}

        vertex_flag = use_vertex if use_vertex is not None else bool(
            os.getenv("GOOGLE_GENAI_USE_VERTEXAI")
        )
        if vertex_flag:
            resolved_project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
            resolved_location = location or os.getenv("GOOGLE_CLOUD_LOCATION")
            if not resolved_project or not resolved_location:
                raise ValueError(
                    "Vertex mode requires GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION."
                )
            client_kwargs.update(
                vertexai=True,
                project=resolved_project,
                location=resolved_location,
            )
        else:
            resolved_api_key = api_key or settings.llm_api_key
            if not resolved_api_key:
                raise ValueError("A Gemini API key must be configured.")
            client_kwargs["api_key"] = resolved_api_key

        self._client = genai.Client(**client_kwargs)

    def __call__(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")

        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config={"temperature": self._temperature},
        )
        return _extract_response_text(response)


class LLM(GeminiLLM):
    """Current default LLM implementation backed by Gemini."""


def _extract_response_text(response: Any) -> str:
    """Normalize Google GenAI responses to plain strings."""

    text = getattr(response, "text", None)
    if isinstance(text, str) and text:
        return text

    candidates = getattr(response, "candidates", None) or []
    collected: list[str] = []

    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = getattr(part, "text", None)
            if isinstance(part_text, str) and part_text:
                collected.append(part_text)

    if collected:
        return "".join(collected)

    return str(response)
