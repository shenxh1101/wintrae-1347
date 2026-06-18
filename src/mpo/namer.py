from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Callable, Optional

from .models import AudioRecord, StudentInfo


DEFAULT_TEMPLATE = "{date}_{class}_{student}_{piece}{comment}"
SAFE_PATTERN = re.compile(r'[\\/:*?"<>|]')


class NamingEngine:
    def __init__(
        self,
        template: Optional[str] = None,
        output_dir: Optional[Path] = None,
        organize_by_class: bool = True,
        organize_by_student: bool = True,
        overwrite: bool = False,
        dry_run: bool = False,
    ):
        self.template = template or DEFAULT_TEMPLATE
        self.output_dir = Path(output_dir) if output_dir else None
        self.organize_by_class = organize_by_class
        self.organize_by_student = organize_by_student
        self.overwrite = overwrite
        self.dry_run = dry_run

    def generate_name(self, record: AudioRecord) -> str:
        context = self._build_context(record)
        name = self.template.format(**context)
        name = SAFE_PATTERN.sub("_", name)
        name = re.sub(r"_{2,}", "_", name).strip("_.")
        if not name.lower().endswith(record.extension.lower()):
            name += record.extension
        return name

    def resolve_target(self, record: AudioRecord) -> Path:
        target_name = self.generate_name(record)
        target_dir = self._resolve_target_dir(record)
        return target_dir / target_name

    def rename(
        self,
        record: AudioRecord,
        on_rename: Optional[Callable[[AudioRecord, Path], None]] = None,
    ) -> Optional[Path]:
        target = self.resolve_target(record)

        if target == record.file_path:
            return None

        if target.exists() and not self.overwrite:
            target = self._resolve_duplicate(target)

        if not self.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(record.file_path), str(target))

        old_path = record.file_path
        record.file_path = target

        if on_rename:
            on_rename(record, old_path)

        return target

    def rename_batch(
        self,
        records: list[AudioRecord],
        on_progress: Optional[Callable[[int, int, AudioRecord], None]] = None,
    ) -> list[tuple[AudioRecord, Optional[Path]]]:
        results = []
        total = len(records)
        for idx, record in enumerate(records, 1):
            try:
                result = self.rename(record)
                results.append((record, result))
            except Exception as e:
                results.append((record, None))
            if on_progress:
                on_progress(idx, total, record)
        return results

    def _build_context(self, record: AudioRecord) -> dict:
        student = record.student or StudentInfo(name="未知学生")
        return {
            "date": record.date_str,
            "class": student.klass or "未分班",
            "student": student.name,
            "piece": record.piece or "未知曲目",
            "duration": record.duration_str.replace(":", "-"),
            "comment": f"_{record.comment}" if record.comment else "",
            "ext": record.extension,
            "original": record.original_name,
        }

    def _resolve_target_dir(self, record: AudioRecord) -> Path:
        base = self.output_dir or record.file_path.parent
        parts = []

        if self.organize_by_class and record.student and record.student.klass:
            parts.append(record.student.klass)
        if self.organize_by_student and record.student:
            parts.append(record.student.name)

        return base.joinpath(*parts) if parts else base

    @staticmethod
    def _resolve_duplicate(target: Path) -> Path:
        stem, suffix = target.stem, target.suffix
        parent = target.parent
        counter = 1
        while True:
            candidate = parent / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
