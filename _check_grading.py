import json
with open('grading_records.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f'Type: {type(data).__name__}')
if isinstance(data, dict) and 'records' in data:
    records = data['records']
    if isinstance(records, dict):
        records = list(records.values())
    print(f'Version: {data.get("version")}, Updated at: {data.get("updated_at")}')
elif isinstance(data, dict):
    records = list(data.values())
else:
    records = data
print(f'Total grading records: {len(records)}')
print('\nSample records (first 2):')
for i, r in enumerate(records[:2]):
    print(f'  {i+1}. class={r.get("klass")}, student={r.get("student")}, student_id={r.get("student_id")}, date={r.get("practice_date")}, comment={r.get("comment")}')

dates = set(r.get('practice_date') for r in records)
print(f'\nAll practice dates in grading records: {sorted(dates)}')

from collections import Counter
keys = Counter()
for r in records:
    key = (r.get('klass'), r.get('student'), r.get('student_id'))
    keys[key] += 1
print('\nRecords per student:')
for k, v in sorted(keys.items()):
    print(f'  {k}: {v}')
