"""
KnowledgeStore — хранилище успешных паттернов решений.
Сохраняет и читает паттерны из results/knowledge.json.
Использует только стандартные библиотеки Python.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


KNOWLEDGE_FILE = Path(__file__).parent.parent / "results" / "knowledge.json"


class KnowledgeStore:
    def __init__(self, path: str = None):
        self._path = Path(path) if path else KNOWLEDGE_FILE
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list:
        if not self._path.exists():
            return []
        with open(self._path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data if isinstance(data, list) else []
            except json.JSONDecodeError:
                return []

    def _save(self, records: list) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    def save_pattern(self, pattern_type: str, data: dict) -> dict:
        """Сохраняет успешный паттерн решения."""
        records = self._load()
        entry = {
            "id": len(records) + 1,
            "pattern_type": pattern_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        records.append(entry)
        self._save(records)
        return entry

    def get_patterns(self, pattern_type: str) -> list:
        """Возвращает все паттерны заданного типа."""
        records = self._load()
        return [r for r in records if r.get("pattern_type") == pattern_type]

    def get_recent(self, limit: int = 5) -> list:
        """Возвращает последние N паттернов (по времени сохранения)."""
        records = self._load()
        return records[-limit:] if len(records) > limit else records
