# FastCode 环境配置指南

## .env 配置

在项目根目录创建 `.env` 文件：

```bash
MODEL=minimax/minimax-m2.2.1
BASE_URL=https://api.minimaxi.com/v1
OPENAI_API_KEY=your-api-key
```

## 环境检查

```python
import sys
from pathlib import Path

script_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(script_dir))

from fastcode_skill import check_environment, print_environment_report

report = check_environment()
print(print_environment_report(report))
```

## 必需依赖

- Python 3.8+
- fastcode (已集成在项目中)
- sentence-transformers
- python-dotenv (可选，用于加载.env)

## 常见问题

### 仓库未加载错误

```
Error: Repository not indexed. Call index_repository() first.
```

**解决方案**: 调用 `load_and_index()` 或 `load_repository()` + `index_repository()`

### Call Graph 分析不准确

代码修改后需要重新索引：

```python
import sys
from pathlib import Path

script_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(script_dir))

from fastcode_skill import reindex
reindex()  # 强制重建Call Graph
```
