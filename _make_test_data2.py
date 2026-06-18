from pathlib import Path
import wave
import os
from datetime import datetime

def create_wav(path, duration_seconds=60):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        nframes = int(44100 * duration_seconds)
        w.writeframes(b'\x00\x00' * nframes)

base = Path('test_data')
if base.exists():
    import shutil
    shutil.rmtree(base)

# 钢琴一班：张三(S001)、张三(S002)、李四(S003) - 同名同班不同学号
# 钢琴二班：张三(S004)、王五(S005)
classes = {
    "钢琴一班": [
        ("张三", "S001", ["练习曲", "奏鸣曲"]),
        ("张三", "S002", ["练习曲", "奏鸣曲"]),
        ("李四", "S003", ["练习曲", "奏鸣曲"]),
    ],
    "钢琴二班": [
        ("张三", "S004", ["练习曲", "奏鸣曲"]),
        ("王五", "S005", ["练习曲", "奏鸣曲"]),
    ],
    "钢琴三班": [
        ("赵六", "S006", []),
        ("钱七", "S007", []),
    ],
}

# 两个日期（跨两周）
dates = [datetime(2025, 6, 15), datetime(2025, 6, 16)]

all_students = []

for klass, students in classes.items():
    for name, sid, pieces in students:
        all_students.append((klass, name, sid))
        for date in dates:
            for piece in pieces:
                # 目录名带学号，文件名是标准的：日期_姓名_曲目.wav
                dir_name = f"{name}_{sid}"
                fname = f"{date.strftime('%Y-%m-%d')}_{name}_{piece}.wav"
                fpath = base / klass / dir_name / fname
                # 每个文件时长不同避免 MD5 相同
                base_dur = 60 if "练习曲" in piece else 90
                import hashlib
                seed = int(hashlib.md5(f"{sid}_{date}_{piece}".encode()).hexdigest(), 16) % 30
                dur = base_dur + seed
                create_wav(fpath, dur)

# 写学生名单（带学号）
with open("students_with_id.csv", "w", encoding="utf-8") as f:
    for klass, name, sid in all_students:
        f.write(f"{klass},{name},{sid}\n")

print("Test data created:")
for root, _, files in os.walk(base):
    for f in files:
        print(f"  {os.path.join(root, f)}")
print("\nStudents list (students_with_id.csv):")
for s in all_students:
    print(f"  {s}")
