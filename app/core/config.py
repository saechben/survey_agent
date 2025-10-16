from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:

    def __init__(self) -> None:
        self.llm_api_key = os.getenv("LLM_API_KEY")
        if not self.llm_api_key:
            raise RuntimeError("Missing LLM_API_KEY in environment or .env file.")

        self.llm_model = os.getenv("LLM_MODEL")
        if not self.llm_model:
            raise RuntimeError("Missing LLM_MODEL in environment or .env file.")


settings = Settings()
