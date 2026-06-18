import json
with open('_scan.json', encoding='utf-8') as f:
    d = json.load(f)
print(f'Total: {len(d)}')
unknown = 0
for r in d:
    if not r['student']:
        unknown += 1
        print(f"  [unknown] {r['file']}")
print(f'Unknown: {unknown}')
students = set()
for r in d:
    if r['student']:
        students.add((r['class'], r['student']))
print(f'Unique students: {len(students)}')
for s in sorted(students):
    print(f'  {s}')
