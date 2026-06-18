from __future__ import annotations

import re
import shutil
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .models import AudioRecord, OperationLogBuilder, StudentInfo


SAFE_PATTERN = re.compile(r'[\\/:*?"<>|]')


class Splitter:
    def __init__(
        self,
        output_dir: Optional[Path] = None,
        copy: bool = True,
        date_range: Optional[tuple[datetime, datetime]] = None,
        operation_log: Optional[OperationLogBuilder] = None,
    ):
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "output"
        self.copy = copy
        self.date_range = date_range
        self.log = operation_log or OperationLogBuilder()

    def filter_by_date(
        self, records: list[AudioRecord]
    ) -> list[AudioRecord]:
        if not self.date_range:
            return records
        start, end = self.date_range
        filtered = [
            r for r in records
            if r.practice_date and start <= r.practice_date <= end
        ]
        for r in records:
            if r not in filtered:
                self.log.record(
                    operation="filter",
                    source=r.file_path,
                    status="skipped",
                    message="日期不在范围内",
                    record=r,
                )
        return filtered

    @staticmethod
    def _build_filename(record: AudioRecord) -> str:
        parts = [record.date_str]
        if record.student and record.student.klass:
            parts.append(record.student.klass)
        if record.student:
            parts.append(record.student.name)
        if record.piece:
            parts.append(record.piece)
        if record.rating:
            parts.append(f"评级{record.rating}")
        if record.passed is True:
            parts.append("通过")
        elif record.passed is False:
            parts.append("未通过")
        if record.comment:
            parts.append(record.comment)
        stem = "_".join(SAFE_PATTERN.sub("_", p) for p in parts if p)
        stem = re.sub(r"_{2,}", "_", stem).strip("_.")
        return stem + record.extension

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
            else:
                groups[StudentInfo(name="未识别")].append(r)

        result = {}
        total = len(groups)
        for idx, (student, recs) in enumerate(groups.items(), 1):
            student_dir = self._student_dir(student)
            paths = []
            for r in recs:
                target_name = self._build_filename(r)
                target = self._resolve_dup(student_dir / target_name)
                try:
                    final = self._transfer(r.file_path, target)
                    paths.append(final)
                    self.log.record(
                        operation="split_student",
                        source=r.file_path,
                        target=final,
                        status="success",
                        record=r,
                    )
                except Exception as e:
                    self.log.record(
                        operation="split_student",
                        source=r.file_path,
                        target=target,
                        status="failed",
                        message=str(e),
                        record=r,
                    )
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
                sub = klass_dir / (r.student.name if r.student else "未识别")
                target_name = self._build_filename(r)
                target = self._resolve_dup(sub / target_name)
                try:
                    final = self._transfer(r.file_path, target)
                    paths.append(final)
                    self.log.record(
                        operation="split_class",
                        source=r.file_path,
                        target=final,
                        status="success",
                        record=r,
                    )
                except Exception as e:
                    self.log.record(
                        operation="split_class",
                        source=r.file_path,
                        target=target,
                        status="failed",
                        message=str(e),
                        record=r,
                    )
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
            else:
                groups[StudentInfo(name="未识别")].append(r)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        archives = []
        total = len(groups)
        for idx, (student, recs) in enumerate(groups.items(), 1):
            klass_part = student.klass + "_" if student.klass else ""
            zip_name = f"{klass_part}{student.name}.zip"
            zip_path = self._resolve_dup(self.output_dir / zip_name)
            try:
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for r in recs:
                        arcname = self._build_filename(r)
                        zf.write(r.file_path, arcname=arcname)
                        self.log.record(
                            operation="pack",
                            source=r.file_path,
                            target=zip_path,
                            status="success",
                            message=f"zip内名: {arcname}",
                            record=r,
                            extra={"arcname": arcname},
                        )
                archives.append(zip_path)
            except Exception as e:
                self.log.record(
                    operation="pack",
                    source=zip_path,
                    status="failed",
                    message=str(e),
                )
            if on_progress:
                on_progress(idx, total, student)

        return archives

    def add_comment_tag(
        self, record: AudioRecord, comment: str
    ) -> Optional[Path]:
        if not comment:
            return None
        target_name = self._build_filename(record)
        new_path = self._resolve_dup(record.file_path.with_name(target_name))

        try:
            if self.copy:
                shutil.copy2(record.file_path, new_path)
            else:
                shutil.move(str(record.file_path), str(new_path))
            record.file_path = new_path
            if record.comment:
                record.comment = f"{record.comment}_{comment}"
            else:
                record.comment = comment
            if comment not in record.tags:
                record.tags.append(comment)
            self.log.record(
                operation="tag_comment",
                source=record.file_path,
                target=new_path,
                status="success",
                message=f"评语: {comment}",
                record=record,
            )
            return new_path
        except Exception as e:
            self.log.record(
                operation="tag_comment",
                source=record.file_path,
                target=new_path,
                status="failed",
                message=str(e),
                record=record,
            )
            return None

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

    @staticmethod
    def _resolve_dup(target: Path) -> Path:
        if not target.exists():
            return target
        stem, suffix = target.stem, target.suffix
        parent = target.parent
        counter = 1
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
