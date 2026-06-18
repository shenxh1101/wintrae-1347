from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .checker import Checker
from .config import Config
from .grader import GradingStore
from .models import (
    AudioRecord,
    OperationLogBuilder,
    StudentInfo,
)
from .namer import NamingEngine
from .reporter import Reporter
from .scanner import AudioScanner
from .splitter import Splitter

console = Console()


def _parse_date(s: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise click.BadParameter(f"无法解析日期: {s}，支持格式 YYYY-MM-DD, YYYYMMDD, YYYY/MM/DD")


@click.group()
@click.version_option(__version__, "-V", "--version")
@click.option("-c", "--config", "config_path", type=click.Path(path_type=Path),
              help="配置文件路径 (YAML)")
@click.option("-g", "--grading-file", type=click.Path(path_type=Path),
              help="批改记录文件 (JSON)，默认 ./grading_records.json")
@click.option("-v", "--verbose", is_flag=True, help="详细输出模式")
@click.pass_context
def cli(
    ctx: click.Context,
    config_path: Path | None,
    grading_file: Path | None,
    verbose: bool,
) -> None:
    """音乐教师练琴音频批量整理工具"""
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load(config_path)
    ctx.obj["verbose"] = verbose
    ctx.obj["grading_store"] = GradingStore(grading_file)


def _common_scan_options(f):
    f = click.option("-d", "--dir", "directory", required=True,
                     type=click.Path(exists=True, path_type=Path),
                     help="要扫描的目录")(f)
    f = click.option("--no-recursive", is_flag=True, help="不递归扫描子目录")(f)
    f = click.option("--ignore", multiple=True, help="忽略的正则模式，可多次指定")(f)
    f = click.option("--class-name", multiple=True, help="班级名称，用于从路径中识别班级，可多次指定")(f)
    f = click.option("--no-load-grading", is_flag=True, help="不自动加载已有批改记录")(f)
    return f


def _do_scan(
    directory: Path,
    no_recursive: bool,
    ignore: tuple[str, ...],
    class_name: tuple[str, ...],
    config: Config,
    grading_store: GradingStore | None = None,
    load_grading: bool = True,
    quiet: bool = False,
) -> tuple[AudioScanner, list[AudioRecord]]:
    ignore_patterns = list(config.ignore_patterns) + list(ignore)
    class_names = list(config.class_names) + list(class_name)
    scanner = AudioScanner(
        ignore_patterns=ignore_patterns,
        class_names=class_names,
    )
    result = scanner.scan_directory(directory, recursive=not no_recursive)
    if not quiet:
        console.print(f"[green]✓[/green] 扫描完成：找到 {result.total_count} 个音频文件"
                      + (f"，跳过 {result.skipped_count} 个" if result.skipped_count else ""))

    if grading_store and load_grading and grading_store.count:
        applied = grading_store.apply_to_records(result.records)
        if applied and not quiet:
            console.print(f"[cyan]ℹ[/cyan] 已加载 {applied} 条批改记录")

    return scanner, result.records


@cli.command("scan")
@_common_scan_options
@click.option("--json", "as_json", is_flag=True, help="以 JSON 格式输出")
@click.pass_context
def scan_cmd(
    ctx: click.Context,
    directory: Path,
    no_recursive: bool,
    ignore: tuple[str, ...],
    class_name: tuple[str, ...],
    no_load_grading: bool,
    as_json: bool,
) -> None:
    """扫描音频文件并识别学生、曲目、日期等信息"""
    config = ctx.obj["config"]
    store = ctx.obj["grading_store"]
    _, records = _do_scan(
        directory, no_recursive, ignore, class_name, config,
        grading_store=store, load_grading=not no_load_grading,
        quiet=as_json,
    )

    if as_json:
        import json
        def default(o):
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, Path):
                return str(o)
            if isinstance(o, StudentInfo):
                return {"name": o.name, "klass": o.klass}
            return str(o)
        click.echo(json.dumps(
            [{"file": str(r.file_path),
              "student": r.student.name if r.student else None,
              "class": r.student.klass if r.student else None,
              "piece": r.piece,
              "date": r.date_str,
              "duration": r.duration_str,
              "duration_seconds": r.duration_seconds,
              "comment": r.comment,
              "rating": r.rating,
              "passed": r.passed} for r in records],
            ensure_ascii=False, indent=2, default=default))
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("文件", overflow="fold")
    table.add_column("学生")
    table.add_column("班级")
    table.add_column("曲目", overflow="fold")
    table.add_column("日期")
    table.add_column("时长", justify="right")
    table.add_column("评级")
    table.add_column("通过")
    table.add_column("评语")

    for i, r in enumerate(records, 1):
        passed = "✓" if r.passed else ("✗" if r.passed is False else "-")
        table.add_row(
            str(i),
            r.file_path.name,
            r.student.name if r.student else "[yellow]未知[/yellow]",
            r.student.klass if r.student and r.student.klass else "-",
            r.piece or "[yellow]未知[/yellow]",
            r.date_str,
            r.duration_str,
            r.rating or "-",
            passed,
            r.comment or "-",
        )

    console.print(table)


