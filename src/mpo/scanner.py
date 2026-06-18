from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import (
    AUDIO_EXTENSIONS,
    AudioRecord,
    ScanResult,
    StudentInfo,
)


DATE_PATTERNS = [
    re.compile(r"(20\d{2})[-_./]?(\d{1,2})[-_./]?(\d{1,2})"),
    re.compile(r"(\d{1,2})[-_./]?(\d{1,2})[-_./]?(20\d{2})"),
    re.compile(r"(20\d{2})(\d{2})(\d{2})"),
]

STUDENT_NAME_PATTERNS = [
    re.compile(r"([\u4e00-\u9fa5][\u4e00-\u9fa5\s]{1,4}[\u4e00-\u9fa5])"),
    re.compile(r"([\u4e00-\u9fa5]{2,4})"),
    re.compile(r"([A-Za-z][A-Za-z\s]{1,20})"),
]

STUDENT_ID_PATTERN = re.compile(r"(S\d{3,}|\d{6,})", re.IGNORECASE)

PIECE_KEYWORDS = [
    "练习曲", "奏鸣曲", "协奏曲", "序曲", "圆舞曲", "夜曲",
    "进行曲", "交响曲", "前奏曲", "赋格", "变奏曲", "幻想曲",
    "小步舞曲", "谐谑曲", "叙事曲", "即兴曲", "随想曲",
    r"Op\.", r"op\.", r"No\.", r"no\.", r"K\. ", r"K\.", "BWV",
]


class AudioScanner:
    def __init__(
        self,
        ignore_patterns: Optional[list[str]] = None,
        class_names: Optional[list[str]] = None,
    ):
        self.ignore_patterns = [re.compile(p) for p in (ignore_patterns or [])]
        self.class_names = class_names or []
        self._piece_pattern = re.compile(
            "|".join(PIECE_KEYWORDS), re.IGNORECASE
        )

    def should_ignore(self, path: Path) -> bool:
        for pattern in self.ignore_patterns:
            if pattern.search(str(path)):
                return True
        return False

    def scan_directory(
        self,
        directory: Path,
        recursive: bool = True,
    ) -> ScanResult:
        result = ScanResult()
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"目录不存在: {directory}")

        iterator = directory.rglob("*") if recursive else directory.glob("*")

        for file_path in iterator:
            if not file_path.is_file():
                continue
            if self.should_ignore(file_path):
                result.skipped.append((file_path, "匹配忽略规则"))
                continue
            if file_path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue

            record = self._build_record(file_path)
            result.records.append(record)

        return result

    def _build_record(self, file_path: Path) -> AudioRecord:
        record = AudioRecord(file_path=file_path)
        record.duration_seconds = self._get_duration(file_path)
        record.file_hash = self._compute_hash(file_path)
        self._parse_filename(record)
        return record

    def _parse_filename(self, record: AudioRecord) -> None:
        stem = record.file_path.stem
        parts = re.split(r"[_\-\s\.]+", stem)
        parts = [p for p in parts if p]

        record.practice_date = self._extract_date(stem, record.file_path)
        record.student = self._extract_student(parts, record.file_path)
        record.piece = self._extract_piece(stem, parts)

    def _extract_date(
        self, filename: str, file_path: Path
    ) -> Optional[datetime]:
        for pattern in DATE_PATTERNS:
            match = pattern.search(filename)
            if match:
                groups = match.groups()
                try:
                    if len(groups[0]) == 4:
                        y, m, d = int(groups[0]), int(groups[1]), int(groups[2])
                    else:
                        m, d, y = int(groups[0]), int(groups[1]), int(groups[2])
                    return datetime(y, m, d)
                except (ValueError, IndexError):
                    continue

        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            return mtime
        except OSError:
            return None

    def _is_class_name(self, text: str) -> bool:
        for cn in self.class_names:
            if cn == text or cn in text:
                return True
        return False

    def _extract_student(
        self, parts: list[str], file_path: Path
    ) -> Optional[StudentInfo]:
        parent_parts = file_path.parent.parts

        klass = None
        for part in parent_parts:
            for cn in self.class_names:
                if cn in part:
                    klass = cn
                    break

        student_id = None
        all_text = " ".join(list(parent_parts) + [file_path.stem])
        id_match = STUDENT_ID_PATTERN.search(all_text)
        if id_match:
            student_id = id_match.group(1)

        for part in parts:
            if self._is_class_name(part):
                continue
            for pattern in STUDENT_NAME_PATTERNS:
                match = pattern.fullmatch(part)
                if match and not self._piece_pattern.search(part):
                    name = match.group(1).replace(" ", "")
                    return StudentInfo(name=name, klass=klass, student_id=student_id)

        for part in parent_parts:
            if self._is_class_name(part):
                continue
            for pattern in STUDENT_NAME_PATTERNS:
                match = pattern.fullmatch(part)
                if match and not self._piece_pattern.search(part):
                    name = match.group(1).replace(" ", "")
                    return StudentInfo(name=name, klass=klass, student_id=student_id)

        return None

    def _extract_piece(
        self, filename: str, parts: list[str]
    ) -> Optional[str]:
        for part in parts:
            if self._piece_pattern.search(part):
                return part

        for keyword in PIECE_KEYWORDS:
            if re.search(keyword, filename, re.IGNORECASE):
                idx = filename.lower().find(keyword.lower().replace("\\", ""))
                if idx >= 0:
                    end = min(idx + 30, len(filename))
                    return filename[idx:end].strip("_- .")

        non_date_parts = []
        for part in parts:
            if not any(p.search(part) for p in DATE_PATTERNS):
                if len(part) >= 2 and not part.isdigit():
                    non_date_parts.append(part)

        if len(non_date_parts) >= 2:
            return non_date_parts[-1]

        return None

    @staticmethod
    def _get_duration(file_path: Path) -> Optional[float]:
        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(str(file_path))
            if audio is not None and audio.info is not None:
                return getattr(audio.info, "length", None)
        except Exception:
            pass
        return None

    @staticmethod
    def _compute_hash(file_path: Path, chunk_size: int = 8192) -> str:
        hasher = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    hasher.update(chunk)
        except OSError:
            return ""
        return hasher.hexdigest()
