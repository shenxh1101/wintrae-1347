from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg",
    ".wma", ".opus", ".aiff", ".aif",
}


@dataclass
class StudentInfo:
    name: str
    klass: Optional[str] = None
    student_id: Optional[str] = None

    def __hash__(self):
        return hash((self.name, self.klass, self.student_id))


@dataclass
class AudioRecord:
    file_path: Path
    student: Optional[StudentInfo] = None
    piece: Optional[str] = None
    practice_date: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    comment: Optional[str] = None
    rating: Optional[str] = None
    passed: Optional[bool] = None
    graded_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    file_hash: Optional[str] = None
    original_name: str = ""

    @property
    def review_key(self) -> str:
        parts = []
        if self.student and self.student.klass:
            parts.append(self.student.klass)
        if self.student:
            parts.append(self.student.name)
        else:
            parts.append("未知学生")
        parts.append(self.date_str)
        parts.append(self.piece or "未知曲目")
        if self.file_hash:
            parts.append(self.file_hash[:8])
        return "|".join(parts)

    def __post_init__(self):
        if not self.original_name:
            self.original_name = self.file_path.name

    @property
    def extension(self) -> str:
        return self.file_path.suffix.lower()

    @property
    def is_audio(self) -> bool:
        return self.extension in AUDIO_EXTENSIONS

    @property
    def duration_str(self) -> str:
        if self.duration_seconds is None:
            return "--:--"
        mins, secs = divmod(int(self.duration_seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    @property
    def date_str(self) -> str:
        if self.practice_date is None:
            return "未知日期"
        return self.practice_date.strftime("%Y-%m-%d")


@dataclass
class ScanResult:
    records: list[AudioRecord] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.records)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)


@dataclass
class CheckIssue:
    level: str
    category: str
    message: str
    record: Optional[AudioRecord] = None
    extra: dict = field(default_factory=dict)


@dataclass
class CheckReport:
    issues: list[CheckIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[CheckIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[CheckIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def info(self) -> list[CheckIssue]:
        return [i for i in self.issues if i.level == "info"]


@dataclass
class OperationLog:
    operation: str
    source: Path
    target: Optional[Path] = None
    status: str = "success"
    message: str = ""
    student: Optional[str] = None
    klass: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    extra: dict = field(default_factory=dict)


class OperationLogBuilder:
    def __init__(self):
        self.logs: list[OperationLog] = []

    def add(self, log: OperationLog) -> None:
        self.logs.append(log)

    def record(
        self,
        operation: str,
        source: Path,
        target: Optional[Path] = None,
        status: str = "success",
        message: str = "",
        record: Optional[AudioRecord] = None,
        extra: Optional[dict] = None,
    ) -> OperationLog:
        student = None
        klass = None
        if record and record.student:
            student = record.student.name
            klass = record.student.klass
        log = OperationLog(
            operation=operation,
            source=Path(source),
            target=Path(target) if target else None,
            status=status,
            message=message,
            student=student,
            klass=klass,
            extra=extra or {},
        )
        self.logs.append(log)
        return log

    def write_csv(self, output_dir: Path, filename: Optional[str] = None) -> Path:
        import csv

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            filename = f"operation_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = output_dir / filename

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "时间", "操作", "班级", "学生",
                "源文件", "目标文件", "状态", "备注",
            ])
            for log in self.logs:
                writer.writerow([
                    log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    log.operation,
                    log.klass or "",
                    log.student or "",
                    str(log.source),
                    str(log.target) if log.target else "",
                    log.status,
                    log.message,
                ])
        return path

    def __len__(self) -> int:
        return len(self.logs)

    def __bool__(self) -> bool:
        return True
