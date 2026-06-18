import subprocess, json
r = subprocess.run(
    ['mpo', 'scan', '-d', './test_data', '--class-name', '钢琴一班', '--class-name', '钢琴二班', '--no-load-grading', '--json'],
    capture_output=True, encoding='utf-8'
)
print("STDERR:", r.stderr)
d = json.loads(r.stdout)
print(f'Total: {len(d)}')
unknown = 0
for rec in d:
    if not rec['student']:
        unknown += 1
        print(f"  [unknown] {rec['file']}")
print(f'Unknown: {unknown}')
students = set()
for rec in d:
    if rec['student']:
        students.add((rec['class'], rec['student']))
print(f'Unique students: {len(students)}')
for s in sorted(students):
    print(f'  {s}')
