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
                    r.student.klass if r.student and r.student.klass else "",
                    r.student.name if r.student else "",
                    r.practice_date or datetime.min,
                )
            )

        return dict(sorted(groups.items()))

    def _student_key(self, student: StudentInfo) -> tuple:
        return (student.klass or "", student.name, student.student_id or "")

    def generate_progress_report(
        self,
        records: list[AudioRecord],
        expected_students: Optional[list[StudentInfo]] = None,
    ) -> dict:
        by_student: dict[tuple, tuple[StudentInfo, list[AudioRecord]]] = {}
        by_class: dict[str, list[AudioRecord]] = defaultdict(list)
        by_piece: dict[str, list[AudioRecord]] = defaultdict(list)
        by_date: dict[str, list[AudioRecord]] = defaultdict(list)

        graded_count = 0
        passed_count = 0

        for r in records:
            if r.student:
                key = self._student_key(r.student)
                if key not in by_student:
                    by_student[key] = (r.student, [])
                by_student[key][1].append(r)
                klass_key = r.student.klass or "未分班"
                by_class[klass_key].append(r)
            else:
                by_class["未识别"].append(r)

            if r.piece:
                by_piece[r.piece].append(r)
            if r.practice_date:
                by_date[r.date_str].append(r)

            if r.rating or r.passed is not None or r.comment:
                graded_count += 1
            if r.passed is True:
                passed_count += 1

        student_stats = {}
        for key, (student, recs) in by_student.items():
            total_duration = sum(r.duration_seconds or 0 for r in recs)
            pieces = {r.piece for r in recs if r.piece}
            graded = sum(1 for r in recs if r.rating or r.passed is not None or r.comment)
            passed = sum(1 for r in recs if r.passed is True)
            ratings = sorted({r.rating for r in recs if r.rating})
            student_stats[f"{student.klass or '未分班'}|{student.name}"] = {
                "klass": student.klass,
                "name": student.name,
                "student_id": student.student_id,
                "count": len(recs),
                "total_minutes": round(total_duration / 60, 1),
                "pieces": sorted(pieces),
                "last_date": max(
                    (r.practice_date for r in recs if r.practice_date),
                    default=None,
                ),
                "graded_count": graded,
                "passed_count": passed,
                "ratings": ratings,
            }

        class_stats = {}
        for klass, recs in by_class.items():
            class_students = {
                (r.student.klass or "", r.student.name)
                for r in recs if r.student
            }
            total_duration = sum(r.duration_seconds or 0 for r in recs)
            pieces = {r.piece for r in recs if r.piece}
            graded = sum(1 for r in recs if r.rating or r.passed is not None or r.comment)
            passed = sum(1 for r in recs if r.passed is True)
            class_stats[klass] = {
                "total_records": len(recs),
                "student_count": len(class_students),
                "total_minutes": round(total_duration / 60, 1),
                "pieces": sorted(pieces),
                "graded_count": graded,
                "passed_count": passed,
                "completion_rate": 0.0,
                "expected_count": 0,
                "missing_count": 0,
            }

        missing = []
        missing_by_class: dict[str, list[dict]] = defaultdict(list)
        if expected_students:
            submitted_keys = {k for k in by_student.keys()}
            for es in expected_students:
                key = self._student_key(es)
                if key not in submitted_keys:
                    entry = {"name": es.name, "klass": es.klass, "student_id": es.student_id}
                    missing.append(entry)
                    missing_by_class[es.klass or "未分班"].append(entry)

            for klass, stats in class_stats.items():
                class_expected = [
                    es for es in expected_students
                    if (es.klass or "未分班") == klass
                ]
                expected_count = len(class_expected)
                submitted_in_class = sum(
                    1 for es in expected_students
                    if (es.klass or "未分班") == klass and self._student_key(es) in submitted_keys
                )
                stats["expected_count"] = expected_count
                stats["missing_count"] = len(missing_by_class.get(klass, []))
                if expected_count > 0:
                    stats["completion_rate"] = round(
                        submitted_in_class / expected_count * 100, 1
                    )

        return {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "total_records": len(records),
            "total_students": len(by_student),
            "total_pieces": len(by_piece),
            "total_classes": len(class_stats),
            "graded_total": graded_count,
            "passed_total": passed_count,
            "date_range": {
                "start": min(by_date.keys()) if by_date else None,
                "end": max(by_date.keys()) if by_date else None,
            },
            "student_stats": student_stats,
            "class_stats": class_stats,
            "pieces": sorted(by_piece.keys()),
            "missing_students": missing,
            "missing_by_class": dict(missing_by_class),
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
                "时长", "评级", "是否通过", "评语",
                "批改时间", "源文件",
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
                    r.rating or "",
                    ("通过" if r.passed else ("未通过" if r.passed is False else "")),
                    r.comment or "",
                    r.graded_at.strftime("%Y-%m-%d %H:%M:%S") if r.graded_at else "",
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
        lines.append("## 总体概览")
        lines.append("")
        lines.append(f"- 总录音数：{progress['total_records']}")
        lines.append(f"- 学生人数：{progress['total_students']}")
        lines.append(f"- 班级数量：{progress['total_classes']}")
        lines.append(f"- 曲目总数：{progress['total_pieces']}")
        lines.append(f"- 已批改：{progress['graded_total']} 份")
        lines.append(f"- 通过：{progress['passed_total']} 份")
        dr = progress["date_range"]
        if dr["start"]:
            lines.append(f"- 日期范围：{dr['start']} ~ {dr['end']}")
        lines.append("")

        lines.append("## 各班完成情况")
        lines.append("")
        lines.append("| 班级 | 提交人数/应提交 | 完成率 | 录音数 | 总时长(分钟) | 已批改 | 通过 | 缺交人数 |")
        lines.append("|------|------------------|--------|--------|--------------|--------|------|----------|")
        for klass, s in sorted(progress["class_stats"].items()):
            submitted = s["student_count"]
            expected = s["expected_count"] or "-"
            rate = f"{s['completion_rate']}%" if s["expected_count"] else "-"
            missing = s["missing_count"] if s["expected_count"] else "-"
            lines.append(
                f"| {klass} | {submitted}/{expected} | {rate} | "
                f"{s['total_records']} | {s['total_minutes']} | "
                f"{s['graded_count']} | {s['passed_count']} | {missing} |"
            )
        lines.append("")

        if progress["missing_students"]:
            lines.append("## 缺交名单（按班级）")
            lines.append("")
            for klass, mlist in sorted(progress["missing_by_class"].items()):
                lines.append(f"### {klass}（{len(mlist)} 人）")
                lines.append("")
                for m in mlist:
                    sid = f" ({m['student_id']})" if m.get("student_id") else ""
                    lines.append(f"- {m['name']}{sid}")
                lines.append("")

        lines.append("## 班级练习清单")
        lines.append("")
        for group_name, recs in groups.items():
            lines.append(f"### {group_name}")
            lines.append("")
            lines.append("| 学生 | 日期 | 曲目 | 时长 | 评级 | 通过 | 评语 |")
            lines.append("|------|------|------|------|------|------|------|")
            for r in recs:
                name = r.student.name if r.student else "未知"
                rating = r.rating or "-"
                passed = "✓" if r.passed else ("✗" if r.passed is False else "-")
                comment = r.comment or "-"
                lines.append(
                    f"| {name} | {r.date_str} | {r.piece or '-'} | "
                    f"{r.duration_str} | {rating} | {passed} | {comment} |"
                )
            lines.append("")

        lines.append("## 学生统计（按班级排序）")
        lines.append("")
        lines.append("| 班级 | 学生 | 提交次数 | 总时长(分钟) | 曲目数 | 最近提交 | 已批改 | 通过 | 评级 |")
        lines.append("|------|------|----------|--------------|--------|----------|--------|------|------|")
        rows = sorted(
            progress["student_stats"].items(),
            key=lambda kv: (kv[1]["klass"] or "", kv[1]["name"]),
        )
        for _, s in rows:
            last = s["last_date"].strftime("%Y-%m-%d") if s["last_date"] else "-"
            ratings = ",".join(s["ratings"]) if s["ratings"] else "-"
            lines.append(
                f"| {s['klass'] or '-'} | {s['name']} | {s['count']} | "
                f"{s['total_minutes']} | {len(s['pieces'])} | {last} | "
                f"{s['graded_count']} | {s['passed_count']} | {ratings} |"
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
            prefix = f"{record.student.klass}_" if record.student.klass else ""
            return f"{prefix}{record.student.name}"
        if group_by == "date" and record.practice_date:
            return record.date_str
        if group_by == "piece" and record.piece:
            return record.piece
        return "其他"
