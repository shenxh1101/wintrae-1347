from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import AudioRecord


DEFAULT_GRADING_FILE = "grading_records.json"


class GradingStore:
    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = Path(store_path) if store_path else Path.cwd() / DEFAULT_GRADING_FILE
        self._records: dict[str, dict] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            with open(self.store_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "records" in data:
                self._records = data.get("records", {})
            elif isinstance(data, dict):
                self._records = data
        except (json.JSONDecodeError, OSError):
            self._records = {}

    def save(self) -> Path:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "records": self._records,
        }
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self._dirty = False
        return self.store_path

    def get(self, key: str) -> Optional[dict]:
        return self._records.get(key)

    def set(
        self,
        key: str,
        comment: Optional[str] = None,
        rating: Optional[str] = None,
        passed: Optional[bool] = None,
        **extra,
    ) -> dict:
        existing = self._records.get(key, {})
        updated = dict(existing)
        if comment is not None:
            updated["comment"] = comment
        if rating is not None:
            updated["rating"] = rating
        if passed is not None:
            updated["passed"] = bool(passed)
        for k, v in extra.items():
            if v is not None:
                updated[k] = v
        updated["graded_at"] = datetime.now().isoformat(timespec="seconds")
        self._records[key] = updated
        self._dirty = True
        return updated

    def apply_to_records(self, audio_records: list[AudioRecord]) -> int:
        count = 0
        hash_index: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        for key, v in self._records.items():
            fh = v.get("file_hash")
            if fh:
                hash_index[fh].append((key, v))

        for r in audio_records:
            data = self.get(r.review_key)
            if not data and r.file_hash and r.file_hash in hash_index:
                for key, cand in hash_index[r.file_hash]:
                    klass_match = (
                        not cand.get("klass")
                        or not r.student
                        or not r.student.klass
                        or cand["klass"] == r.student.klass
                    )
                    name_match = (
                        not cand.get("student")
                        or not r.student
                        or cand["student"] == r.student.name
                    )
                    if klass_match and name_match:
                        data = cand
                        break
            if data:
                if "comment" in data and data["comment"] and not r.comment:
                    r.comment = data["comment"]
                if "rating" in data and data["rating"] and not r.rating:
                    r.rating = data["rating"]
                if "passed" in data and data["passed"] is not None and r.passed is None:
                    r.passed = bool(data["passed"])
                if "graded_at" in data and data["graded_at"] and not r.graded_at:
                    try:
                        r.graded_at = datetime.fromisoformat(data["graded_at"])
                    except ValueError:
                        pass
                count += 1
        return count

    def collect_from_records(self, audio_records: list[AudioRecord]) -> int:
        count = 0
        for r in audio_records:
            if not (r.comment or r.rating is not None or r.passed is not None):
                continue
            self.set(
                r.review_key,
                comment=r.comment,
                rating=r.rating,
                passed=r.passed,
                file_hash=r.file_hash,
                student=r.student.name if r.student else None,
                klass=r.student.klass if r.student else None,
                piece=r.piece,
                practice_date=r.date_str,
                source_file=str(r.file_path),
            )
            count += 1
        return count

    @property
    def count(self) -> int:
        return len(self._records)

    def __len__(self) -> int:
        return self.count