@cli.command("rename")
@_common_scan_options
@click.option("-t", "--template", help=f"命名模板，默认 {{date}}_{{class}}_{{student}}_{{piece}}{{comment}}")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="输出目录，默认就地重命名")
@click.option("--no-organize-class", is_flag=True, help="不按班级建子目录")
@click.option("--no-organize-student", is_flag=True, help="不按学生建子目录")
@click.option("--overwrite", is_flag=True, help="覆盖已存在的文件")
@click.option("-n", "--dry-run", is_flag=True, help="仅预览，不实际重命名")
@click.option("--log-output", type=click.Path(path_type=Path), help="操作清单输出目录，默认与输出目录相同")
@click.pass_context
def rename_cmd(
    ctx: click.Context,
    directory: Path,
    no_recursive: bool,
    ignore: tuple[str, ...],
    class_name: tuple[str, ...],
    no_load_grading: bool,
    template: str | None,
    output: Path | None,
    no_organize_class: bool,
    no_organize_student: bool,
    overwrite: bool,
    dry_run: bool,
    log_output: Path | None,
) -> None:
    """按统一规则批量重命名音频文件"""
    config = ctx.obj["config"]
    store = ctx.obj["grading_store"]
    _, records = _do_scan(
        directory, no_recursive, ignore, class_name, config,
        grading_store=store, load_grading=not no_load_grading,
    )

    op_log = OperationLogBuilder()
    engine = NamingEngine(
        template=template or config.template,
        output_dir=output or (Path(config.output_dir) if config.output_dir else None),
        organize_by_class=config.organize_by_class and not no_organize_class,
        organize_by_student=config.organize_by_student and not no_organize_student,
        overwrite=overwrite,
        dry_run=dry_run,
        operation_log=op_log,
    )

    def on_progress(idx: int, total: int, r: AudioRecord) -> None:
        target = engine.resolve_target(r)
        tag = "[yellow][预览][/yellow]" if dry_run else ""
        console.print(f"  [{idx}/{total}] {tag}{r.file_path.name} → {target.name}")

    results = engine.rename_batch(records, on_progress=on_progress)
    summary = engine.summary(results)

    log_dir = Path(log_output) if log_output else (output or (
        Path(config.output_dir) if config.output_dir else directory
    ))
    log_path = op_log.write_csv(Path(log_dir), filename="rename_operation_log.csv")
    console.print(f"\n[cyan]ℹ[/cyan] 操作清单已保存：{log_path}")

    if dry_run:
        console.print(
            f"\n[cyan]预览完成[/cyan]：将重命名 {summary['preview']} 个文件，"
            f"{summary['unchanged']} 个无需变更"
            + (f"，{summary['failed']} 个失败" if summary["failed"] else "")
        )
    else:
        console.print(
            f"\n[green]✓[/green] 完成：已重命名 {summary['success']} 个文件，"
            f"{summary['unchanged']} 个无需变更"
            + (f"，{summary['failed']} 个失败" if summary["failed"] else "")
        )
        if summary["failed"]:
            sys.exit(1)


