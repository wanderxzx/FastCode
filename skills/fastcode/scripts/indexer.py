"""
Code Indexer - Index code repository for retrieval
Simplified for commit review skill
"""

import os
import ast
import hashlib
import logging
import sys
from typing import List, Dict, Any, Optional

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x: x

try:
    from .elements import CodeElement
except ImportError:
    from elements import CodeElement

# CallExtractor will be imported lazily to avoid circular imports
HAS_CALL_EXTRACTOR = None  # Will be set lazily


def _get_call_extractor():
    """Lazily import and return CallExtractor."""
    global HAS_CALL_EXTRACTOR
    if HAS_CALL_EXTRACTOR is None:
        try:
            from call_extractor import CallExtractor
            HAS_CALL_EXTRACTOR = True
            return CallExtractor()
        except ImportError:
            HAS_CALL_EXTRACTOR = False
            return None
    elif HAS_CALL_EXTRACTOR:
        return CallExtractor()
    return None


# Supported file extensions
SUPPORTED_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.hpp',
    '.go', '.rs', '.rb', '.php', '.cs', '.swift', '.kt', '.scala', '.lua',
    '.sh', '.bash', '.zsh', '.sql', '.yaml', '.yml', '.json', '.toml', '.xml',
    '.md', '.rst', '.txt'
}

IGNORE_PATTERNS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv', '.idea', '.vscode',
    'build', 'dist', 'target', '.pytest_cache', '.mypy_cache', '*.pyc', '*.pyo',
    '.DS_Store', 'Thumbs.db', '*.swp', '*.swo', '*~'
}


