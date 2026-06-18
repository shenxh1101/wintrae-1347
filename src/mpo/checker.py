from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .models import AudioRecord, CheckIssue, CheckReport, StudentInfo


class Checker:
    def __init__(
        self,
        min_duration_seconds: float = 10.0,
        expected_students: Optional[list[StudentInfo]] = None,
        expected_pieces: Optional[list[str]] = None,
        date_range: Optional[tuple[datetime, datetime]] = None,
    ):
        self.min_duration = min_duration_seconds
        self.expected_students = expected_students or []
        self.expected_pieces = expected_pieces or []
        self.date_range = date_range

    def run(self, records: list[AudioRecord]) -> CheckReport:
        report = CheckReport()

        self._check_unknown_students(records, report)
        self._check_unknown_pieces(records, report)
        self._check_short_duration(records, report)
        self._check_duplicates(records, report)
        self._check_missing_students(records, report)
        self._check_out_of_range(records, report)

        return report

    def _check_unknown_students(
        self, records: list[AudioRecord], report: CheckReport
    ) -> None:
        for r in records:
            if r.student is None:
                report.issues.append(
                    CheckIssue(
                        level="warning",
                        category="student",
                        message=f"无法识别学生: {r.file_path.name}",
                        record=r,
                    )
                )

    def _check_unknown_pieces(
        self, records: list[AudioRecord], report: CheckReport
    ) -> None:
        for r in records:
            if r.piece is None:
                report.issues.append(
                    CheckIssue(
                        level="info",
                        category="piece",
                        message=f"无法识别曲目: {r.file_path.name}",
                        record=r,
                    )
                )

    def _check_short_duration(
        self, records: list[AudioRecord], report: CheckReport
    ) -> None:
        for r in records:
            if (
                r.duration_seconds is not None
                and r.duration_seconds < self.min_duration
            ):
                report.issues.append(
                    CheckIssue(
                        level="warning",
                        category="duration",
                        message=(
                            f"时长短于 {self.min_duration:.0f} 秒: "
                            f"{r.duration_str} - {r.file_path.name}"
                        ),
                        record=r,
                        extra={"duration": r.duration_seconds},
                    )
                )

    def _check_duplicates(
        self, records: list[AudioRecord], report: CheckReport
    ) -> None:
        hash_groups: dict[str, list[AudioRecord]] = defaultdict(list)
        for r in records:
            if r.file_hash:
                hash_groups[r.file_hash].append(r)

        for h, group in hash_groups.items():
            if len(group) > 1:
                report.issues.append(
                    CheckIssue(
                        level="error",
                        category="duplicate",
                        message=(
                            f"发现 {len(group)} 个重复文件: "
                            + ", ".join(r.file_path.name for r in group)
                        ),
                        extra={"files": [str(r.file_path) for r in group]},
                    )
                )

        name_groups: dict[tuple, list[AudioRecord]] = defaultdict(list)
        for r in records:
            if r.student and r.piece and r.practice_date:
                key = (r.student.name, r.piece, r.date_str)
                name_groups[key].append(r)

        for key, group in name_groups.items():
            if len(group) > 1:
                report.issues.append(
                    CheckIssue(
                        level="warning",
                        category="duplicate",
                        message=(
                            f"同一名学生同日期同曲目提交 {len(group)} 次: "
                            f"{key[0]} - {key[2]} - {key[1]}"
                        ),
                        extra={"files": [str(r.file_path) for r in group]},
                    )
                )

    def _check_missing_students(
        self, records: list[AudioRecord], report: CheckReport
    ) -> None:
        if not self.expected_students:
            return

        submitted = {r.student for r in records if r.student}
        for expected in self.expected_students:
            matched = any(
                s.name == expected.name
                and (not expected.klass or s.klass == expected.klass)
                for s in submitted
            )
            if not matched:
                msg = f"学生缺交: {expected.name}"
                if expected.klass:
                    msg += f" ({expected.klass})"
                report.issues.append(
                    CheckIssue(
                        level="error",
                        category="missing",
                        message=msg,
                        extra={"student": expected},
                    )
                )

    def _check_out_of_range(
        self, records: list[AudioRecord], report: CheckReport
    ) -> None:
        if not self.date_range:
            return

        start, end = self.date_range
        for r in records:
            if r.practice_date:
                if r.practice_date < start or r.practice_date > end:
                    report.issues.append(
                        CheckIssue(
                            level="info",
                            category="date",
                            message=(
                                f"日期超出范围 {start.strftime('%Y-%m-%d')} ~ "
                                f"{end.strftime('%Y-%m-%d')}: {r.date_str} "
                                f"- {r.file_path.name}"
                            ),
                            record=r,
                        )
                    )

    @staticmethod
    def load_students_from_file(path: Path) -> list[StudentInfo]:
        path = Path(path)
        students = []
        if path.suffix in {".txt", ".csv"}:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip().strip(",")
                    if not line:
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 2:
                        klass, name = parts[0], parts[1]
                        sid = parts[2] if len(parts) >= 3 else None
                        students.append(StudentInfo(name=name, klass=klass, student_id=sid))
                    else:
                        students.append(StudentInfo(name=parts[0]))
        return students