@cli.command("check")
@_common_scan_options
@click.option("--min-duration", type=float, help="最小时长（秒），默认 10 秒")
@click.option("--students-file", type=click.Path(exists=True, path_type=Path),
              help="学生名单文件 (TXT/CSV)，格式：班级,姓名,学号")
@click.option("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="结束日期 (YYYY-MM-DD)")
@click.pass_context
def check_cmd(
    ctx: click.Context,
    directory: Path,
    no_recursive: bool,
    ignore: tuple[str, ...],
    class_name: tuple[str, ...],
    no_load_grading: bool,
    min_duration: float | None,
    students_file: Path | None,
    start_date: str | None,
    end_date: str | None,
) -> None:
    """检查缺交名单、重复文件和时长过短记录"""
    config = ctx.obj["config"]
    store = ctx.obj["grading_store"]
    _, records = _do_scan(
        directory, no_recursive, ignore, class_name, config,
        grading_store=store, load_grading=not no_load_grading,
    )

    expected_students = None
    if students_file:
        expected_students = Checker.load_students_from_file(students_file)
        console.print(f"[cyan]ℹ[/cyan] 已加载 {len(expected_students)} 名预期学生")

    date_range = None
    if start_date or end_date:
        sd = _parse_date(start_date) if start_date else datetime.min
        ed = _parse_date(end_date) if end_date else datetime.max
        date_range = (sd, ed)

    checker = Checker(
        min_duration_seconds=min_duration or config.min_duration_seconds,
        expected_students=expected_students,
        date_range=date_range,
    )
    report = checker.run(records)

    console.print("")

    if report.errors:
        console.print(f"[bold red]错误 ({len(report.errors)})：[/bold red]")
        for issue in report.errors:
            console.print(f"  ✗ [{issue.category}] {issue.message}")

    if report.warnings:
        console.print(f"[bold yellow]警告 ({len(report.warnings)})：[/bold yellow]")
        for issue in report.warnings:
            console.print(f"  ⚠ [{issue.category}] {issue.message}")

    if report.info:
        console.print(f"[bold blue]提示 ({len(report.info)})：[/bold blue]")
        for issue in report.info:
            console.print(f"  ℹ [{issue.category}] {issue.message}")

    if not report.issues:
        console.print("[green]✓[/green] 未发现问题")

    if report.errors:
        sys.exit(1)


@cli.command("report")
@_common_scan_options
@click.option("-o", "--output", type=click.Path(path_type=Path), help="报告输出目录")
@click.option("--group-by", type=click.Choice(["class", "student", "date", "piece"]),
              default="class", show_default=True, help="分组方式")
@click.option("--students-file", type=click.Path(exists=True, path_type=Path),
              help="学生名单文件，用于标记缺交")
@click.option("--format", "fmt", type=click.Choice(["all", "csv", "json", "markdown"]),
              default="all", show_default=True, help="输出格式")
@click.option("--trend/--no-trend", default=False, help="是否生成周/月趋势报告")
@click.option("--trend-granularity", type=click.Choice(["week", "month", "both"]),
              default="both", show_default=True, help="趋势统计粒度")
@click.option("--save-grading", is_flag=True, help="将本次识别/批改信息保存到批改记录文件")
@click.pass_context
def report_cmd(
    ctx: click.Context,
    directory: Path,
    no_recursive: bool,
    ignore: tuple[str, ...],
    class_name: tuple[str, ...],
    no_load_grading: bool,
    output: Path | None,
    group_by: str,
    students_file: Path | None,
    fmt: str,
    trend: bool,
    trend_granularity: str,
    save_grading: bool,
) -> None:
    """生成班级练习清单、进度报告（支持周/月趋势）"""
    config = ctx.obj["config"]
    store = ctx.obj["grading_store"]
    _, records = _do_scan(
        directory, no_recursive, ignore, class_name, config,
        grading_store=store, load_grading=not no_load_grading,
    )

    reporter = Reporter(output_dir=output or Path.cwd())

    expected_students = None
    if students_file:
        expected_students = Checker.load_students_from_file(students_file)

    groups = reporter.generate_practice_list(records, group_by=group_by)
    progress = reporter.generate_progress_report(records, expected_students)

    trend_datas: list[dict] = []
    if trend:
        granularities = []
        if trend_granularity == "both":
            granularities = ["week", "month"]
        else:
            granularities = [trend_granularity]
        for g in granularities:
            trend_datas.append(
                reporter.generate_trend_report(records, expected_students, granularity=g)
            )

    outputs = []
    if fmt in ("all", "csv"):
        outputs.append(reporter.write_csv(records))
        for td in trend_datas:
            outputs.append(reporter.write_trend_csv(td))
    if fmt in ("all", "json"):
        json_data = {
            "progress": progress,
            "groups": {k: [str(r.file_path) for r in v] for k, v in groups.items()},
        }
        if trend_datas:
            json_data["trends"] = trend_datas
        outputs.append(reporter.write_json(json_data))
    if fmt in ("all", "markdown"):
        outputs.append(reporter.write_markdown(
            progress, groups, trends=trend_datas
        ))

    if save_grading:
        collected = store.collect_from_records(records)
        saved_path = store.save()
        console.print(f"[cyan]ℹ[/cyan] 已保存 {collected} 条批改记录到 {saved_path}")

    console.print("")
    console.print(f"[green]✓[/green] 报告生成完成：")
    for p in outputs:
        console.print(f"  - {p}")

    console.print("")
    console.print(
        f"  概览：共 {progress['total_records']} 个录音，"
        f"{progress['total_students']} 名学生，"
        f"{progress['total_classes']} 个班级，"
        f"{progress['total_pieces']} 首曲目"
    )
    console.print(
        f"  批改：{progress['graded_total']} 份已批改，"
        f"{progress['passed_total']} 份通过"
    )
    if progress["missing_students"]:
        console.print(f"  [yellow]⚠ 缺交学生：{len(progress['missing_students'])} 人[/yellow]")


@cli.command("grade")
@_common_scan_options
@click.option("--comment", type=str, help="批量添加评语")
@click.option("--rating", type=click.Choice(["A", "B", "C", "D", "优", "良", "中", "差"]),
              help="批量评级")
@click.option("--passed/--not-passed", default=None, help="批量标记是否通过")
@click.option("--student", "filter_student", type=str, help="仅批改指定学生（姓名）")
@click.option("--klass", "filter_klass", type=str, help="仅批改指定班级")
@click.option("--save/--no-save", default=True, help="是否保存批改记录（默认保存）")
@click.pass_context
def grade_cmd(
    ctx: click.Context,
    directory: Path,
    no_recursive: bool,
    ignore: tuple[str, ...],
    class_name: tuple[str, ...],
    no_load_grading: bool,
    comment: str | None,
    rating: str | None,
    passed: bool | None,
    filter_student: str | None,
    filter_klass: str | None,
    save: bool,
) -> None:
    """批量或单个批改：添加评语、评级、是否通过，并持久化保存"""
    config = ctx.obj["config"]
    store = ctx.obj["grading_store"]
    _, records = _do_scan(
        directory, no_recursive, ignore, class_name, config,
        grading_store=store, load_grading=not no_load_grading,
    )

    if not (comment or rating or passed is not None):
        console.print("[yellow]⚠[/yellow] 请至少指定 --comment、--rating 或 --passed/--not-passed")
        sys.exit(2)

    target_records = []
    for r in records:
        if filter_student and (not r.student or r.student.name != filter_student):
            continue
        if filter_klass and (not r.student or r.student.klass != filter_klass):
            continue
        target_records.append(r)

    if not target_records:
        console.print("[yellow]⚠[/yellow] 没有匹配的音频文件")
        return

    count = 0
    for r in target_records:
        if comment:
            if r.comment:
                r.comment = f"{r.comment}_{comment}"
            else:
                r.comment = comment
        if rating:
            r.rating = rating
        if passed is not None:
            r.passed = passed
        r.graded_at = datetime.now()
        count += 1

    console.print(f"[green]✓[/green] 已批改 {count} 个文件")

    if save:
        collected = store.collect_from_records(target_records)
        saved_path = store.save()
        console.print(f"[cyan]ℹ[/cyan] 批改记录已保存到 {saved_path}（共 {collected} 条）")


@cli.command("grade-export")
@click.option("-o", "--output", required=True, type=click.Path(path_type=Path),
              help="导出目录")
@click.option("--student", type=str, help="仅导出指定学生（姓名）")
@click.option("--klass", type=str, help="仅导出指定班级")
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]),
              default="csv", show_default=True, help="导出格式")