class CodeIndexer:
    """Index code repository at multiple levels"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.indexing_config = self.config.get("indexing", {})
        self.logger = logging.getLogger(__name__)
        
        self.elements: List[CodeElement] = []
        
        # Indexing options
        self.index_files = self.indexing_config.get("index_files", True)
        self.index_classes = self.indexing_config.get("index_classes", True)
        self.index_functions = self.indexing_config.get("index_functions", True)
        self.index_docs = self.indexing_config.get("index_documentation", True)
        
        # Call extractor for function call relationships (lazy loaded)
        self._call_extractor = None
    
    @property
    def call_extractor(self):
        """Lazy load call extractor."""
        if self._call_extractor is None:
            self._call_extractor = _get_call_extractor()
        return self._call_extractor
    
    def index_directory(self, directory: str, repo_name: str = "default") -> List[CodeElement]:
        """
        Index a directory of code files
        
        Args:
            directory: Path to directory
            repo_name: Repository name for identification
        
        Returns:
            List of indexed code elements
        """
        self.logger.info(f"Indexing directory: {directory}")
        self.elements = []
        
        # Collect all supported files
        files = []
        for root, dirs, filenames in os.walk(directory):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(root, d))]
            
            for filename in filenames:
                filepath = os.path.join(root, filename)
                if self._is_supported(filepath):
                    rel_path = os.path.relpath(filepath, directory)
                    files.append((filepath, rel_path))
        
        self.logger.info(f"Found {len(files)} supported files")
        
        # Index each file
        for filepath, rel_path in tqdm(files, desc="Indexing files"):
            try:
                elems = self._index_file(filepath, rel_path, repo_name)
                self.elements.extend(elems)
            except Exception as e:
                self.logger.warning(f"Failed to index {filepath}: {e}")
        
        self.logger.info(f"Indexed {len(self.elements)} elements from {len(files)} files")
        return self.elements
    
    def _index_file(self, filepath: str, rel_path: str, repo_name: str) -> List[CodeElement]:
        """Index a single file"""
        elems = []
        
        ext = os.path.splitext(filepath)[1].lower()
        language = self._get_language(ext)
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return elems
        
        # Index file element
        if self.index_files:
            file_elem = CodeElement(
                id=self._generate_id(rel_path, "file"),
                type="file",
                name=os.path.basename(filepath),
                file_path=filepath,
                relative_path=rel_path,
                language=language,
                start_line=1,
                end_line=len(content.splitlines()),
                code="",  # Don't store full content
                signature=None,
                docstring=None,
                summary=f"{language} file",
                metadata={"size": len(content), "extension": ext},
                repo_name=repo_name,
            )
            elems.append(file_elem)
        
        # Parse and index code elements (simplified Python parsing)
        if ext == '.py' and (self.index_classes or self.index_functions):
            elems.extend(self._parse_python_file(filepath, rel_path, content, repo_name, language))
        
        return elems
    
    def _parse_python_file(self, filepath: str, rel_path: str, content: str, 
                          repo_name: str, language: str) -> List[CodeElement]:
        """Parse Python file and extract classes/functions"""
        elems = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return elems
        
        # Add parent references to AST nodes for traversal
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child.parent = parent
        
        # Extract function calls using tree-sitter (if available)
        calls_by_scope = {}
        if self.call_extractor and self.call_extractor.is_available():
            try:
                all_calls = self.call_extractor.extract_calls(content, filepath)
                # Group calls by scope
                for call in all_calls:
                    scope = call.get('scope', 'module')
                    if scope not in calls_by_scope:
                        calls_by_scope[scope] = []
                    calls_by_scope[scope].append(call['call_name'])
            except Exception as e:
                self.logger.debug(f"Failed to extract calls: {e}")
        
        # Find function/class definitions and their calls
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and self.index_classes:
                elem = self._create_python_element(
                    node, "class", rel_path, repo_name, language, content,
                    calls_by_scope.get(node.name, [])
                )
                if elem:
                    elems.append(elem)
            
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and self.index_functions:
                # For methods, try both qualified name and simple name
                qualified_name = self._get_qualified_name(node)
                # Also try just the method name for top-level functions
                calls = calls_by_scope.get(qualified_name, [])
                if qualified_name != node.name:
                    calls = calls or calls_by_scope.get(node.name, [])
                elem = self._create_python_element(
                    node, "function", rel_path, repo_name, language, content, calls
                )
                if elem:
                    elems.append(elem)
        
        return elems
    
    def _get_qualified_name(self, node) -> str:
        """Get qualified name for methods (class_name.method_name)."""
        # Walk up the parent chain to find class context
        class_name = None
        current = node
        while hasattr(current, 'parent'):
            if isinstance(current, ast.ClassDef):
                class_name = current.name
                break
            current = current.parent
        
        if class_name:
            return f"{class_name}.{node.name}"
        return node.name
    
    def _create_python_element(self, node, elem_type: str, rel_path: str, 
                               repo_name: str, language: str, content: str,
                               calls: List[str] = None) -> Optional[CodeElement]:
        """Create a CodeElement from AST node"""
        try:
            # Get line numbers
            start_line = node.lineno
            end_line = node.end_lineno or start_line
            
            # Get source code
            lines = content.splitlines()
            if start_line > len(lines) or end_line > len(lines):
                return None
            
            code = "\n".join(lines[start_line-1:end_line])
            
            # Get docstring
            docstring = ast.get_docstring(node)
            
            # Get signature
            signature = None
            if hasattr(node, 'args'):
                args = [arg.arg for arg in node.args.args]
                signature = f"{node.name}({', '.join(args)})"
            
            # Generate element ID
            elem_id = self._generate_id(f"{rel_path}:{node.name}", elem_type)
            
            # Build metadata with calls
            metadata = {}
            if calls:
                metadata['calls'] = list(set(calls))  # Deduplicate
            
            # Import here to avoid potential circular import issues
            from elements import CodeElement
            
            return CodeElement(
                id=elem_id,
                type=elem_type,
                name=node.name,
                file_path=rel_path,
                relative_path=rel_path,
                language=language,
                start_line=start_line,
                end_line=end_line,
                code=code[:5000],  # Limit code length
                signature=signature,
                docstring=docstring,
                summary=docstring[:200] if docstring else None,
                metadata=metadata,
                repo_name=repo_name,
            )
        except Exception as e:
            self.logger.warning(f"Failed to create element {node.name}: {e}")
            return None
    
    def _generate_id(self, identifier: str, elem_type: str) -> str:
        """Generate unique ID for element"""
        combined = f"{identifier}:{elem_type}"
        return hashlib.md5(combined.encode()).hexdigest()[:16]
    
    def _is_supported(self, filepath: str) -> bool:
        """Check if file should be indexed"""
        ext = os.path.splitext(filepath)[1].lower()
        return ext in SUPPORTED_EXTENSIONS
    
    def _should_ignore(self, path: str) -> bool:
        """Check if path should be ignored"""
        basename = os.path.basename(path)
        for pattern in IGNORE_PATTERNS:
            if pattern.startswith('*'):
                if basename.endswith(pattern[1:]):
                    return True
            elif pattern in path:
                return True
        return False
    
    def _get_language(self, ext: str) -> str:
        """Map extension to language name"""
        lang_map = {
            '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
            '.jsx': 'javascript', '.tsx': 'typescript', '.java': 'java',
            '.c': 'c', '.cpp': 'cpp', '.go': 'go', '.rs': 'rust',
        }
        return lang_map.get(ext, 'unknown')
    
    def get_elements(self) -> List[CodeElement]:
        """Get all indexed elements"""
        return self.elements
    
    def get_elements_by_file(self, filepath: str) -> List[CodeElement]:
        """Get elements from a specific file"""
        return [e for e in self.elements if e.file_path == filepath]
