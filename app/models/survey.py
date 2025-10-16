from __future__ import annotations

from typing import Annotated, Iterable, List, Union, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class CategoricalAnswer(BaseModel):
    """Represents a multiple-choice style response."""

    type: Literal["categorical"] = Field(default="categorical", frozen=True)
    choices: List[str]
    response: str | None = None

    @field_validator("choices", mode="before")
    @classmethod
    def _stringify_choices(cls, value: Iterable[Union[str, int]] | None) -> List[str]:
        if value is None:
            raise TypeError("choices must be provided")
        if isinstance(value, str):
            raise TypeError("choices must be provided as a sequence, not a single string")
        return [str(choice) for choice in value]

    @field_validator("response", mode="before")
    @classmethod
    def _stringify_response(cls, value: Union[str, int, None]) -> str | None:
        if value is None:
            return None
        return str(value)

    @model_validator(mode="after")
    def _ensure_valid_response(self) -> "CategoricalAnswer":
        if self.response is None:
            return self

        if self.response not in self.choices:
            raise ValueError("response must be one of the provided choices")

        return self

    model_config = {"extra": "forbid"}


class FreeTextAnswer(BaseModel):
    """Represents a free-form textual response."""

    type: Literal["free_text"] = Field(default="free_text", frozen=True)
    response: str | None = None

    model_config = {"extra": "forbid"}


Answer = Annotated[
    Union[CategoricalAnswer, FreeTextAnswer],
    Field(discriminator="type"),
]


class SurveyQuestion(BaseModel):
    """A single survey item with its associated answer definition."""

    question: str
    answer: Answer

    model_config = {"extra": "forbid"}


class Survey(BaseModel):
    """Container for a set of survey questions."""

    questions: List[SurveyQuestion]

    model_config = {"extra": "forbid"}
