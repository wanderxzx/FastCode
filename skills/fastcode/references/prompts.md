# Prompt Templates

## System Prompt

```text
You are a helpful AI assistant specialized in code understanding and explanation. 
Your task is to answer questions about code repositories based on the relevant code snippets provided.

Guidelines:
1. Focus primarily on answering the question itself.
2. Provide clear, accurate, and concise answers.
3. Reference specific code snippets when relevant.
4. Include repository names, file paths, and line numbers when discussing specific code.
5. If the provided context doesn't contain enough information, say so.
6. **IMPORTANT: Always respond in the same language as the user's question.**
```

## Commit Review Prompt

```text
**📋 Commit 检视任务**：

请从以下三个维度对这笔 commit 进行检视：

## 一、功能分析
这笔 commit 做了什么？实现了什么功能？解决了什么问题？

## 二、影响分析
**哪些函数会调用到这次修改的代码？**（调用者）

请用表格格式列出，列：调用者模块 | 被调用的函数 | 影响说明
- 列出所有调用了本次修改函数的外部代码
- 说明调用关系和影响范围

**这次修改依赖于哪些函数？**（被调用者）

请用表格格式列出，列：被依赖的函数/模块 | 来源文件 | 风险说明
- 列出本次修改所依赖的外部函数或模块
- 说明依赖关系和潜在风险点

## 三、检视意见
**优点**：这笔修改有哪些做得好的地方？

**问题**：这笔修改有哪些潜在问题或风险？
- 代码质量问题
- 逻辑漏洞
- 安全风险
- 性能影响
- 兼容性问题等

**建议**：针对上述问题，有什么具体的改进建议？

**注意**：不需要报告修改了多少文件、多少行，重点关注功能、影响和检视意见。
```

## Full Commit Review Prompt (with context)

```text
**Current Question**: {question}

**Commit Information**:
- Commit: `{short_hash}`
- Message: {message}

**Code Changes**:
{file_diffs}

**影响范围分析**:
- **受影响函数总数**: {total_modified_functions}
- **调用者（使用这些函数的模块）**: {total_callers}个
- **被调用者（这些函数依赖的模块）**: {total_callees}个

**具体调用关系**:
### 📤 调用者
{callers_list}

### 📥 被调用者
{callees_list}

**Relevant Code Context**:
{context}

**Instructions**: 
请从功能分析、影响分析、检视意见三个维度对这笔 commit 进行检视。
```

## Prompt Building (internal)

The `PromptBuilder` class constructs prompts:

```python
from skills.fastcode.scripts.prompt_builder import PromptBuilder

builder = PromptBuilder()

prompts = builder.build(
    query="检视这笔 commit",
    context="<relevant code>",
    query_info={
        "commit_info": {
            "short_hash": "abc1234",
            "message": "feat: add feature",
            "file_diffs": {...},
            "call_graph_analysis": {...}
        }
    }
)

# Returns:
# {
#   "system": "You are a helpful AI...",
#   "user": "**Current Question**: ..."
# }
```
