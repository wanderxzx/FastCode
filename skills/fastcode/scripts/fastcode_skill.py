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


def review_commit(
    question: str,
    commit_hash: str,
    use_agency_mode: bool = False
) -> Dict[str, Any]:
    """
    Commit检视（参考web_app commit分析流程）
    
    Args:
        question: 分析问题
        commit_hash: Commit Hash
        use_agency_mode: 启用Agency模式
    
    Returns:
        FastCode原始分析结果
    """
    try:
        fc = _get_fastcode()
        
        # 获取diff信息
        diff = fc.get_commit_diff(commit_hash)
        
        # 执行查询
        result = fc.query(
            question=question,
            commit_hash=commit_hash,
            use_agency_mode=use_agency_mode
        )
        
        return result
    except Exception as e:
        return {"answer": f"Error: {str(e)}", "query": question, "error": str(e)}


# ============================================================
# Commit检视报告 - 标准化格式
# ============================================================

COMMIT_REVIEW_PROMPT = """请检视以下Commit，提供包含以下内容的报告：

1. **基本信息**：Commit ID、消息、变更文件数
2. **变更分析**：
   - 修改文件数、受影响函数数
   - 影响范围（调用者、被调用者数量）
3. **按文件分类**：每个修改文件的详情
4. **详细分析**：
   - 主要改动是什么
   - 涉及了哪些文件和模块
   - 有没有潜在问题或风险
5. **代码质量评估**：可读性、可维护性、健壮性等
6. **结论与建议**：推荐行动、改进点

请直接输出报告，不要有其他多余内容。"""


def commit_review(commit_hash: str) -> Dict[str, Any]:
    """
    Commit检视 - 标准化报告格式
    
    Args:
        commit_hash: Commit Hash
    
    Returns:
        包含标准化格式报告的FastCode结果
    """
    try:
        fc = _get_fastcode()
        
        result = fc.query(
            question=COMMIT_REVIEW_PROMPT,
            commit_hash=commit_hash,
            use_agency_mode=False
        )
        
        return result
    except Exception as e:
        return {"answer": f"Error: {str(e)}", "error": str(e)}


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
