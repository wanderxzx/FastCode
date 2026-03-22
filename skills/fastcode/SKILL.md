---
name: fastcode
description: FastCode代码理解和Commit检视Skill。使用场景：(1) 分析仓库代码结构 (2) 理解模块功能 (3) Commit代码检视 (4) 代码问题排查。提供load、index、reindex、query、commit_review等核心函数。
---

# FastCode Skill

基于FastCode的代码理解和Commit检视能力。

## 环境配置

### FASTCODE_PATH 环境变量

Skill 通过 `FASTCODE_PATH` 环境变量定位 FastCode 本体：

```bash
export FASTCODE_PATH="/path/to/your/fastcode"
```

## 快速开始

```python
import sys
from pathlib import Path

script_dir = Path(__file__).parent / "scripts"
sys.path.insert(0, str(script_dir))

from fastcode_skill import (
    load_and_index, 
    review_commit,
    get_commits,
    reindex
)

# 1. 加载仓库
load_and_index("/path/to/repo")

# 2. Commit检视（返回标准化报告）
commits = get_commits(max_count=10)
result = review_commit("帮我检视一下这个commit", commits["commits"][0]["short_hash"])
print(result["answer"])
```

## 重要：代码修改后必须reindex

```python
# 代码修改后，重新索引才能获取准确的Call Graph分析
reindex()
```

## API参考

### 仓库管理

| 函数 | 说明 |
|------|------|
| `load_repository(source)` | 加载仓库（不索引） |
| `index_repository(force)` | 索引仓库 |
| `reindex()` | ⚠️ 重新索引（重建Call Graph） |
| `load_and_index(source, force)` | 加载并索引 |

### Commit检视

| 函数 | 说明 |
|------|------|
| `review_commit(question, commit_hash, output_dir)` | ⭐ Commit检视，返回标准化报告格式 |
| `get_commits(max_count)` | 获取提交历史 |
| `get_commit_diff(commit_hash)` | 获取变更内容 |

**review_commit 返回值**:
- `answer`: 检视报告文本
- `report_file`: 📄 报告文件路径（自动生成markdown文件）

**报告文件**: 检视结果会自动保存为 `commit_review_{hash}_{timestamp}.md`，方便分享和存档。

### 查询

| 函数 | 说明 |
|------|------|
| `query(question, session_id, enable_multi_turn, commit_hash)` | 代码查询，直接返回FastCode结果 |

### 系统

| 函数 | 说明 |
|------|------|
| `get_status()` | 获取系统状态 |
| `health_check()` | 健康检查 |

## 配置指南

详见 [references/config.md](references/config.md)
