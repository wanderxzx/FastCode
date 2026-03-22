"""
CodeElement - Core data structure for code indexing
Extracted from FastCode's indexer.py
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


@dataclass
class CodeElement:
    """Unified code element for indexing"""
    id: str
    type: str  # file, class, function, documentation
    name: str
    file_path: str
    relative_path: str
    language: str
    start_line: int
    end_line: int
    code: str
    signature: Optional[str] = None
    docstring: Optional[str] = None
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    repo_name: Optional[str] = None
    repo_url: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Remove embedding from metadata if present (too large to serialize)
        if d.get("metadata") and "embedding" in d["metadata"]:
            del d["metadata"]["embedding"]
        return d
    
    def to_simple_dict(self) -> Dict[str, Any]:
        """Simplified dict for LLM context"""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "file_path": self.relative_path,
            "signature": self.signature,
            "summary": self.summary or "",
            "code_snippet": self.code[:500] if self.code else "",  # Truncate for context
        }
