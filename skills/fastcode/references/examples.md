# Examples

## Finding and Reviewing Commits

### Example 1: List and Select Commits

```python
from reviewer import load_and_index

# Load repository
reviewer = load_and_index("/path/to/repo")

# List recent commits
print("Recent commits:")
for c in reviewer.get_commits(10):
    print(f"  {c['short_hash']} - {c['summary']}")

# Output:
#   abc1234 - feat: add user authentication
#   def5678 - fix: resolve parser bug
#   ghi9012 - refactor: simplify utils
```

### Example 2: Find Commit by Keyword

```python
# Find commit with specific keyword
commits = reviewer.get_commits(100)
auth_commit = next(
    (c for c in commits if "auth" in c['message'].lower()),
    None
)

if auth_commit:
    print(f"Found: {auth_commit['short_hash']}")
    report = reviewer.review_commit(
        question="分析这个 commit 的安全性",
        commit_hash=auth_commit['short_hash']
    )
```

### Example 3: Review Latest Commit

```python
# Get latest commit
commits = reviewer.get_commits(1)
latest = commits[0]

# Review it
report = reviewer.review_commit(
    question="检视这笔 commit",
    commit_hash=latest['short_hash'],
    output_dir="./reports"
)
print(f"Report: {report}")
```

### Example 4: Review Multiple Commits

```python
# Batch review recent commits
commits = reviewer.get_commits(5)

for commit in commits:
    print(f"Reviewing {commit['short_hash']}...")
    report = reviewer.review_commit(
        question="简短总结这笔 commit",
        commit_hash=commit['short_hash'],
        output_dir="./reports"
    )
```

## Using Existing Index

### Example 5: Load with Existing Index (自动)

```python
from reviewer import FastCodeReviewer

# load_and_index 会自动检测已存在的索引并加载
reviewer = FastCodeReviewer()
reviewer.load_and_index(
    "/path/to/repo",
    index_dir="/path/to/repo/.fastcode_index"  # 可选，不指定则使用默认路径
)

# 检查是否加载成功
if reviewer.vector_store.get_count() > 0:
    print(f"Loaded {reviewer.vector_store.get_count()} indexed elements")
```

### Example 6: Force Rebuild Index

```python
from reviewer import FastCodeReviewer

reviewer = FastCodeReviewer()

# 删除旧索引后重新加载，会自动重建
import shutil
import os
index_dir = "/path/to/repo/.fastcode_index"
if os.path.exists(index_dir):
    shutil.rmtree(index_dir)

reviewer.load_and_index("/path/to/repo")

# 或者直接调用 reindex()
# reviewer.reindex()
```

## LLM Configuration

### Example 7: Use Claude

```python
from reviewer import SkillConfig, FastCodeReviewer

SkillConfig.set_env(
    api_key="sk-ant-...",
    provider="anthropic",
    model="claude-3-sonnet-20240229"
)

reviewer = FastCodeReviewer()
reviewer.load_and_index("/path/to/repo")
```

### Example 8: Use Proxy

```python
from reviewer import SkillConfig

SkillConfig.set_env(
    api_key="your-key",
    provider="openai",
    model="gpt-4",
    base_url="https://your-proxy.com/v1"  # Optional
)
```

### Example 9: Custom Config

```python
from reviewer import FastCodeReviewer, SkillConfig

config = SkillConfig().to_dict()
config["generation"]["temperature"] = 0.2
config["generation"]["max_tokens"] = 5000
config["retrieval"]["max_results"] = 5

reviewer = FastCodeReviewer(config)
```

## Report Format

Generated report structure:

```markdown
# Commit 检视报告

## 基本信息
- **Commit**: `abc1234`
- **Message**: feat: add feature
- **Author**: John
- **Date**: 2026-03-22

## 检视结果
### 一、功能分析
...

### 二、影响分析
（统一用表格展示调用者/被调用者）

### 三、检视意见
- 优点: ...
- 问题: ...
- 建议: ...

---
*由 FastCode Commit Review Skill 生成*
```
