"""
FastCode Skill - 精简版

核心功能：
1. 环境配置检查和引导
2. 仓库加载和索引
3. 代码查询
4. Commit分析和检视
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

# ============================================================
# FastCode路径配置
# ============================================================

# 从环境变量获取FastCode路径，默认使用相对路径
FASTCODE_PATH = os.environ.get("FASTCODE_PATH", str(Path(__file__).parent.parent.parent / "fastcode"))
if FASTCODE_PATH and FASTCODE_PATH not in sys.path:
    sys.path.insert(0, FASTCODE_PATH)

# ============================================================
# 环境配置加载
# ============================================================

def _load_env():
    """加载.env配置文件"""
    possible_paths = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent / ".env",
        Path(FASTCODE_PATH).parent / ".env" if FASTCODE_PATH else None,
    ]
    possible_paths = [p for p in possible_paths if p]
    
    for env_path in possible_paths:
        if env_path.exists():
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
                return True
            except ImportError:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
                return True
    return False

_load_env()


# ============================================================
# 全局状态
# ============================================================

_fastcode = None

def _get_fastcode() -> Any:
    """获取FastCode实例"""
    global _fastcode
    if _fastcode is None:
        from fastcode import FastCode
        _fastcode = FastCode()
    return _fastcode


# ============================================================
# 配置检查
# ============================================================

def check_environment() -> Dict[str, Any]:
    """
    检查环境配置
    
    Returns:
        环境检查结果
    """
    from config import check_environment as _check
    return _check()


def print_environment_report() -> str:
    """打印环境检查报告"""
    from config import print_environment_report as _print
    from config import check_environment as _check
    return _print(_check())


def get_setup_instructions() -> Dict[str, Any]:
    """获取配置指南"""
    from config import get_setup_instructions as _get
    return _get()


# ============================================================
# 仓库管理 (参考web_app: load, index, load-and-index)
# ============================================================

def load_repository(
    source: str,
    is_url: Optional[bool] = None,
    copy_to_workspace: bool = False
) -> Dict[str, Any]:
    """
    加载仓库（不索引）
    
    Args:
        source: 仓库路径或GitHub URL
        is_url: 是否为URL
        copy_to_workspace: 是否复制到workspace
    """
    try:
        fc = _get_fastcode()
        fc.load_repository(source, is_url=is_url, copy_to_workspace=copy_to_workspace)
        return {
            "success": True,
            "repo_info": fc.repo_info
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def index_repository(force: bool = False) -> Dict[str, Any]:
    """
    索引仓库（参考web_app /api/index）
    
    Args:
        force: 是否强制重新索引（会重新构建Call Graph）
    
    Returns:
        索引结果
    """
    try:
        fc = _get_fastcode()
        if not fc.repo_loaded:
            return {"success": False, "error": "仓库未加载"}
        
        fc.index_repository(force=force)
        
        # 清除扫描缓存
        if hasattr(fc, 'vector_store'):
            fc.vector_store.invalidate_scan_cache()
        
        return {
            "success": True,
            "repo_info": fc.repo_info,
            "summary": fc.get_repository_summary()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def reindex() -> Dict[str, Any]:
    """
    重新索引仓库（强制重建索引和Call Graph）
    
    ⚠️ 重要：当代码修改后，必须调用此函数才能获取准确的Call Graph分析
    
    Returns:
        重新索引结果
    """
    try:
        fc = _get_fastcode()
        if not fc.repo_loaded:
            return {"success": False, "error": "仓库未加载，请先调用 load_repository()"}
        
        fc.index_repository(force=True)
        
        return {
            "success": True,
            "message": "仓库已重新索引，Call Graph已重建",
            "repo_info": fc.repo_info,
            "summary": fc.get_repository_summary()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def load_and_index(
    source: str,
    is_url: Optional[bool] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    加载并索引仓库（参考web_app /api/load-and-index）
    
    Args:
        source: 仓库路径或GitHub URL
        is_url: 是否为URL
        force: 强制重新索引
    
    Returns:
        FastCode原始结果
    """
    try:
        fc = _get_fastcode()
        fc.load_repository(source, is_url=is_url)
        fc.index_repository(force=force)
        
        return {
            "success": True,
            "repo_info": fc.repo_info,
            "summary": fc.get_repository_summary()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_repositories() -> Dict[str, Any]:
    """列出仓库"""
    try:
        fc = _get_fastcode()
        available = fc.vector_store.scan_available_indexes() if hasattr(fc, 'vector_store') else []
        loaded = fc.list_repositories() if hasattr(fc, 'list_repositories') else []
        
        return {
            "success": True,
            "available": available,
            "loaded": loaded,
            "current_repo": fc.repo_info.get("name") if fc.repo_info else None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# 代码查询 (参考web_app: /api/query)
# ============================================================

def query(
    question: str,
    session_id: Optional[str] = None,
    enable_multi_turn: bool = False,
    repo_filter: Optional[List[str]] = None,
    commit_hash: Optional[str] = None,
    use_agency_mode: bool = False
) -> Dict[str, Any]:
    """
    查询代码库（参考web_app /api/query）
    
    Args:
        question: 问题
        session_id: 会话ID
        enable_multi_turn: 启用多轮对话
        repo_filter: 仓库过滤
        commit_hash: Commit上下文
        use_agency_mode: 启用Agency模式
    
    Returns:
        FastCode原始结果，包含answer
    """
    try:
        fc = _get_fastcode()
        
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())[:8]
        
        result = fc.query(
            question=question,
            session_id=session_id,
            enable_multi_turn=enable_multi_turn,
            repo_filter=repo_filter,
            commit_hash=commit_hash,
            use_agency_mode=use_agency_mode
        )
        
        return result
    except Exception as e:
        return {"answer": f"Error: {str(e)}", "query": question, "error": str(e)}


# ============================================================
# Commit操作 (参考web_app: /api/commits, /api/commit/{hash})
# ============================================================

def get_commits(max_count: int = 50) -> Dict[str, Any]:
    """获取提交历史"""
    try:
        fc = _get_fastcode()
        commits = fc.get_commits(max_count=max_count)
        return {"success": True, "commits": commits, "count": len(commits)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_commit_diff(commit_hash: str) -> Dict[str, Any]:
    """获取Commit的代码变更"""
    try:
        fc = _get_fastcode()
        diff = fc.get_commit_diff(commit_hash)
        return diff
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# Commit检视报告 - 标准化格式
# ============================================================
def review_commit(
    question: str,
    commit_hash: str,
    use_agency_mode: bool = False,
    output_dir: str = None
) -> Dict[str, Any]:
    """
    Commit检视（参考web_app commit分析流程）
    
    Args:
        question: 分析问题
        commit_hash: Commit Hash
        use_agency_mode: 启用Agency模式
        output_dir: 报告输出目录（默认: workspace目录）
    
    Returns:
        FastCode原始分析结果，包含 report_file 字段（报告文件路径）
    """
    try:
        fc = _get_fastcode()
        
        # 获取 commit 基本信息
        commit_info = fc.get_commit_diff(commit_hash)
        # 只取第一行（subject），避免截断问题
        raw_msg = commit_info.get('message', '') if commit_info else ''
        commit_msg = raw_msg.split('\n')[0].strip()[:80] if raw_msg else ''
        commit_short = commit_info.get('short_hash', commit_hash) if commit_info else commit_hash
        
        # 执行查询
        result = fc.query(
            question=question,
            commit_hash=commit_hash,
            use_agency_mode=use_agency_mode
        )
        
        # 生成报告文件
        report_file = _generate_commit_review_report(
            commit_hash=commit_short,
            commit_msg=commit_msg,
            answer=result.get('answer', ''),
            output_dir=output_dir
        )
        
        # 添加报告文件路径到结果
        result['report_file'] = report_file
        
        return result
    except Exception as e:
        return {"answer": f"Error: {str(e)}", "query": question, "error": str(e)}


def _generate_commit_review_report(
    commit_hash: str,
    commit_msg: str,
    answer: str,
    output_dir: str = None
) -> str:
    """
    生成Commit检视报告文件
    
    Args:
        commit_hash: Commit短哈希
        commit_msg: Commit消息
        answer: 检视分析内容
        output_dir: 输出目录
    
    Returns:
        报告文件路径
    """
    import os
    from datetime import datetime
    
    # 确定输出目录
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'workspace')
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"commit_review_{commit_hash}_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)
    
    # 简化清理：移除开头的标题节（如果有）
    lines = answer.strip().split('\n')
    
    # 移除开头的报告标题和基本信息节
    skip_patterns = [
        '# Commit 检视报告', '## Commit 检视报告',
        '### 基本信息', '## 基本信息',
        '## Commit 信息', '# Commit ',
    ]
    
    start_idx = 0
    for i, line in enumerate(lines[:10]):
        stripped = line.strip()
        for pattern in skip_patterns:
            if stripped.startswith(pattern):
                start_idx = i + 1
                # 跳过空行
                while start_idx < len(lines) and not lines[start_idx].strip():
                    start_idx += 1
                break
        if start_idx > 0:
            break
    
    cleaned_lines = lines[start_idx:] if start_idx > 0 else lines
    
    # 清理连续空行
    result = []
    prev_empty = False
    for line in cleaned_lines:
        stripped = line.strip()
        if stripped == '':
            if not prev_empty:
                result.append(line)
            prev_empty = True
        else:
            result.append(line)
            prev_empty = False
    
    cleaned_answer = '\n'.join(result)
    
    # 生成报告内容
    report_content = f"""# Commit 检视报告

**Commit**: `{commit_hash}`  
**消息**: {commit_msg}  
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{cleaned_answer}

---

*报告由 FastCode Skill 自动生成*
"""
    
    # 写入文件
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    return filepath


# ============================================================
# 系统状态 (参考web_app: /api/status, /api/health)
# ============================================================

def get_status() -> Dict[str, Any]:
    """获取系统状态"""
    try:
        fc = _get_fastcode()
        return {
            "success": True,
            "repo_loaded": fc.repo_loaded,
            "repo_indexed": fc.repo_indexed,
            "repo_info": fc.repo_info
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def health_check() -> Dict[str, Any]:
    """健康检查"""
    try:
        fc = _get_fastcode()
        return {
            "status": "healthy" if fc is not None else "unhealthy",
            "repo_loaded": fc.repo_loaded if fc else False,
            "repo_indexed": fc.repo_indexed if fc else False
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def get_repository_summary() -> Dict[str, Any]:
    """获取仓库摘要"""
    try:
        fc = _get_fastcode()
        summary = fc.get_repository_summary()
        return {"success": True, "summary": summary, "repo_info": fc.repo_info}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# 工具元数据
# ============================================================

TOOLS_METADATA = [
    {
        "name": "check_environment",
        "description": "检查环境配置（LLM API、依赖）",
        "category": "配置"
    },
    {
        "name": "get_setup_instructions",
        "description": "获取配置指南",
        "category": "配置"
    },
    {
        "name": "load_and_index",
        "description": "加载并索引仓库",
        "category": "仓库管理",
        "params": ["source", "is_url", "force"]
    },
    {
        "name": "list_repositories",
        "description": "列出仓库",
        "category": "仓库管理"
    },
    {
        "name": "query",
        "description": "代码库查询",
        "category": "查询",
        "params": ["question", "session_id", "enable_multi_turn", "commit_hash"]
    },
    {
        "name": "get_commits",
        "description": "获取提交历史",
        "category": "Commit"
    },
    {
        "name": "get_commit_diff",
        "description": "获取Commit变更",
        "category": "Commit"
    },
    {
        "name": "review_commit",
        "description": "Commit检视（推荐）",
        "category": "Commit",
        "params": ["question", "commit_hash"]
    },
    {
        "name": "get_status",
        "description": "获取系统状态",
        "category": "系统"
    },
    {
        "name": "get_repository_summary",
        "description": "获取仓库摘要",
        "category": "系统"
    }
]


__all__ = [
    # 配置
    "check_environment",
    "print_environment_report",
    "get_setup_instructions",
    
    # 仓库
    "load_and_index",
    "list_repositories",
    
    # 查询
    "query",
    
    # Commit
    "get_commits",
    "get_commit_diff",
    "review_commit",
    
    # 系统
    "get_status",
    "health_check",
    "get_repository_summary",
    
    # 元数据
    "TOOLS_METADATA",
]
