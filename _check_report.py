import json
with open('test_report/report.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
print('Student stats keys:', list(d['progress']['student_stats'].keys()))
print('Trend periods:', d.get('trend', {}).get('period_order', []))
for k, v in d['progress']['student_stats'].items():
    sid = v.get('student_id', '-')
    print(f'  {k}: {v["name"]} ({sid}) - {v["count"]} recordings')

# 检查趋势数据
if 'trend' in d:
    print('\nTrend data present:', list(d['trend'].keys()))
    for period in d['trend'].get('period_order', []):
        print(f'  {period}:')
        period_data = d['trend']['periods'].get(period, {})
        for klass, stats in period_data.get('by_class', {}).items():
            print(f'    {klass}: submitted={stats["submitted_count"]}, expected={stats["expected_count"]}, graded={stats["graded_count"]}')
