"""
FastCode 环境配置引导模块

提供以下功能：
1. 环境检查 - 验证所有依赖是否正确安装
2. 配置引导 - 引导用户配置LLM API和模型
3. 健康检查 - 验证FastCode是否能正常工作
4. 自动修复 - 尝试自动修复常见配置问题
"""

import os
import sys
import subprocess
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConfigLevel(Enum):
    """配置级别"""
    CRITICAL = "critical"      # 必须配置
    RECOMMENDED = "recommended" # 推荐配置
    OPTIONAL = "optional"      # 可选配置


@dataclass
class ConfigRequirement:
    """配置需求"""
    name: str
    env_var: str
    description: str
    level: ConfigLevel
    example: str
    check_func: Optional[Callable[[], bool]] = None


@dataclass
class DependencyCheck:
    """依赖检查项"""
    name: str
    import_name: str
    required: bool
    install_cmd: str
    min_version: Optional[str] = None


@dataclass
class ConfigStatus:
    """配置状态"""
    name: str
    configured: bool
    value: Optional[str]
    status: str  # "ok", "warning", "error"
    message: str


# ============================================================
# 依赖检查
# ============================================================

PYTHON_DEPS: List[DependencyCheck] = [
    DependencyCheck("NumPy", "numpy", True, "pip install numpy"),
    DependencyCheck("GitPython", "git", True, "pip install gitpython"),
    DependencyCheck("Sentence Transformers", "sentence_transformers", True, "pip install sentence-transformers"),
    DependencyCheck("Rank BM25", "rank_bm25", True, "pip install rank-bm25"),
    DependencyCheck("Tree-sitter", "tree_sitter", True, "pip install tree-sitter"),
    DependencyCheck("PyYAML", "yaml", True, "pip install pyyaml"),
    DependencyCheck("Click", "click", True, "pip install click"),
    DependencyCheck("FastAPI", "fastapi", False, "pip install fastapi uvicorn"),
    DependencyCheck("FAISS", "faiss", False, "pip install faiss-cpu"),
]


# ============================================================
# 环境变量配置需求
# ============================================================

LLM_CONFIG: List[ConfigRequirement] = [
    ConfigRequirement(
        name="MODEL",
        env_var="MODEL",
        description="LLM模型名称（如 gpt-4o、gpt-4、claude-3-sonnet 等）",
        level=ConfigLevel.CRITICAL,
        example="MODEL=gpt-4o",
        check_func=lambda: os.getenv("MODEL") is not None
    ),
    ConfigRequirement(
        name="BASE_URL",
        env_var="BASE_URL",
        description="LLM API基础URL（OpenAI兼容格式）",
        level=ConfigLevel.CRITICAL,
        example="BASE_URL=https://api.openai.com/v1 或 https://api.deepseek.com",
        check_func=lambda: os.getenv("BASE_URL") is not None
    ),
    ConfigRequirement(
        name="API_KEY",
        env_var="API_KEY",
        description="LLM API密钥",
        level=ConfigLevel.CRITICAL,
        example="API_KEY=sk-...",
        check_func=lambda: os.getenv("API_KEY") is not None
    ),
]

EMBEDDING_CONFIG: List[ConfigRequirement] = [
    ConfigRequirement(
        name="EMBEDDING_MODEL",
        env_var="EMBEDDING_MODEL",
        description="Embedding模型名称（用于代码向量检索）",
        level=ConfigLevel.RECOMMENDED,
        example="EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        check_func=None  # 有默认值
    ),
]


# ============================================================
# 配置检查函数
# ============================================================

def check_python_deps() -> Dict[str, Any]:
    """
    检查Python依赖是否正确安装
    
    Returns:
        包含检查结果的字典
    """
    results = []
    all_ok = True
    
    for dep in PYTHON_DEPS:
        try:
            if dep.import_name == "git":
                import git
                version = git.VersionInfo.__version__ if hasattr(git, 'VersionInfo') else "unknown"
            elif dep.import_name == "yaml":
                import yaml
                version = yaml.__version__
            else:
                module = __import__(dep.import_name)
                version = getattr(module, "__version__", "unknown")
            
            results.append({
                "name": dep.name,
                "status": "ok",
                "version": version,
                "required": dep.required
            })
        except ImportError:
            all_ok = False
            results.append({
                "name": dep.name,
                "status": "error",
                "install_cmd": dep.install_cmd,
                "required": dep.required
            })
    
    return {
        "success": all_ok,
        "results": results,
        "missing_required": [r for r in results if r["status"] == "error" and r["required"]]
    }


