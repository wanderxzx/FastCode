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
    commit_review,
    get_commits,
    reindex
)

# 1. 加载仓库
load_and_index("/path/to/repo")

# 2. Commit检视（返回标准化报告）
commits = get_commits(max_count=10)
result = commit_review(commits["commits"][0]["short_hash"])
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
| `commit_review(commit_hash)` | ⭐ Commit检视，返回标准化报告格式 |
| `review_commit(question, commit_hash)` | 自定义问题的Commit检视 |
| `get_commits(max_count)` | 获取提交历史 |
| `get_commit_diff(commit_hash)` | 获取变更内容 |

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
