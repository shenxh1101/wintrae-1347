import json
from pathlib import Path

print("=== 1. 班级统计（验证0提交班级） ===")
with open('test_report/report.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
progress = d['progress']
print(f"总班级数: {progress['total_classes']}")
for klass, stats in sorted(progress['class_stats'].items()):
    print(f"  {klass}: 提交{stats['student_count']}人, 应提交{stats['expected_count']}人, "
          f"缺交{stats['missing_count']}人, 完成率{stats['completion_rate']}%, "
          f"录音{stats['total_records']}个")

print(f"\n缺交总人数: {len(progress['missing_students'])}")
for m in progress['missing_students']:
    print(f"  {m['klass']} - {m['name']} ({m.get('student_id','-')})")

print("\n=== 2. 趋势文件 ===")
for p in sorted(Path('test_report').glob('trend_*.csv')):
    print(f"  {p.name}")

print("\n=== 3. Markdown 中的趋势章节 ===")
with open('test_report/progress_report.md', 'r', encoding='utf-8') as f:
    md = f.read()
trend_sections = [l for l in md.split('\n') if l.startswith('## 按')]
print(f"  找到 {len(trend_sections)} 个趋势章节:")
for s in trend_sections:
    print(f"    {s}")

print("\n=== 4. 周趋势 CSV ===")
with open('test_report/trend_summary_week.csv', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()
    for i, line in enumerate(lines[:8]):
        print(f"  {line.strip()}")

print("\n=== 5. 月趋势 CSV ===")
with open('test_report/trend_summary_month.csv', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()
    for i, line in enumerate(lines[:8]):
        print(f"  {line.strip()}")

print("\n=== 6. JSON 中的 trends ===")
trends = d.get('trends', [])
print(f"  趋势数据个数: {len(trends)}")
for t in trends:
    print(f"    - {t['granularity']}: {len(t['periods'])} 个周期")
