import json
from pathlib import Path

print("=== 验证日期范围批改（需求2） ===")
with open('test_report/report.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

trends = d.get('trends', [])
week_trend = [t for t in trends if t['granularity'] == 'week'][0]

print("周趋势各周期已批改数:")
for period in week_trend['period_order']:
    pd = week_trend['periods'][period]
    print(f"  {period}: 总已批改={pd['graded_count']}")
    for klass, cd in pd['class_data'].items():
        print(f"    {klass}: {cd['graded_count']} 份已批改")

print("\n=== 验证 grade-export 按时间排序（需求4） ===")
import subprocess, os
env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'
r = subprocess.run(
    ['mpo', 'grade-export', '--klass', '钢琴一班', '-o', './test_output'],
    capture_output=True, encoding='utf-8', env=env
)
print(r.stdout.strip())

with open('test_output/grading_history_钢琴一班.csv', 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()
print(f"\n钢琴一班批改历史（共 {len(lines)-1} 条）:")
print(f"  {'练习日期':<12} {'学生':<6} {'学号':<6} {'评语'}")
for line in lines[1:]:
    parts = line.strip().split(',')
    if len(parts) >= 6:
        print(f"  {parts[2]:<12} {parts[1]:<6} {parts[3]:<6} {parts[4]}")

print("\n=== 验证 JSON 导出 ===")
r = subprocess.run(
    ['mpo', 'grade-export', '--klass', '钢琴一班', '--format', 'json', '-o', './test_output'],
    capture_output=True, encoding='utf-8', env=env
)
with open('test_output/grading_history_钢琴一班.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f"导出 {data['count']} 条记录")
dates = [r['practice_date'] for r in data['records']]
print(f"日期顺序: {dates}")
print(f"时间排序正确: {dates == sorted(dates)}")
