from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:

    def __init__(self) -> None:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key:
            api_key = api_key.strip()
        if not api_key:
            raise RuntimeError("Missing LLM/OpenAI API key in environment or .env file.")
        self.llm_api_key = api_key

        model_name = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL")
        if model_name:
            model_name = model_name.strip()
        if not model_name:
            raise RuntimeError("Missing LLM/OpenAI model name in environment or .env file.")
        self.llm_model = model_name

        survey_path = os.getenv("SURVEY_FILE_PATH", "app/data/real_survey.txt")
        self.survey_file_path = Path(survey_path).expanduser().resolve()
        if not self.survey_file_path.is_file():
            raise RuntimeError(f"Survey file not found at {self.survey_file_path}")

        results_path = os.getenv("SURVEY_RESULTS_PATH", "app/data/survey_results.txt")
        self.survey_results_path = Path(results_path).expanduser().resolve()
        self.survey_results_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
