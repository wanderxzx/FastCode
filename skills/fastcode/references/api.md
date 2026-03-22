# API Reference

## FastCodeReviewer

Main class for commit review and code understanding.

### Constructor

```python
from reviewer import FastCodeReviewer

reviewer = FastCodeReviewer(config)  # config is optional
```

### Methods

#### `load_and_index(repo_path, index_dir=None)`

Load repository and build index. **Handles three scenarios automatically:**
1. No index exists → builds new one
2. Index exists → loads it (fast, no rebuild)
3. Code changed → use `reindex()` to force rebuild

```python
reviewer = load_and_index("/path/to/repo")
```

#### `get_commits(max_count=50)`

Get list of recent commits.

**Returns:** `List[Dict]`

```python
commits = reviewer.get_commits(20)
# [{
#   "hash": "abc1234...",
#   "short_hash": "abc1234",
#   "message": "feat: add feature\n\nDetails...",
#   "summary": "feat: add feature",
#   "author": "John",
#   "author_email": "john@example.com",
#   "date": "2026-03-22T10:30:00"
# }]
```

#### `get_commit_diff(commit_hash)`

Get detailed diff for a commit.

**Returns:** `Dict`

```python
diff = reviewer.get_commit_diff("abc1234")
# {
#   "commit_hash": "abc1234...",
#   "short_hash": "abc1234",
#   "message": "feat: add feature",
#   "author": "John",
#   "date": "2026-03-22T10:30:00",
#   "parent_hash": "def5678...",
#   "changed_files": [
#     {"path": "src/main.py", "change_type": "modified", "additions": 50, "deletions": 10}
#   ],
#   "file_diffs": {
#     "src/main.py": {"diff": "...", "change_type": "modified"}
#   }
# }
```

#### `review_commit(question, commit_hash, output_dir=None)`

Generate commit review report.

**Args:**
- `question` (str): User question about the commit
- `commit_hash` (str): Commit hash to review
- `output_dir` (str, optional): Directory for report output

**Returns:** `str` - Path to generated report file

```python
report = reviewer.review_commit(
    question="检视这笔 commit 的影响",
    commit_hash="abc1234",
    output_dir="/reports"
)
```

#### `reindex()`

Rebuild index for loaded repository.

```python
reviewer.reindex()
```

## Helper Functions

### `load_and_index(repo_path, index_dir=None)`

Convenience function that creates a reviewer and loads the repo.

```python
from reviewer import load_and_index

reviewer = load_and_index("/path/to/repo")
```

### `review_commit(question, commit_hash, repo_path=None, output_dir=None)`

Convenience function for quick review.

```python
from reviewer import review_commit

review_commit(
    question="检视",
    commit_hash="abc1234",
    repo_path="/path/to/repo"
)
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_API_KEY` | - | API key for LLM |
| `LLM_PROVIDER` | `openai` | Provider: `openai`, `anthropic` |
| `LLM_MODEL` | `gpt-4` | Model name |
| `LLM_BASE_URL` | - | API base URL for proxies |
| `LLM_TEMPERATURE` | `0.4` | Generation temperature |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Embedding model |

### Programmatic Config

```python
from reviewer import SkillConfig

config = SkillConfig()
config.set_env(
    api_key="sk-...",
    provider="openai",
    model="gpt-4",
    temperature=0.4
)

reviewer = FastCodeReviewer(config.to_dict())
```
