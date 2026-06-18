from __future__ import annotations

import shutil
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .models import AudioRecord, StudentInfo


class Splitter:
    def __init__(
        self,
        output_dir: Optional[Path] = None,
        copy: bool = True,
        date_range: Optional[tuple[datetime, datetime]] = None,
    ):
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "output"
        self.copy = copy
        self.date_range = date_range

    def filter_by_date(
        self, records: list[AudioRecord]
    ) -> list[AudioRecord]:
        if not self.date_range:
            return records
        start, end = self.date_range
        return [
            r for r in records
            if r.practice_date and start <= r.practice_date <= end
        ]

    def split_by_student(
        self,
        records: list[AudioRecord],
        on_progress: Optional[Callable[[int, int, StudentInfo], None]] = None,
    ) -> dict[StudentInfo, list[Path]]:
        records = self.filter_by_date(records)
        groups: dict[StudentInfo, list[AudioRecord]] = defaultdict(list)

        for r in records:
            if r.student:
                groups[r.student].append(r)

        result = {}
        total = len(groups)
        for idx, (student, recs) in enumerate(groups.items(), 1):
            student_dir = self._student_dir(student)
            paths = []
            for r in recs:
                target = student_dir / r.file_path.name
                paths.append(self._transfer(r.file_path, target))
            result[student] = paths
            if on_progress:
                on_progress(idx, total, student)

        return result

    def split_by_class(
        self,
        records: list[AudioRecord],
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> dict[str, list[Path]]:
        records = self.filter_by_date(records)
        groups: dict[str, list[AudioRecord]] = defaultdict(list)

        for r in records:
            key = r.student.klass if r.student and r.student.klass else "未分班"
            groups[key].append(r)

        result = {}
        total = len(groups)
        for idx, (klass, recs) in enumerate(groups.items(), 1):
            klass_dir = self.output_dir / klass
            paths = []
            for r in recs:
                sub = klass_dir / (r.student.name if r.student else "未知")
                target = sub / r.file_path.name
                paths.append(self._transfer(r.file_path, target))
            result[klass] = paths
            if on_progress:
                on_progress(idx, total, klass)

        return result

    def pack_by_student(
        self,
        records: list[AudioRecord],
        on_progress: Optional[Callable[[int, int, StudentInfo], None]] = None,
    ) -> list[Path]:
        records = self.filter_by_date(records)
        groups: dict[StudentInfo, list[AudioRecord]] = defaultdict(list)
        for r in records:
            if r.student:
                groups[r.student].append(r)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        archives = []
        total = len(groups)
        for idx, (student, recs) in enumerate(groups.items(), 1):
            zip_name = f"{student.klass + '_' if student.klass else ''}{student.name}.zip"
            zip_path = self.output_dir / zip_name
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for r in recs:
                    arcname = f"{r.date_str}_{r.piece or 'unknown'}{r.extension}"
                    zf.write(r.file_path, arcname=arcname)
            archives.append(zip_path)
            if on_progress:
                on_progress(idx, total, student)

        return archives

    def add_comment_tag(
        self, record: AudioRecord, comment: str
    ) -> Optional[Path]:
        if not comment:
            return None

        stem = record.file_path.stem
        new_stem = f"{stem}_{comment}"
        new_path = record.file_path.with_name(new_stem + record.extension)

        counter = 1
        while new_path.exists():
            new_path = record.file_path.with_name(
                f"{stem}_{comment}_{counter}{record.extension}"
            )
            counter += 1

        if self.copy:
            shutil.copy2(record.file_path, new_path)
        else:
            shutil.move(str(record.file_path), str(new_path))

        record.file_path = new_path
        record.comment = comment
        if comment not in record.tags:
            record.tags.append(comment)

        return new_path

    def _student_dir(self, student: StudentInfo) -> Path:
        parts = []
        if student.klass:
            parts.append(student.klass)
        parts.append(student.name)
        path = self.output_dir.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _transfer(self, src: Path, dst: Path) -> Path:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if self.copy:
            shutil.copy2(src, dst)
        else:
            shutil.move(str(src), str(dst))
        return dst