@click.option("-g", "--grading-file", type=click.Path(path_type=Path),
              help="批改记录文件 (JSON)，默认 ./grading_records.json")
@click.pass_context
def grade_export_cmd(
    ctx: click.Context,
    output: Path,
    student: str | None,
    klass: str | None,
    fmt: str,
    grading_file: Path | None,
) -> None:
    """导出批改历史记录（可按学生或班级筛选）"""
    if grading_file:
        store = GradingStore(grading_file)
    else:
        store = ctx.obj["grading_store"]

    if store.count == 0:
        console.print("[yellow]⚠[/yellow] 没有批改记录可导出")
        return

    path = store.export_history(
        output_dir=output,
        student=student,
        klass=klass,
        fmt=fmt,
    )
    console.print(
        f"[green]✓[/green] 已导出 {store.count} 条批改记录到 {path}"
    )


@cli.command("split")
@_common_scan_options
@click.option("-o", "--output", required=True, type=click.Path(path_type=Path),
              help="输出目录")
@click.option("--mode", type=click.Choice(["student", "class", "pack"]),
              default="student", show_default=True,
              help="分割方式：按学生、按班级、或打包为 zip")
@click.option("--start-date", type=str, help="开始日期 (YYYY-MM-DD)")
@click.option("--end-date", type=str, help="结束日期 (YYYY-MM-DD)")
@click.option("--comment", type=str, help="为所有文件追加评语标签")
@click.option("--rating", type=click.Choice(["A", "B", "C", "D", "优", "良", "中", "差"]),
              help="批量评级（同时写入批改记录）")
