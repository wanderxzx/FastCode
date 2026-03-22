"""
Prompt Builder - Build prompts for commit review
Simplified from FastCode's answer_generator.py
"""

from typing import Dict, List, Any, Optional


SYSTEM_PROMPT = """You are a helpful AI assistant specialized in code understanding and explanation. 
Your task is to answer questions about code repositories based on the relevant code snippets provided.

Guidelines:
1. Focus primarily on answering the question itself.
2. Provide clear, accurate, and concise answers.
3. Reference specific code snippets when relevant.
4. Include repository names, file paths, and line numbers when discussing specific code.
5. If the provided context doesn't contain enough information, say so.
6. **IMPORTANT: Always respond in the same language as the user's question.**"""


COMMIT_REVIEW_INSTRUCTION = """
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
"""


class PromptBuilder:
    """Build prompts for commit review"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    def build(self, query: str, context: str, 
              query_info: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Build complete prompt for commit review
        
        Args:
            query: User question
            context: Relevant code context
            query_info: Optional query information including commit_info
        
        Returns:
            Dict with 'system' and 'user' prompts
        """
        user_parts = []
        
        # Add current query
        user_parts.append(f"**Current Question**: {query}")
        
        # Add commit context if available
        if query_info and "commit_info" in query_info:
            commit_info = query_info["commit_info"]
            user_parts.append("\n**Commit Information**:\n")
            user_parts.append(f"Commit: `{commit_info.get('short_hash', 'unknown')}`\n")
            
            # Add commit message (first line only)
            message = commit_info.get('message', '') or commit_info.get('summary', '')
            if message:
                first_line = message.split('\n')[0][:200]
                user_parts.append(f"Message: {first_line}\n\n")
            
            # Add code changes (diff)
            if commit_info.get('file_diffs'):
                user_parts.append("**Code Changes**:\n")
                file_count = 0
                for file_path, file_info in commit_info['file_diffs'].items():
                    if file_count >= 5:
                        user_parts.append("...(more files omitted)\n")
                        break
                    
                    diff_text = file_info.get('diff', '')
                    if diff_text:
                        diff_lines = diff_text.split('\n')
                        key_lines = []
                        for line in diff_lines[:30]:
                            if line.startswith('@@'):
                                key_lines.append(line)
                            elif line.startswith('+') and not line.startswith('+++'):
                                key_lines.append(line)
                            elif line.startswith('-') and not line.startswith('---'):
                                key_lines.append(line)
                            elif line.startswith('diff --git a/'):
                                key_lines.append(line)
                        
                        if key_lines:
                            user_parts.append(f"\n**{file_path}**:\n")
                            user_parts.append('\n'.join(key_lines[:20]))
                            if len(diff_lines) > 20:
                                user_parts.append("\n...(truncated)")
                            user_parts.append("\n")
                        file_count += 1
                user_parts.append("\n")
            
            # Add call graph analysis if available
            if commit_info.get('call_graph_analysis'):
                call_graph = commit_info['call_graph_analysis']
                user_parts.append("**影响范围分析**:\n")
                user_parts.append(f"- **受影响函数总数**: {call_graph.get('total_modified_functions', 0)}\n")
                user_parts.append(f"- **调用者（使用这些函数的模块）**: {call_graph.get('total_callers', 0)}个\n")
                user_parts.append(f"- **被调用者（这些函数依赖的模块）**: {call_graph.get('total_callees', 0)}个\n\n")
                
                # Add file-level details
                if call_graph.get('file_details'):
                    user_parts.append("**按文件分类**:\n")
                    for file_path, file_info in call_graph['file_details'].items():
                        modified_count = file_info.get('modified_count', 0)
                        modified_functions = file_info.get('modified_functions', [])
                        user_parts.append(f"#### {file_path}\n")
                        user_parts.append(f"- **修改函数数**: {modified_count}\n")
                        if modified_functions:
                            user_parts.append(f"- **修改的函数**: {', '.join(modified_functions)}\n")
                        user_parts.append("\n")
                
                # Add specific caller/callee names
                callers_map = call_graph.get('callers', {})
                callees_map = call_graph.get('callees', {})
                
                if callers_map or callees_map:
                    user_parts.append("**具体调用关系**:\n")
                    
                    if callers_map:
                        user_parts.append("### 📤 调用者\n")
                        for func_name, caller_list in callers_map.items():
                            if caller_list:
                                user_parts.append(f"- **{func_name}** 被以下函数调用:\n")
                                for caller in caller_list[:10]:
                                    user_parts.append(f"  - `{caller}`\n")
                                if len(caller_list) > 10:
                                    user_parts.append(f"  - ... 还有 {len(caller_list) - 10} 个\n")
                                user_parts.append("\n")
                    
                    if callees_map:
                        user_parts.append("### 📥 被调用者\n")
                        for func_name, callee_list in callees_map.items():
                            if callee_list:
                                user_parts.append(f"- **{func_name}** 调用了以下函数:\n")
                                for callee in callee_list[:10]:
                                    user_parts.append(f"  - `{callee}`\n")
                                if len(callee_list) > 10:
                                    user_parts.append(f"  - ... 还有 {len(callee_list) - 10} 个\n")
                                user_parts.append("\n")
                    
                    user_parts.append("\n")
        
        # Add code context
        user_parts.append("**Relevant Code Context**:\n")
        user_parts.append(context)
        
        # Add instruction
        instruction = "\n**Instructions**: Please answer the question using the code snippets above only if they are relevant."
        
        # Add commit review instruction if applicable
        if query_info and "commit_info" in query_info:
            instruction += COMMIT_REVIEW_INSTRUCTION
        
        user_parts.append(instruction)
        
        return {
            "system": SYSTEM_PROMPT,
            "user": "\n".join(user_parts)
        }
