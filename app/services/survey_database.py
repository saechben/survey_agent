from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

from app.core.config import settings


@dataclass(slots=True)
class SurveyResultRecord:
    survey_id: str
    responses: Dict[int, str]
    followups: Dict[int, Dict[str, Any]]
    followup_responses: Dict[int, str]


class SurveyDatabaseInterface(Protocol):
    """Minimal interface for persisting completed survey results."""

    def save_survey_results(self, record: SurveyResultRecord) -> None: ...

    def load_survey_results(self, survey_id: str) -> Optional[SurveyResultRecord]: ...


class MockSurveyDatabase(SurveyDatabaseInterface):
    """Simple file-backed implementation used until a real database is available."""

    def __init__(self, storage_path: Path) -> None:
        self._path = Path(storage_path)
        self._lock = threading.Lock()

    def save_survey_results(self, record: SurveyResultRecord) -> None:
        with self._lock:
            payload = self._read_all_unlocked()
            payload[record.survey_id] = self._serialize_record(record)
            self._write_all_unlocked(payload)

    def load_survey_results(self, survey_id: str) -> Optional[SurveyResultRecord]:
        with self._lock:
            payload = self._read_all_unlocked()
            raw_record = payload.get(survey_id)
        if raw_record is None:
            return None
        return self._deserialize_record(survey_id, raw_record)

    def _read_all_unlocked(self) -> Dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_all_unlocked(self, payload: Dict[str, Any]) -> None:
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _serialize_record(record: SurveyResultRecord) -> Dict[str, Any]:
        return {
            "responses": {str(key): value for key, value in record.responses.items()},
            "followups": {str(key): value for key, value in record.followups.items()},
            "followup_responses": {
                str(key): value for key, value in record.followup_responses.items()
            },
        }

    @staticmethod
    def _deserialize_record(survey_id: str, payload: Dict[str, Any]) -> SurveyResultRecord:
        def _convert_keys(source: Dict[str, Any]) -> Dict[int, Any]:
            converted: Dict[int, Any] = {}
            for key, value in source.items():
                try:
                    converted[int(key)] = value
                except (TypeError, ValueError):
                    continue
            return converted

        return SurveyResultRecord(
            survey_id=survey_id,
            responses={k: str(v) for k, v in _convert_keys(payload.get("responses", {})).items()},
            followups=_convert_keys(payload.get("followups", {})),
            followup_responses={
                k: str(v) for k, v in _convert_keys(payload.get("followup_responses", {})).items()
            },
        )


_DATABASE_INSTANCE: Optional[SurveyDatabaseInterface] = None
_DATABASE_LOCK = threading.Lock()


def get_survey_database() -> SurveyDatabaseInterface:
    """Return the shared survey database instance."""

    global _DATABASE_INSTANCE
    if _DATABASE_INSTANCE is None:
        with _DATABASE_LOCK:
            if _DATABASE_INSTANCE is None:
                _DATABASE_INSTANCE = MockSurveyDatabase(settings.survey_results_path)
    return _DATABASE_INSTANCE


__all__ = [
    "SurveyDatabaseInterface",
    "SurveyResultRecord",
    "MockSurveyDatabase",
    "get_survey_database",
]