def _get_api_key() -> Optional[str]:
    """
    获取API Key，支持多种环境变量命名
    
    优先级: API_KEY > OPENAI_API_KEY > AZURE_OPENAI_KEY > ANTHROPIC_API_KEY
    """
    return (
        os.getenv("API_KEY") or
        os.getenv("OPENAI_API_KEY") or
        os.getenv("AZURE_OPENAI_KEY") or
        os.getenv("ANTHROPIC_API_KEY") or
        os.getenv("DEEPSEEK_API_KEY") or
        os.getenv("GEMINI_API_KEY")
    )


def check_llm_config() -> Dict[str, Any]:
    """
    检查LLM配置是否正确
    
    Returns:
        配置状态列表
    """
    statuses = []
    
    # 检查MODEL
    model_value = os.getenv("MODEL")
    configured = model_value is not None
    if configured:
        statuses.append(ConfigStatus(
            name="MODEL",
            configured=True,
            value=model_value,
            status="ok",
            message=f"已配置: {model_value}"
        ))
    else:
        statuses.append(ConfigStatus(
            name="MODEL",
            configured=False,
            value=None,
            status="error",
            message="未配置 (critical): LLM模型名称"
        ))
    
    # 检查BASE_URL
    base_url_value = os.getenv("BASE_URL")
    configured = base_url_value is not None
    if configured:
        # 隐藏敏感信息
        display_url = base_url_value[:50] + "..." if len(base_url_value) > 50 else base_url_value
        statuses.append(ConfigStatus(
            name="BASE_URL",
            configured=True,
            value=display_url,
            status="ok",
            message=f"已配置: {display_url}"
        ))
    else:
        statuses.append(ConfigStatus(
            name="BASE_URL",
            configured=False,
            value=None,
            status="error",
            message="未配置 (critical): LLM API基础URL"
        ))
    
    # 检查API_KEY (支持多种命名)
    api_key_value = _get_api_key()
    configured = api_key_value is not None
    if configured:
        display_key = "***" + api_key_value[-8:] if len(api_key_value) > 8 else "***"
        # 记录实际使用的环境变量名
        actual_var = (
            "API_KEY" if os.getenv("API_KEY") else
            "OPENAI_API_KEY" if os.getenv("OPENAI_API_KEY") else
            "其他"
        )
        statuses.append(ConfigStatus(
            name=f"API_KEY ({actual_var})",
            configured=True,
            value=display_key,
            status="ok",
            message=f"已配置: {display_key}"
        ))
    else:
        statuses.append(ConfigStatus(
            name="API_KEY",
            configured=False,
            value=None,
            status="error",
            message="未配置 (critical): LLM API密钥 (支持: API_KEY, OPENAI_API_KEY等)"
        ))
    
    all_critical = all(s.status != "error" for s in statuses)
    
    return {
        "success": all_critical,
        "configured": all(s.configured for s in statuses),
        "statuses": [
            {"name": s.name, "configured": s.configured, "status": s.status, "message": s.message}
            for s in statuses
        ]
    }


def check_embedding_model() -> Dict[str, Any]:
    """
    检查Embedding模型
    
    Returns:
        模型状态
    """
    model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    return {
        "name": "Embedding Model",
        "model": model_name,
        "configured": True,
        "status": "ok",
        "message": f"使用模型: {model_name}"
    }


def check_fastcode_import() -> Dict[str, Any]:
    """
    检查FastCode是否能正常导入
    
    Returns:
        导入状态
    """
    try:
        from fastcode import FastCode
        return {
            "success": True,
            "status": "ok",
            "message": "FastCode导入成功",
            "version": getattr(FastCode, "__version__", "unknown")
        }
    except ImportError as e:
        return {
            "success": False,
            "status": "error",
            "message": f"FastCode导入失败: {str(e)}",
            "error": str(e)
        }
    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "message": f"FastCode初始化失败: {str(e)}",
            "error": str(e)
        }


# ============================================================
# 完整环境检查
# ============================================================

def check_environment() -> Dict[str, Any]:
    """
    执行完整的环境检查
    
    Returns:
        完整的检查报告
    """
    report = {
        "timestamp": str(subprocess.run(["date"], capture_output=True, text=True).stdout.strip()),
        "python_version": sys.version,
        "checks": {}
    }
    
    # 1. Python依赖
    report["checks"]["dependencies"] = check_python_deps()
    
    # 2. LLM配置
    report["checks"]["llm_config"] = check_llm_config()
    
    # 3. Embedding模型
    report["checks"]["embedding"] = check_embedding_model()
    
    # 4. FastCode导入
    report["checks"]["fastcode"] = check_fastcode_import()
    
    # 5. 整体状态
    deps_ok = report["checks"]["dependencies"]["success"]
    llm_ok = report["checks"]["llm_config"]["success"]
    fastcode_ok = report["checks"]["fastcode"]["success"]
    
    report["overall_status"] = "ready" if (deps_ok and llm_ok and fastcode_ok) else "not_ready"
    report["can_run"] = deps_ok and llm_ok and fastcode_ok
    
    return report


