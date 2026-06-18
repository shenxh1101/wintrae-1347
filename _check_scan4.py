import subprocess, json
r = subprocess.run(
    ['mpo', 'scan', '-d', './test_data', '--class-name', '钢琴一班', '--class-name', '钢琴二班', '--no-load-grading', '--json'],
    capture_output=True, encoding='utf-8'
)
d = json.loads(r.stdout)
print(f'Total: {len(d)}')
students = {}
for rec in d:
    key = (rec.get('class'), rec.get('student'))
    if key not in students:
        students[key] = []
    students[key].append(rec['file'])
print(f'Unique (class, student) pairs: {len(students)}')
for k, v in sorted(students.items()):
    print(f'  {k}: {len(v)} files, first: {v[0]}')

# 检查 StudentInfo 里的 student_id 是否被正确识别
from pathlib import Path
from mpo.scanner import AudioScanner
scanner = AudioScanner(class_names=["钢琴一班", "钢琴二班"])
result = scanner.scan_directory(Path('test_data'))
print(f'\nDirect scan - student_id:')
seen = {}
for rec in result.records:
    if rec.student:
        key = (rec.student.klass, rec.student.name, rec.student.student_id)
        if key not in seen:
            seen[key] = 0
        seen[key] += 1
for k, v in sorted(seen.items()):
    print(f'  {k}: {v} files')
