from __future__ import annotations

import os
import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if "dotenv" not in sys.modules:
    mock_dotenv = types.ModuleType("dotenv")

    def _noop_load_dotenv(*args, **kwargs) -> bool:
        return False

    mock_dotenv.load_dotenv = _noop_load_dotenv
    sys.modules["dotenv"] = mock_dotenv

os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "gpt-4o-mini")
