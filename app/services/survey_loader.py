from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

from app.models.survey import (
    CategoricalAnswer,
    FreeTextAnswer,
    Survey,
    SurveyQuestion,
)


class SurveyLoader:
    """Load survey questions from a simple text file.

    Each non-empty line of the file represents a question. A line may optionally
    specify categorical choices using the pipe character ("|") to separate the
    question text from a comma-separated list of options:

        What is your favourite colour? | Red, Blue, Green

    Lines without a choice segment are treated as free-text questions. Lines
    beginning with "#" or that are blank are ignored.
    """

    def __init__(self, source: str | Path) -> None:
        self._path = Path(source)
        if not self._path.is_file():
            raise FileNotFoundError(f"Survey file not found: {self._path}")

        questions = list(self._load_questions())
        self._survey = Survey(questions=questions)
        self._cursor = 0

    @property
    def survey(self) -> Survey:
        """Return the full survey loaded from the file."""

        return self._survey

    def next_question(self) -> SurveyQuestion | None:
        """Return the next question or ``None`` once exhausted."""

        if self._cursor >= len(self._survey.questions):
            return None

        question = self._survey.questions[self._cursor]
        self._cursor += 1
        return question

    def reset(self) -> None:
        """Reset the internal cursor so iteration can begin again."""

        self._cursor = 0

    def _load_questions(self) -> Iterable[SurveyQuestion]:
        with self._path.open("r", encoding="utf-8") as handle:
            for lineno, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                question_text, choices = self._parse_line(line, lineno)
                answer = (
                    CategoricalAnswer(choices=choices)
                    if choices
                    else FreeTextAnswer()
                )
                yield SurveyQuestion(question=question_text, answer=answer)

    def _parse_line(self, line: str, lineno: int) -> tuple[str, List[str]]:
        if "|" not in line:
            question_text = line
            if not question_text:
                raise ValueError(f"Line {lineno}: question text cannot be empty")
            return question_text, []

        question_part, choices_part = line.split("|", maxsplit=1)
        question_text = question_part.strip()
        if not question_text:
            raise ValueError(f"Line {lineno}: question text cannot be empty")

        choices = [choice.strip() for choice in choices_part.split(",") if choice.strip()]
        if not choices:
            raise ValueError(f"Line {lineno}: categorical question must define at least one choice")

        return question_text, choices