@click.option("--passed/--not-passed", default=None, help="批量标记是否通过")
@click.option("--move", is_flag=True, help="移动文件而非复制")
@click.option("--save-grading/--no-save-grading", default=True,
              help="是否保存批改记录（默认保存）")
@click.option("--log-output", type=click.Path(path_type=Path), help="操作清单输出目录，默认与输出目录相同")
@click.pass_context
def split_cmd(
    ctx: click.Context,
    directory: Path,
    no_recursive: bool,
    ignore: tuple[str, ...],
    class_name: tuple[str, ...],
    no_load_grading: bool,
    output: Path,
    mode: str,
    start_date: str | None,
    end_date: str | None,
    comment: str | None,
    rating: str | None,
    passed: bool | None,
    move: bool,
    save_grading: bool,
    log_output: Path | None,
) -> None:
    """按日期抽取、追加评语、批改、按学生打包"""
    config = ctx.obj["config"]
    store = ctx.obj["grading_store"]
    _, records = _do_scan(
        directory, no_recursive, ignore, class_name, config,
        grading_store=store, load_grading=not no_load_grading,
    )

    date_range = None
    if start_date or end_date:
        sd = _parse_date(start_date) if start_date else datetime.min
        ed = _parse_date(end_date) if end_date else datetime.max
        date_range = (sd, ed)
        console.print(f"[cyan]ℹ[/cyan] 日期筛选：{sd.strftime('%Y-%m-%d')} ~ {ed.strftime('%Y-%m-%d')}")

    filtered_records = records
    if date_range:
        start, end = date_range
        filtered_records = [
            r for r in records
            if r.practice_date and start <= r.practice_date <= end
        ]
        console.print(f"[cyan]ℹ[/cyan] 日期范围内的音频：{len(filtered_records)} 个（共 {len(records)} 个）")

    changed = 0
    if comment:
        for r in filtered_records:
            if r.comment:
                r.comment = f"{r.comment}_{comment}"
            else:
                r.comment = comment
            changed += 1
        console.print(f"[cyan]ℹ[/cyan] 已追加评语标签：{comment}（{changed} 个）")

    if rating or passed is not None:
        for r in filtered_records:
            if rating:
                r.rating = rating
            if passed is not None:
                r.passed = passed
            r.graded_at = datetime.now()
        console.print(
            f"[cyan]ℹ[/cyan] 已应用批改"
            + (f" 评级={rating}" if rating else "")
            + (f" 通过={passed}" if passed is not None else "")
        )

    if save_grading and (comment or rating or passed is not None):
        collected = store.collect_from_records(filtered_records)
        saved_path = store.save()
        console.print(f"[cyan]ℹ[/cyan] 批改记录已保存到 {saved_path}（共 {collected} 条）")

    op_log = OperationLogBuilder()
    splitter = Splitter(
        output_dir=output,
        copy=not move,
        date_range=date_range,
        operation_log=op_log,
    )

    if mode == "student":
        def on_progress(idx, total, student):
            klass = f" ({student.klass})" if student.klass else ""
            console.print(f"  [{idx}/{total}] 处理 {student.name}{klass}")

        result = splitter.split_by_student(records, on_progress=on_progress)
        console.print(f"\n[green]✓[/green] 完成：已按学生分割 {len(result)} 组到 {output}")

    elif mode == "class":
        def on_progress(idx, total, klass):
            console.print(f"  [{idx}/{total}] 处理 {klass}")

        result = splitter.split_by_class(records, on_progress=on_progress)
        console.print(f"\n[green]✓[/green] 完成：已按班级分割 {len(result)} 组到 {output}")

    elif mode == "pack":
        def on_progress(idx, total, student):
            console.print(f"  [{idx}/{total}] 打包 {student.name}")

        archives_with_records = splitter.pack_by_student(records, on_progress=on_progress)
        archive_paths = [a[0] for a in archives_with_records]
        console.print(f"\n[green]✓[/green] 完成：已生成 {len(archive_paths)} 个 zip 包到 {output}")
        for a in archive_paths:
            console.print(f"  - {a.name}")

        if archives_with_records:
            md_idx = splitter.write_pack_index(archives_with_records, fmt="markdown")
            csv_idx = splitter.write_pack_index(archives_with_records, fmt="csv")
            console.print(f"\n[cyan]ℹ[/cyan] 作业索引已生成：")
            console.print(f"  - {md_idx}")
            console.print(f"  - {csv_idx}")

    log_dir = Path(log_output) if log_output else Path(output)
    log_path = op_log.write_csv(log_dir, filename=f"split_{mode}_operation_log.csv")
    console.print(f"[cyan]ℹ[/cyan] 操作清单已保存：{log_path}")


def main() -> None:
    cli(obj={})


if __name__ == "__main__":
    main()
