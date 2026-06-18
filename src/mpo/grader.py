from __future__ import annotations

import csv
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
                    student_id_match = (
                        not cand.get("student_id")
                        or not r.student
                        or not r.student.student_id
                        or cand["student_id"] == r.student.student_id
                    )
                    date_match = (
                        not cand.get("practice_date")
                        or not r.date_str
                        or cand["practice_date"] == r.date_str
                    )
                    if klass_match and name_match and student_id_match and date_match:
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
                if r.student and data.get("student_id") and not r.student.student_id:
                    r.student = r.student._replace(student_id=data["student_id"])
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
                student_id=r.student.student_id if r.student else None,
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

    def export_history(
        self,
        output_dir: Path,
        student: Optional[str] = None,
        klass: Optional[str] = None,
        fmt: str = "csv",
    ) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        records = []
        for key, v in self._records.items():
            if student and v.get("student") != student:
                continue
            if klass and v.get("klass") != klass:
                continue
            records.append((key, v))

        if klass or student:
            records.sort(key=lambda kv: (
                kv[1].get("practice_date", ""),
                kv[1].get("graded_at", ""),
                kv[1].get("klass", ""),
                kv[1].get("student", ""),
                kv[1].get("student_id", ""),
            ))
        else:
            records.sort(key=lambda kv: (
                kv[1].get("klass", ""),
                kv[1].get("student", ""),
                kv[1].get("student_id", ""),
                kv[1].get("practice_date", ""),
                kv[1].get("graded_at", ""),
            ))

        if fmt == "json":
            filename = "grading_history"
            if klass:
                filename += f"_{klass}"
            if student:
                filename += f"_{student}"
            filename += ".json"
            path = output_dir / filename
            data = {
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "filter": {"student": student, "klass": klass},
                "count": len(records),
                "records": [
                    {
                        "key": key,
                        "student": v.get("student"),
                        "student_id": v.get("student_id"),
                        "klass": v.get("klass"),
                        "piece": v.get("piece"),
                        "practice_date": v.get("practice_date"),
                        "comment": v.get("comment"),
                        "rating": v.get("rating"),
                        "passed": v.get("passed"),
                        "graded_at": v.get("graded_at"),
                        "source_file": v.get("source_file"),
                        "file_hash": v.get("file_hash"),
                    }
                    for key, v in records
                ],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return path

        filename = "grading_history"
        if klass:
            filename += f"_{klass}"
        if student:
            filename += f"_{student}"
        filename += ".csv"
        path = output_dir / filename

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "班级", "学生", "学号", "练习日期", "曲目",
                "评语", "评级", "是否通过", "批改时间",
                "源文件", "文件哈希",
            ])
            for key, v in records:
                passed = ""
                if v.get("passed") is True:
                    passed = "通过"
                elif v.get("passed") is False:
                    passed = "未通过"
                writer.writerow([
                    v.get("klass", ""),
                    v.get("student", ""),
                    v.get("student_id", ""),
                    v.get("practice_date", ""),
                    v.get("piece", ""),
                    v.get("comment", ""),
                    v.get("rating", ""),
                    passed,
                    v.get("graded_at", ""),
                    v.get("source_file", ""),
                    v.get("file_hash", "")[:16] if v.get("file_hash") else "",
                ])
        return path

    def __len__(self) -> int:
        return self.count
