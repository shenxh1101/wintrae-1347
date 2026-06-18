from __future__ import annotations

import re
import shutil
import traceback
from pathlib import Path
from typing import Callable, Optional

from .models import AudioRecord, OperationLogBuilder, StudentInfo


DEFAULT_TEMPLATE = "{date}_{class}_{student}_{piece}{comment}"
SAFE_PATTERN = re.compile(r'[\\/:*?"<>|]')


class RenameResult:
    def __init__(
        self,
        record: AudioRecord,
        target: Optional[Path],
        old_path: Optional[Path] = None,
        status: str = "success",
        message: str = "",
    ):
        self.record = record
        self.target = target
        self.old_path = old_path
        self.status = status
        self.message = message

    @property
    def changed(self) -> bool:
        return self.target is not None


class NamingEngine:
    def __init__(
        self,
        template: Optional[str] = None,
        output_dir: Optional[Path] = None,
        organize_by_class: bool = True,
        organize_by_student: bool = True,
        overwrite: bool = False,
        dry_run: bool = False,
        operation_log: Optional[OperationLogBuilder] = None,
    ):
        self.template = template or DEFAULT_TEMPLATE
        self.output_dir = Path(output_dir) if output_dir else None
        self.organize_by_class = organize_by_class
        self.organize_by_student = organize_by_student
        self.overwrite = overwrite
        self.dry_run = dry_run
        self.log = operation_log or OperationLogBuilder()

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
    ) -> RenameResult:
        target = self.resolve_target(record)
        old_path = record.file_path

        if target == record.file_path:
            self.log.record(
                operation="rename",
                source=old_path,
                target=target,
                status="unchanged",
                message="文件名无需变更",
                record=record,
            )
            return RenameResult(record, None, old_path, "unchanged", "文件名无需变更")

        resolved_target = target
        if target.exists() and not self.overwrite:
            resolved_target = self._resolve_duplicate(target)

        try:
            if not self.dry_run:
                resolved_target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(record.file_path), str(resolved_target))
            record.file_path = resolved_target

            if on_rename:
                on_rename(record, old_path)

            status = "preview" if self.dry_run else "success"
            msg = "[预览] 未实际执行" if self.dry_run else ""
            self.log.record(
                operation="rename",
                source=old_path,
                target=resolved_target,
                status=status,
                message=msg,
                record=record,
            )
            return RenameResult(record, resolved_target, old_path, status, msg)
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            self.log.record(
                operation="rename",
                source=old_path,
                target=resolved_target,
                status="failed",
                message=err_msg,
                record=record,
                extra={"traceback": traceback.format_exc()},
            )
            return RenameResult(record, None, old_path, "failed", err_msg)

    def rename_batch(
        self,
        records: list[AudioRecord],
        on_progress: Optional[Callable[[int, int, AudioRecord], None]] = None,
    ) -> list[RenameResult]:
        results = []
        total = len(records)
        for idx, record in enumerate(records, 1):
            result = self.rename(record)
            results.append(result)
            if on_progress:
                on_progress(idx, total, record)
        return results

    def summary(self, results: list[RenameResult]) -> dict:
        return {
            "total": len(results),
            "success": sum(1 for r in results if r.status == "success"),
            "preview": sum(1 for r in results if r.status == "preview"),
            "unchanged": sum(1 for r in results if r.status == "unchanged"),
            "failed": sum(1 for r in results if r.status == "failed"),
        }

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