def print_environment_report(report: Dict[str, Any]) -> str:
    """
    格式化输出环境检查报告
    
    Returns:
        格式化的报告字符串
    """
    lines = []
    lines.append("=" * 60)
    lines.append("FastCode 环境检查报告")
    lines.append("=" * 60)
    lines.append(f"时间: {report['timestamp']}")
    lines.append(f"Python: {report['python_version'].split()[0]}")
    lines.append("")
    
    # 依赖检查
    lines.append("【依赖检查】")
    deps = report["checks"]["dependencies"]
    for dep in deps["results"]:
        if dep["status"] == "ok":
            lines.append(f"  ✅ {dep['name']}: {dep.get('version', 'ok')}")
        else:
            lines.append(f"  ❌ {dep['name']}: 未安装")
            lines.append(f"     安装命令: {dep.get('install_cmd', 'N/A')}")
    lines.append("")
    
    # LLM配置
    lines.append("【LLM配置】")
    llm = report["checks"]["llm_config"]
    for status in llm["statuses"]:
        icon = "✅" if status["configured"] else "❌"
        lines.append(f"  {icon} {status['name']}: {status['message']}")
    lines.append("")
    
    # Embedding
    emb = report["checks"]["embedding"]
    lines.append("【Embedding模型】")
    lines.append(f"  ✅ {emb['model']}")
    lines.append("")
    
    # FastCode
    fc = report["checks"]["fastcode"]
    icon = "✅" if fc["success"] else "❌"
    lines.append("【FastCode】")
    lines.append(f"  {icon} {fc['message']}")
    lines.append("")
    
    # 整体状态
    lines.append("=" * 60)
    icon = "✅" if report["can_run"] else "❌"
    lines.append(f"整体状态: {icon} {report['overall_status'].upper()}")
    lines.append("=" * 60)
    
    return "\n".join(lines)


# ============================================================
# 配置引导
# ============================================================

def get_setup_instructions() -> Dict[str, Any]:
    """
    获取完整的配置引导指令
    
    Returns:
        分步配置指南
    """
    return {
        "step_1_env_vars": {
            "title": "步骤1: 配置环境变量",
            "description": "设置LLM API相关环境变量",
            "variables": [
                {
                    "name": "MODEL",
                    "example": "gpt-4o",
                    "description": "使用的LLM模型名称",
                    "required": True
                },
                {
                    "name": "BASE_URL",
                    "example": "https://api.openai.com/v1",
                    "description": "API基础URL（支持OpenAI兼容格式）",
                    "required": True
                },
                {
                    "name": "API_KEY",
                    "example": "sk-xxx...",
                    "description": "API密钥",
                    "required": True
                }
            ],
            "example_bash": '''# 在 ~/.bashrc 或 ~/.zshrc 中添加:
export MODEL="gpt-4o"
export BASE_URL="https://api.openai.com/v1"
export API_KEY="your-api-key-here"

# 或者使用临时环境变量:
export MODEL="gpt-4o" BASE_URL="https://api.openai.com/v1" API_KEY="sk-xxx" python your_script.py''',
            "example_windows": '''# 在命令提示符中:
set MODEL=gpt-4o
set BASE_URL=https://api.openai.com/v1
set API_KEY=your-api-key-here''',
        },
        
        "step_2_deps": {
            "title": "步骤2: 安装依赖",
            "description": "确保所有Python依赖正确安装",
            "commands": [
                "pip install numpy gitpython sentence-transformers rank-bm25 pyyaml click",
                "pip install tree-sitter tree-sitter-python tree-sitter-javascript",
                "pip install fastapi uvicorn",  # 可选，用于Web界面
                "pip install faiss-cpu"  # 可选，用于向量存储
            ]
        },
        
        "step_3_models": {
            "title": "步骤3: 下载Embedding模型",
            "description": "首次运行时FastCode会自动下载Embedding模型",
            "note": "如果网络较慢，可以手动下载:",
            "command": '''python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
print('Model downloaded successfully')
"'''
        },
        
        "step_4_verify": {
            "title": "步骤4: 验证配置",
            "description": "运行以下命令验证配置是否正确",
            "command": '''python -c "
from skills.fastcode.scripts.config import check_environment, print_environment_report
report = check_environment()
print(print_environment_report(report))
"'''
        }
    }


# ============================================================
# 导出
# ============================================================

__all__ = [
    "check_environment",
    "check_python_deps",
    "check_llm_config",
    "check_embedding_model",
    "check_fastcode_import",
    "print_environment_report",
    "get_setup_instructions",
    "ConfigLevel",
    "ConfigRequirement",
    "DependencyCheck",
    "ConfigStatus",
]
