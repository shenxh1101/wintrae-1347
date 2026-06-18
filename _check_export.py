import json
with open('test_output/grading_history_钢琴一班.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
print(f'Count: {d["count"]}')
for r in d['records']:
    print(f'  {r["klass"]} {r["student"]} ({r.get("student_id","-")}) {r["practice_date"]} {r["piece"]}')
