import shutil
from pathlib import Path
import subprocess
import json
import os

env = os.environ.copy()
env['PYTHONIOENCODING'] = 'utf-8'

# 1. 备份 test_data
if Path('test_data_backup').exists():
    shutil.rmtree('test_data_backup')
shutil.copytree('test_data', 'test_data_backup')

# 2. 改名模拟换目录
if Path('test_data_new').exists():
    shutil.rmtree('test_data_new')
Path('test_data').rename('test_data_new')

# 3. 重新扫描新目录，看批改记录是否被正确加载
print("=== 重新扫描新目录 test_data_new ===")
r = subprocess.run(
    ['mpo', 'scan', '-d', './test_data_new', '--class-name', '钢琴一班', '--class-name', '钢琴二班', '--json'],
    capture_output=True, encoding='utf-8', env=env
)
d = json.loads(r.stdout)
graded = [x for x in d if x.get('comment') or x.get('rating') or x.get('passed') is not None]
print(f"Total: {len(d)}, Graded: {len(graded)}")
for x in graded[:3]:
    print(f"  {x['file']}: comment={x['comment']}, rating={x['rating']}, passed={x['passed']}")

# 4. 验证 report 也能正确识别
print("\n=== Report 测试 ===")
if Path('test_report2').exists():
    shutil.rmtree('test_report2')
r = subprocess.run(
    ['mpo', 'report', '-d', './test_data_new', '--class-name', '钢琴一班', '--class-name', '钢琴二班',
     '--students-file', 'students_with_id.csv', '-o', './test_report2'],
    capture_output=True, encoding='utf-8', env=env
)
print(r.stdout[-200:])

# 5. 恢复原目录名
if Path('test_data').exists():
    shutil.rmtree('test_data')
Path('test_data_new').rename('test_data')
shutil.rmtree('test_data_backup')
print("\n恢复原目录名完成")
