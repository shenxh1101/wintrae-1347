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
    tags: list[str] = field(default_factory=list)
    file_hash: Optional[str] = None
    original_name: str = ""

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
