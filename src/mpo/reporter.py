from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
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
            stat_key = f"{student.klass or '未分班'}|{student.name}"
            if student.student_id:
                stat_key += f"|{student.student_id}"
            student_stats[stat_key] = {
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
                self._student_key(r.student)
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

    def generate_trend_report(
        self,
        records: list[AudioRecord],
        expected_students: Optional[list[StudentInfo]] = None,
        granularity: str = "week",
    ) -> dict:
        if granularity not in ("week", "month"):
            raise ValueError(f"不支持的时间粒度: {granularity}，请使用 week 或 month")

        def period_key(d: datetime) -> str:
            if granularity == "week":
                start = d - timedelta(days=d.weekday())
                return start.strftime("%Y-%m-%d") + "周"
            return d.strftime("%Y-%m")

        periods: dict[str, list[AudioRecord]] = defaultdict(list)
        for r in records:
            if r.practice_date:
                periods[period_key(r.practice_date)].append(r)

        sorted_periods = sorted(periods.keys())
        if not sorted_periods:
            return {"granularity": granularity, "periods": {}}

        expected_by_class: dict[str, list[StudentInfo]] = defaultdict(list)
        if expected_students:
            for es in expected_students:
                expected_by_class[es.klass or "未分班"].append(es)

        period_stats: dict[str, dict] = {}
        all_classes: set[str] = set()

        for period, precs in periods.items():
            by_student_in_period: dict[tuple, StudentInfo] = {}
            by_class_in_period: dict[str, list[AudioRecord]] = defaultdict(list)
            graded = 0
            passed = 0

            for r in precs:
                if r.student:
                    key = self._student_key(r.student)
                    by_student_in_period[key] = r.student
                    klass = r.student.klass or "未分班"
                    by_class_in_period[klass].append(r)
                    all_classes.add(klass)
                if r.rating or r.passed is not None or r.comment:
                    graded += 1
                if r.passed is True:
                    passed += 1

            class_data: dict[str, dict] = {}
            for klass in sorted(all_classes):
                class_recs = by_class_in_period.get(klass, [])
                class_submitted_students: set[tuple] = {
                    self._student_key(r.student)
                    for r in class_recs if r.student
                }
                class_expected = expected_by_class.get(klass, [])
                class_submitted_count = len(class_submitted_students)
                class_expected_count = len(class_expected)
                class_missing = class_expected_count - class_submitted_count if class_expected_count > 0 else 0
                class_graded = sum(1 for r in class_recs if r.rating or r.passed is not None or r.comment)
                class_passed = sum(1 for r in class_recs if r.passed is True)
                class_total = len(class_recs)
                class_rate = round(class_submitted_count / class_expected_count * 100, 1) if class_expected_count > 0 else 0.0
                class_pass_rate = round(class_passed / class_graded * 100, 1) if class_graded > 0 else 0.0

                class_data[klass] = {
                    "total_records": class_total,
                    "submitted_students": class_submitted_count,
                    "expected_students": class_expected_count,
                    "missing_students": class_missing,
                    "graded_count": class_graded,
                    "passed_count": class_passed,
                    "completion_rate": class_rate,
                    "pass_rate": class_pass_rate,
                }

            period_stats[period] = {
                "total_records": len(precs),
                "submitted_students": len(by_student_in_period),
                "graded_count": graded,
                "passed_count": passed,
                "class_data": class_data,
            }

        prev_period = None
        for period in sorted_periods:
            if prev_period and prev_period in period_stats:
                cur = period_stats[period]
                prev = period_stats[prev_period]
                cur["compared_to_previous"] = {
                    "records_delta": cur["total_records"] - prev["total_records"],
                    "students_delta": cur["submitted_students"] - prev["submitted_students"],
                    "graded_delta": cur["graded_count"] - prev["graded_count"],
                    "passed_delta": cur["passed_count"] - prev["passed_count"],
                }
                for klass in cur["class_data"]:
                    cd = cur["class_data"][klass]
                    pd = prev["class_data"].get(klass, {})
                    cd["compared_to_previous"] = {
                        "submitted_delta": cd["submitted_students"] - pd.get("submitted_students", 0),
                        "missing_delta": cd["missing_students"] - pd.get("missing_students", 0),
                        "graded_delta": cd["graded_count"] - pd.get("graded_count", 0),
                        "pass_rate_delta": round(cd["pass_rate"] - pd.get("pass_rate", 0), 1),
                    }
            prev_period = period

        return {
            "granularity": granularity,
            "periods": dict(sorted(period_stats.items())),
            "period_order": sorted_periods,
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

    def write_trend_csv(
        self,
        trend: dict,
        filename: str = "trend_summary.csv",
    ) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / filename

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "周期", "班级", "提交录音数", "提交人数", "应提交人数",
                "缺交人数", "完成率", "已批改数", "通过数", "通过率",
                "提交人数环比", "缺交人数环比", "通过率环比",
            ])
            for period in trend.get("period_order", []):
                ps = trend["periods"][period]
                for klass, cd in ps["class_data"].items():
                    delta = cd.get("compared_to_previous", {})
                    submit_delta = delta.get("submitted_delta", 0)
                    missing_delta = delta.get("missing_delta", 0)
                    pass_delta = delta.get("pass_rate_delta", 0)
                    writer.writerow([
                        period, klass,
                        cd["total_records"], cd["submitted_students"], cd["expected_students"],
                        cd["missing_students"], f"{cd['completion_rate']}%",
                        cd["graded_count"], cd["passed_count"], f"{cd['pass_rate']}%",
                        f"{submit_delta:+d}", f"{missing_delta:+d}", f"{pass_delta:+.1f}%",
                    ])
        return path

    def write_markdown(
        self,
        progress: dict,
        groups: dict,
        filename: str = "progress_report.md",
        trend: Optional[dict] = None,
        trend_granularity: str = "week",
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

        if trend and trend.get("periods"):
            period_label = "周" if trend_granularity == "week" else "月"
            lines.append(f"## 按{period_label}趋势")
            lines.append("")
            for period in trend.get("period_order", []):
                ps = trend["periods"][period]
                lines.append(f"### {period_label}度：{period}")
                lines.append("")
                comp = ps.get("compared_to_previous")
                if comp:
                    lines.append(
                        f"环比：录音数 {comp['records_delta']:+d}，"
                        f"提交人数 {comp['students_delta']:+d}，"
                        f"已批改 {comp['graded_delta']:+d}，"
                        f"通过 {comp['passed_delta']:+d}"
                    )
                    lines.append("")
                lines.append("| 班级 | 录音数 | 提交/应提交 | 完成率 | 已批改 | 通过数 | 通过率 | 缺交 | 环比 |")
                lines.append("|------|--------|-------------|--------|--------|--------|--------|------|------|")
                for klass, cd in ps["class_data"].items():
                    delta = cd.get("compared_to_previous", {})
                    submit_delta = delta.get("submitted_delta", 0)
                    trend_str = f"提交{submit_delta:+d}"
                    if "pass_rate_delta" in delta:
                        trend_str += f" 通过率{delta['pass_rate_delta']:+.1f}%"
                    lines.append(
                        f"| {klass} | {cd['total_records']} | "
                        f"{cd['submitted_students']}/{cd['expected_students']} | "
                        f"{cd['completion_rate']}% | {cd['graded_count']} | "
                        f"{cd['passed_count']} | {cd['pass_rate']}% | "
                        f"{cd['missing_students']} | {trend_str} |"
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
        lines.append("| 班级 | 学生 | 学号 | 提交次数 | 总时长(分钟) | 曲目数 | 最近提交 | 已批改 | 通过 | 评级 |")
        lines.append("|------|------|------|----------|--------------|--------|----------|--------|------|------|")
        rows = sorted(
            progress["student_stats"].items(),
            key=lambda kv: (kv[1]["klass"] or "", kv[1]["name"], kv[1].get("student_id") or ""),
        )
        for _, s in rows:
            last = s["last_date"].strftime("%Y-%m-%d") if s["last_date"] else "-"
            ratings = ",".join(s["ratings"]) if s["ratings"] else "-"
            sid = s.get("student_id") or "-"
            lines.append(
                f"| {s['klass'] or '-'} | {s['name']} | {sid} | {s['count']} | "
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
