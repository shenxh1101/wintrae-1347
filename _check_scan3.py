import subprocess
r = subprocess.run(
    ['mpo', 'scan', '-d', './test_data', '--class-name', '钢琴一班', '--class-name', '钢琴二班', '--no-load-grading', '--json'],
    capture_output=True, encoding='utf-8'
)
print("RC:", r.returncode)
print("STDOUT:", repr(r.stdout[:500]))
print("STDERR:", repr(r.stderr[:500]))
