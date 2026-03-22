---
name: fastcode
description: Code commit review skill using RAG and tree-sitter. Use when: "review this commit", "analyze this change", "check commit impact", "find code", "understand this repository". Supports Python, JS/TS, C/C++, Java, Go, Rust, C#.
---

# FastCode - Commit 检视 Skill

## 快速开始

### 调用方式

```python
import sys, os

# 获取 scripts 目录路径（SKILL.md 所在目录的下一级）
skill_dir = "/path/to/fastcode"  # 替换为实际的 SKILL.md 所在目录
scripts_dir = os.path.join(skill_dir, "scripts")
sys.path.insert(0, scripts_dir)

from reviewer import review_commit

report_path = review_commit(
    question="检视这笔 commit",
    commit_hash="abc1234",
    repo_path="/path/to/repo"
)
```

reviewer.py 会自动加载 `.env` 并设置模型缓存路径。

### 工作流程

```
load_and_index(repo_path)  ← 第一步
    ↓
review_commit(question, commit_hash)  ← 生成检视报告
```

---

## 配置

在 `fastcode/.env` 中配置：

```bash
LLM_API_KEY=sk-your-key
LLM_PROVIDER=openai  # 或 anthropic
LLM_MODEL=gpt-4
```

### 默认路径

| 类型 | 位置 |
|------|------|
| 模型缓存 | `{skill_dir}/data/model/` |
| 仓库索引 | `{repo}/.fastcode_index/` |

---

## 详细文档

- [API 参考](references/api.md) - 方法说明、参数详解
- [使用示例](references/examples.md) - 完整代码示例
- [Prompt 模板](references/prompts.md) - LLM prompt 配置
