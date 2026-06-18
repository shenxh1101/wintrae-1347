from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import AudioRecord, StudentInfo


class Reporter:
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir) if output_dir else Path.cwd()

    def generate_practice_list(
        self,
        records: list[AudioRecord],
        group_by: str = "class",
    ) -> dict:
        groups: dict[str, list[AudioRecord]] = defaultdict(list)

        for r in records:
            key = self._get_group_key(r, group_by)
            groups[key].append(r)

        for key in groups:
            groups[key].sort(
                key=lambda r: (
                    r.student.name if r.student else "",
                    r.practice_date or datetime.min,
                )
            )

        return dict(groups)

    def generate_progress_report(
        self,
        records: list[AudioRecord],
        expected_students: Optional[list[StudentInfo]] = None,
    ) -> dict:
        by_student: dict[StudentInfo, list[AudioRecord]] = defaultdict(list)
        by_piece: dict[str, list[AudioRecord]] = defaultdict(list)
        by_date: dict[str, list[AudioRecord]] = defaultdict(list)

        for r in records:
            if r.student:
                by_student[r.student].append(r)
            if r.piece:
                by_piece[r.piece].append(r)
            if r.practice_date:
                by_date[r.date_str].append(r)

        student_stats = {}
        for student, recs in by_student.items():
            total_duration = sum(
                r.duration_seconds or 0 for r in recs
            )
            pieces = {r.piece for r in recs if r.piece}
            student_stats[student.name] = {
                "klass": student.klass,
                "count": len(recs),
                "total_minutes": round(total_duration / 60, 1),
                "pieces": sorted(pieces),
                "last_date": max(
                    (r.practice_date for r in recs if r.practice_date),
                    default=None,
                ),
            }

        missing = []
        if expected_students:
            submitted_names = {s.name for s in by_student.keys()}
            for es in expected_students:
                if es.name not in submitted_names:
                    missing.append({"name": es.name, "klass": es.klass})

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "total_records": len(records),
            "total_students": len(by_student),
            "total_pieces": len(by_piece),
            "date_range": {
                "start": min(by_date.keys()) if by_date else None,
                "end": max(by_date.keys()) if by_date else None,
            },
            "student_stats": student_stats,
            "pieces": sorted(by_piece.keys()),
            "missing_students": missing,
        }

    def write_csv(
        self,
        records: list[AudioRecord],
        filename: str = "practice_list.csv",
    ) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "班级", "学生姓名", "练习日期", "曲目",
                "时长", "评语", "源文件",
            ])
            for r in sorted(
                records,
                key=lambda x: (
                    x.student.klass if x.student else "",
                    x.student.name if x.student else "",
                    x.practice_date or datetime.min,
                ),
            ):
                writer.writerow([
                    r.student.klass if r.student else "",
                    r.student.name if r.student else "",
                    r.date_str,
                    r.piece or "",
                    r.duration_str,
                    r.comment or "",
                    str(r.file_path),
                ])

        return path

    def write_json(
        self, data: dict, filename: str = "report.json"
    ) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename

        def default(o):
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, Path):
                return str(o)
            if isinstance(o, StudentInfo):
                return {"name": o.name, "klass": o.klass, "student_id": o.student_id}
            return str(o)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=default)

        return path

    def write_markdown(
        self,
        progress: dict,
        groups: dict,
        filename: str = "progress_report.md",
    ) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename

        lines = []
        lines.append("# 练琴进度报告")
        lines.append("")
        lines.append(f"生成时间：{progress['generated_at']}")
        lines.append("")
        lines.append("## 概览")
        lines.append("")
        lines.append(f"- 总录音数：{progress['total_records']}")
        lines.append(f"- 学生人数：{progress['total_students']}")
        lines.append(f"- 曲目总数：{progress['total_pieces']}")
        dr = progress["date_range"]
        if dr["start"]:
            lines.append(f"- 日期范围：{dr['start']} ~ {dr['end']}")
        lines.append("")

        if progress["missing_students"]:
            lines.append("## 缺交学生")
            lines.append("")
            for m in progress["missing_students"]:
                klass = f" ({m['klass']})" if m["klass"] else ""
                lines.append(f"- {m['name']}{klass}")
            lines.append("")

        lines.append("## 班级练习清单")
        lines.append("")
        for group_name, recs in groups.items():
            lines.append(f"### {group_name}")
            lines.append("")
            lines.append("| 学生 | 日期 | 曲目 | 时长 | 评语 |")
            lines.append("|------|------|------|------|------|")
            for r in recs:
                name = r.student.name if r.student else "未知"
                lines.append(
                    f"| {name} | {r.date_str} | {r.piece or '-'} | "
                    f"{r.duration_str} | {r.comment or '-'} |"
                )
            lines.append("")

        lines.append("## 学生统计")
        lines.append("")
        lines.append("| 学生 | 班级 | 提交次数 | 总时长(分钟) | 曲目数 | 最近提交 |")
        lines.append("|------|------|----------|--------------|--------|----------|")
        for name, s in sorted(progress["student_stats"].items()):
            last = s["last_date"].strftime("%Y-%m-%d") if s["last_date"] else "-"
            lines.append(
                f"| {name} | {s['klass'] or '-'} | {s['count']} | "
                f"{s['total_minutes']} | {len(s['pieces'])} | {last} |"
            )
        lines.append("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return path

    @staticmethod
    def _get_group_key(record: AudioRecord, group_by: str) -> str:
        if group_by == "class" and record.student and record.student.klass:
            return record.student.klass
        if group_by == "student" and record.student:
            return record.student.name
        if group_by == "date" and record.practice_date:
            return record.date_str
        if group_by == "piece" and record.piece:
            return record.piece
        return "其他"
