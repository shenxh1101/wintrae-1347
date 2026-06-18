# 练琴音频整理工具 (Music Practice Organizer)

为音乐教师设计的命令行工具，用于批量整理学生提交的练琴录音。

## 功能特性

- **scan 扫描**：递归扫描音频文件夹，自动识别学生姓名、班级、曲目、日期和时长
- **rename 重命名**：按自定义模板统一重命名文件，自动按班级/学生归档到子目录
- **check 检查**：检测缺交名单、重复文件（基于 MD5）、无法识别的学生/曲目、时长过短的录音
- **report 报告**：生成班级练习清单、学生练习进度报告（CSV / JSON / Markdown）
- **split 分割**：按日期范围抽取、追加评语标签、按学生或班级分目录、打包为 zip

## 安装

```bash
pip install -e .
# 或
pip install -r requirements.txt
```

安装后可直接使用命令 `mpo`。

## 快速开始

```bash
# 1. 扫描目录预览识别结果
mpo scan -d ./录音

# 2. 预览重命名效果
mpo rename -d ./录音 -n

# 3. 实际执行重命名
mpo rename -d ./录音 -o ./整理后

# 4. 检查提交情况（配合学生名单）
mpo check -d ./整理后 --students-file students.csv

# 5. 生成进度报告
mpo report -d ./整理后 -o ./reports

# 6. 按学生打包提交材料
mpo split -d ./整理后 -o ./打包 --mode pack
```

## 命令详解

### 通用选项

| 选项 | 说明 |
|------|------|
| `-c, --config` | 指定 YAML 配置文件路径 |
| `-v, --verbose` | 详细输出模式 |
| `-d, --dir` | 要处理的目录（所有命令必填） |
| `--no-recursive` | 不递归扫描子目录 |
| `--ignore` | 忽略正则模式，可重复使用 |
| `--class-name` | 班级名称，可重复使用，用于从路径识别班级 |

### scan - 扫描识别

```bash
mpo scan -d ./录音 [--json]
```

输出表格或 JSON，包含：学生、班级、曲目、日期、时长。

### rename - 批量重命名

```bash
mpo rename -d ./录音 \
  -t "{date}_{class}_{student}_{piece}" \
  -o ./整理后 \
  [--no-organize-class] [--no-organize-student] \
  [--overwrite] [-n/--dry-run]
```

**命名模板占位符**：

| 变量 | 说明 |
|------|------|
| `{date}` | 练习日期 (YYYY-MM-DD) |
| `{class}` | 班级 |
| `{student}` | 学生姓名 |
| `{piece}` | 曲目名称 |
| `{duration}` | 时长 (HH-MM-SS) |
| `{comment}` | 评语标签（带下划线前缀） |
| `{ext}` | 扩展名（含点号） |
| `{original}` | 原文件名 |

### check - 检查审核

```bash
mpo check -d ./整理后 \
  --students-file students.csv \
  --min-duration 10 \
  --start-date 2025-06-01 --end-date 2025-06-30
```

学生名单格式：`班级,姓名,学号`（学号可选），TXT 或 CSV。

### report - 生成报告

```bash
mpo report -d ./整理后 \
  -o ./reports \
  --group-by class \
  --format all
```

生成文件：
- `practice_list.csv` - 班级练习清单
- `report.json` - 完整数据（含统计）
- `progress_report.md` - Markdown 格式进度报告

### split - 抽取/分割/打包

```bash
# 按日期抽取并分学生目录
mpo split -d ./录音 -o ./week1 \
  --start-date 2025-06-09 --end-date 2025-06-15 \
  --mode student

# 追加评语标签
mpo split -d ./录音 -o ./已批改 --comment 已批改

# 按学生打包成 zip
mpo split -d ./录音 -o ./打包 --mode pack
```

## 配置文件

参考 `config.example.yaml`：

```yaml
template: "{date}_{class}_{student}_{piece}{comment}"
output_dir: null
ignore_patterns:
  - "^\\."
  - "__MACOSX"
class_names:
  - "钢琴一班"
  - "钢琴二班"
min_duration_seconds: 10
organize_by_class: true
organize_by_student: true
```

## 支持的音频格式

mp3, wav, m4a, flac, aac, ogg, wma, opus, aiff, aif

## 项目结构

```
src/mpo/
├── __init__.py      # 包入口
├── cli.py           # CLI 命令定义
├── models.py        # 数据模型
├── scanner.py       # 目录扫描与信息识别
├── namer.py         # 命名规则引擎
├── checker.py       # 缺交/重复/时长检查
├── reporter.py      # 报告生成 (CSV/JSON/MD)
├── splitter.py      # 按日期/学生分割与打包
└── config.py        # 配置文件加载
```
