import json
with open('test_report/report.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
trend = d.get('trend', {})
print('Trend structure:', json.dumps(trend, indent=2, ensure_ascii=False)[:1000])
