"""
FastCode Commit Review Skill - Main Entry Point
"""

import os
import sys
import logging
import re
from typing import Dict, List, Any, Optional, Iterator

# Ensure scripts directory is in path
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

# Load environment variables from .env file in skill directory
try:
    from dotenv import load_dotenv
    _skill_dir = os.path.dirname(_scripts_dir)
    _env_path = os.path.join(_skill_dir, '.env')
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass  # dotenv not installed

from config import SkillConfig
from git_utils import GitUtils
from call_graph import CallGraphBuilder
from embedder import CodeEmbedder
from vector_store import VectorStore
from retriever import HybridRetriever
from indexer import CodeIndexer
from prompt_builder import PromptBuilder
from llm_generator import LLMGenerator


def _parse_hunk_headers(diff_text: str) -> List[Dict[str, Any]]:
    """
    Parse diff to extract modified line numbers from hunk headers.
    Returns list of {file_path, line_numbers} where line_numbers are modified positions.
    """
    hunk_pattern = re.compile(r'^@@\s*-(\d+)(?:,\d+)?\s*\+(\d+)(?:,\d+)?\s*@@', re.MULTILINE)
    result = []
    
    current_file = None
    lines = diff_text.split('\n')
    
    for line in lines:
        if line.startswith('--- ') or line.startswith('+++ '):
            # Extract file path
            match = re.match(r'^[+-]{3}\s+(?:a/)?(.+)', line)
            if match:
                current_file = match.group(1)
        elif line.startswith('@@'):
            # Hunk header - extract new file line number
            match = hunk_pattern.match(line)
            if match and current_file:
                start_line = int(match.group(2))
                result.append({
                    'file': current_file,
                    'start_line': start_line,
                    'header': line
                })
    
    return result


def _find_functions_containing_lines(file_path: str, modified_lines: List[int], 
                                      git_repo_path: str = None, commit_hash: str = None) -> List[str]:
    """
    Find function and class definitions that contain the given line numbers.
    Returns list of function/class names.
    
    Args:
        file_path: Relative path to the file in repo
        modified_lines: List of line numbers that were modified
        git_repo_path: Path to the git repository (for getting file at specific commit)
        commit_hash: Commit hash (if provided, get file content at this commit)
    """
    content = None
    
    # Try to get file content at the specific commit
    if git_repo_path and commit_hash:
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'show', f'{commit_hash}:{file_path}'],
                cwd=git_repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                content = result.stdout
        except Exception:
            pass
    
    # Fall back to local file if couldn't get from git
    if content is None:
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            return []
    
    lines = content.split('\n')
    results = []
    
    # Build list of (line_number, indent, name, type) for functions and classes
    definitions = []
    
    # Function pattern: def func_name(...) or async def func_name(...)
    func_pattern = re.compile(r'^(\s*)(?:async\s+)?def\s+(\w+)\s*\(')
    # Class pattern: class ClassName(...)
    class_pattern = re.compile(r'^(\s*)class\s+(\w+)\s*[:\(]')
    
    for i, line in enumerate(lines, 1):
        func_match = func_pattern.match(line)
        if func_match:
            indent = len(func_match.group(1))
            func_name = func_match.group(2)
            definitions.append((i, indent, func_name, 'function'))
        
        class_match = class_pattern.match(line)
        if class_match:
            indent = len(class_match.group(1))
            class_name = class_match.group(2)
            definitions.append((i, indent, class_name, 'class'))
    
    # For each modified line, find the containing scope
    for mod_line in modified_lines:
        best_match = None
        best_indent = -1
        
        for line_num, indent, name, def_type in definitions:
            if line_num <= mod_line:
                # Prefer more specific scope (larger indent)
                if indent >= best_indent:
                    best_match = (name, def_type)
                    best_indent = indent
        
        if best_match:
            name, def_type = best_match
            if name not in results:
                results.append(name)
    
    return results


class FastCodeReviewer:
    """FastCode commit review skill"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or SkillConfig().to_dict()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.vector_store = VectorStore(self.config)
        self.embedder = CodeEmbedder(self.config)
        self.graph_builder = CallGraphBuilder(self.config)
        self.indexer = CodeIndexer(self.config)
        self.retriever = HybridRetriever(self.config, self.vector_store)
        self.prompt_builder = PromptBuilder(self.config)
        self.llm_generator = LLMGenerator(self.config)
        
        # State
        self.repo_path: Optional[str] = None
        self.index_dir: Optional[str] = None
        self.git_utils: Optional[GitUtils] = None
    
    def load_and_index(self, repo_path: str, index_dir: Optional[str] = None) -> bool:
        """
        Load repository and build index
        
        Args:
            repo_path: Path to the repository
            index_dir: Directory to store index data (overrides config)
        
        Returns:
            True if successful
        """
        self.repo_path = os.path.abspath(repo_path)
        # Use provided index_dir, or default to repo's .fastcode_index
        self.index_dir = index_dir if index_dir else os.path.join(self.repo_path, ".fastcode_index")
        
        self.logger.info(f"Loading repository: {self.repo_path}")
        
        # Initialize git utils
        self.git_utils = GitUtils(self.repo_path)
        
        # Set up index directory
        self.vector_store.persist_dir = self.index_dir
        self.graph_builder.set_persist_dir(self.index_dir)
        
        # Check if index exists
        if os.path.exists(self.index_dir):
            self.logger.info(f"Loading existing index from {self.index_dir}")
            if self._load_index():
                return True
        
        # Build new index
        self.logger.info("Building new index...")
        return self._build_index()
    
    def _build_index(self) -> bool:
        """Build index for repository"""
        try:
            # Index repository
            elements = self.indexer.index_directory(self.repo_path)
            self.logger.info(f"Indexed {len(elements)} elements")
            
            # Generate embeddings
            if self.embedder.model and elements:
                element_dicts = [e.to_dict() for e in elements]
                element_dicts = self.embedder.embed_code_elements(element_dicts)
                
                # Add to vector store
                embeddings = []
                for elem in element_dicts:
                    if "embedding" in elem:
                        embeddings.append(elem["embedding"])
                
                if embeddings:
                    import numpy as np
                    self.vector_store.initialize(len(embeddings[0]))
                    self.vector_store.add_vectors(
                        np.array(embeddings),
                        element_dicts
                    )
                
                # Build call graph (remove embedding before creating CodeElement)
                from elements import CodeElement
                code_elements = []
                for e in element_dicts:
                    # Remove top-level embedding fields before creating CodeElement
                    e_clean = {k: v for k, v in e.items() 
                               if k not in ("embedding", "embedding_text")}
                    code_elements.append(CodeElement(**e_clean))
                self.graph_builder.build_graphs(code_elements)
            
            # Build BM25 index
            if elements:
                self.retriever.index_for_bm25([e.to_dict() for e in elements])
            
            # Save index
            self._save_index()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to build index: {e}")
            return False
    
    def _save_index(self):
        """Save index to disk"""
        self.logger.info("Saving index to disk...")
        self.vector_store.save()
        self.graph_builder.save()
        self.logger.info("Index saved successfully")
    
    def _load_index(self) -> bool:
        """Load index from disk"""
        if self.vector_store.load() and self.graph_builder.load():
            # Rebuild BM25 from loaded elements
            elements = [m for m in self.vector_store.metadata if m]
            if elements:
                self.retriever.index_for_bm25(elements)
            return True
        return False
    
    def reindex(self) -> bool:
        """Reindex the repository"""
        if not self.repo_path:
            raise RuntimeError("No repository loaded")
        
        self.logger.info("Reindexing repository...")
        return self._build_index()
    
    def get_commits(self, max_count: int = 50) -> List[Dict[str, Any]]:
        """Get commit list"""
        if not self.git_utils:
            raise RuntimeError("No repository loaded")
        return self.git_utils.get_commit_list(max_count)
    
    def get_commit_diff(self, commit_hash: str) -> Dict[str, Any]:
        """Get commit diff"""
        if not self.git_utils:
            raise RuntimeError("No repository loaded")
        return self.git_utils.get_commit_diff(commit_hash)
    
    def review_commit(self, question: str, commit_hash: str, 
                     output_dir: Optional[str] = None) -> str:
        """
        Review a commit and generate report
        
        Args:
            question: User question about the commit
            commit_hash: Commit hash to review
            output_dir: Directory to save report (default: skill dir)
        
        Returns:
            Path to the generated report file
        """
        if not self.git_utils:
            raise RuntimeError("No repository loaded")
        
        # Get commit diff
        commit_info = self.get_commit_diff(commit_hash)
        
        # Enhance with call graph analysis
        commit_info = self._enhance_with_call_graph(commit_info)
        
        # Build query info
        query_info = {
            "commit_info": commit_info,
            "intent": "commit_review"
        }
        
        # Retrieve relevant code elements
        retrieved = self._retrieve_relevant(question)
        
        # Build context
        context = self._build_context(retrieved)
        
        # Build prompt
        prompts = self.prompt_builder.build(question, context, query_info)
        
        # Generate answer using LLM
        answer = self._generate_answer(prompts)
        
        # Clean answer (remove think content)
        answer = self._clean_think_content(answer)
        
        # Generate report
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        report_path = self._generate_report(
            commit_info, answer, 
            output_dir or skill_dir
        )
        
        return report_path
    
    def _clean_think_content(self, text: str) -> str:
        """Remove think tags and content from LLM response"""
        # Remove <think>...</think> blocks
        text = re.sub(r'<think>[\s\S]*?</think>', '', text)
        # Remove <thinking>...</thinking> blocks
        text = re.sub(r'<thinking>[\s\S]*?</thinking>', '', text)
        # Clean up multiple blank lines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def _enhance_with_call_graph(self, commit_info: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance commit info with call graph analysis"""
        if not commit_info.get('file_diffs'):
            return commit_info
        
        if not self.graph_builder or not self.graph_builder.element_by_name:
            # No call graph available
            commit_info['call_graph_analysis'] = {
                'total_modified_functions': 0,
                'total_callers': 0,
                'total_callees': 0,
                'file_details': {},
                'callers': {},
                'callees': {}
            }
            return commit_info
        
        call_graph_stats = {
            'total_modified_functions': 0,
            'total_callers': 0,
            'total_callees': 0,
            'file_details': {},
            'callers': {},
            'callees': {}
        }
        
        changed_files = commit_info.get('changed_files', [])
        file_diffs = commit_info.get('file_diffs', {})
        
        # Regex patterns for function/class definitions in diff
        diff_func_pattern = re.compile(r'^[+]?(?:def\s+(\w+)\s*\()', re.MULTILINE)
        class_pattern = re.compile(r'^[+]?(?:class\s+(\w+)\s*[:\(])', re.MULTILINE)
        
        all_modified_funcs = set()
        
        for file_info in changed_files:
            file_path = file_info.get('path', '')
            
            # Skip non-code files
            if not file_path.endswith('.py'):
                continue
            
            diff_text = file_diffs.get(file_path, {}).get('diff', '')
            if not diff_text:
                continue
            
            modified_in_file = []
            
            # Method 1: Find new function definitions in diff
            for match in diff_func_pattern.finditer(diff_text):
                func_name = match.group(1)
                if func_name and not func_name.startswith('_'):
                    modified_in_file.append(func_name)
                    all_modified_funcs.add(func_name)
            
            # Method 2: Find class definitions in diff
            for match in class_pattern.finditer(diff_text):
                class_name = match.group(1)
                if class_name:
                    modified_in_file.append(class_name)
                    all_modified_funcs.add(class_name)
            
            # Method 3: Find functions containing modified lines
            # Parse hunk headers to get modified line numbers
            hunk_pattern = re.compile(r'^@@\s*-(\d+)(?:,\d+)?\s*\+(\d+)(?:,\d+)?\s*@@', re.MULTILINE)
            modified_lines = []
            
            for match in hunk_pattern.finditer(diff_text):
                start_line = int(match.group(2))
                modified_lines.append(start_line)
            
            if modified_lines:
                # Find the repo path for full file path
                repo_path = self.repo_path if hasattr(self, 'repo_path') else ''
                full_file_path = os.path.join(repo_path, file_path) if repo_path else file_path
                
                # Get absolute path for local file fallback
                if not os.path.isabs(full_file_path):
                    full_file_path = os.path.abspath(full_file_path)
                
                # Get commit hash for git-based file retrieval
                commit_hash = commit_info.get('commit_hash', '')
                
                # Find functions/classes containing these lines (include private ones)
                # Pass commit_hash to get file content at that specific commit
                containing_funcs = _find_functions_containing_lines(
                    file_path, modified_lines, 
                    git_repo_path=repo_path if os.path.isabs(repo_path) else None,
                    commit_hash=commit_hash
                )
                for func_name in containing_funcs:
                    modified_in_file.append(func_name)
                    all_modified_funcs.add(func_name)
            
            if modified_in_file:
                call_graph_stats['file_details'][file_path] = {
                    'modified_functions': list(set(modified_in_file)),
                    'modified_count': len(set(modified_in_file))
                }
        
        # Look up call graph relationships for modified functions
        callers_map = {}
        callees_map = {}
        
        for func_name in all_modified_funcs:
            # Find element by name
            element = self.graph_builder.element_by_name.get(func_name)
            if not element:
                continue
            
            element_id = element.id
            
            # Get callers (who calls this function)
            caller_ids = self.graph_builder.get_callers(element_id)
            callers = []
            for caller_id in caller_ids:
                caller_elem = self.graph_builder.element_by_id.get(caller_id)
                if caller_elem:
                    callers.append(caller_elem.name)
            
            if callers:
                callers_map[func_name] = callers
                call_graph_stats['total_callers'] += len(callers)
            
            # Get callees (what this function calls)
            callee_ids = self.graph_builder.get_callees(element_id)
            callees = []
            for callee_id in callee_ids:
                callee_elem = self.graph_builder.element_by_id.get(callee_id)
                if callee_elem:
                    callees.append(callee_elem.name)
            
            if callees:
                callees_map[func_name] = callees
                call_graph_stats['total_callees'] += len(callees)
        
        call_graph_stats['total_modified_functions'] = len(all_modified_funcs)
        call_graph_stats['callers'] = callers_map
        call_graph_stats['callees'] = callees_map
        
        commit_info['call_graph_analysis'] = call_graph_stats
        return commit_info
    
    def _retrieve_relevant(self, query: str, top_k: int = 10) -> List:
        """Retrieve relevant code elements"""
        if not self.vector_store.get_count():
            return []
        
        # Get query embedding
        if self.embedder.model:
            query_embedding = self.embedder.embed_text(query)
            results = self.vector_store.search(query_embedding, k=top_k)
            return [r[0] for r in results]
        
        return []
    
    def _build_context(self, retrieved: List[Dict[str, Any]]) -> str:
        """Build context string from retrieved elements"""
        if not retrieved:
            return "No relevant code found."
        
        context_parts = []
        for elem in retrieved[:10]:  # Limit to 10 elements
            file_path = elem.get('file_path', elem.get('relative_path', 'unknown'))
            name = elem.get('name', 'unknown')
            elem_type = elem.get('type', 'unknown')
            code = elem.get('code', '')[:500]
            
            context_parts.append(f"**{file_path}** ({elem_type}: {name})\n```\n{code}\n```\n")
        
        return "\n".join(context_parts)
    
    def _generate_answer(self, prompts: Dict[str, str]) -> str:
        """Generate answer using LLM"""
        system_prompt = prompts.get("system", "")
        user_prompt = prompts.get("user", "")
        
        if not self.llm_generator.is_available():
            return "Error: LLM not available. Please set LLM_API_KEY or OPENAI_API_KEY."
        
        # Build full prompt with system message
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        return self.llm_generator.generate(full_prompt)
    
    def _generate_answer_stream(self, prompts: Dict[str, str]) -> Iterator[str]:
        """Generate answer using LLM with streaming"""
        system_prompt = prompts.get("system", "")
        user_prompt = prompts.get("user", "")
        
        if not self.llm_generator.is_available():
            yield "Error: LLM not available. Please set LLM_API_KEY or OPENAI_API_KEY."
            return
        
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        for chunk in self.llm_generator.generate_stream(full_prompt):
            yield chunk
    
    def _generate_report(self, commit_info: Dict[str, Any], 
                        answer: str, output_dir: str) -> str:
        """Generate markdown report"""
        import datetime
        
        commit_hash = commit_info.get('short_hash', 'unknown')
        filename = f"commit_review_{commit_hash}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(output_dir, filename)
        
        report = f"""# Commit 检视报告

## 基本信息
- **Commit**: `{commit_info.get('commit_hash', 'unknown')}`
- **Message**: {commit_info.get('message', '').split(chr(10))[0]}
- **Author**: {commit_info.get('author', 'unknown')}
- **Date**: {commit_info.get('date', 'unknown')}

## 检视结果
{answer}

---
*由 FastCode Commit Review Skill 生成*
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        self.logger.info(f"Report saved to {filepath}")
        return filepath


# Convenience functions
def load_and_index(repo_path: str, index_dir: Optional[str] = None) -> FastCodeReviewer:
    """Load repository and build index"""
    reviewer = FastCodeReviewer()
    reviewer.load_and_index(repo_path, index_dir)
    return reviewer


def review_commit(question: str, commit_hash: str, 
                repo_path: str = None, output_dir: Optional[str] = None) -> str:
    """
    Review a commit and generate report file.
    
    Args:
        question: Question about the commit
        commit_hash: Commit hash to review
        repo_path: Repository path
        output_dir: Directory to save report (default: skill dir)
    
    Returns:
        Path to the generated report file
    """
    reviewer = FastCodeReviewer()
    if repo_path:
        reviewer.load_and_index(repo_path)
    
    return reviewer.review_commit(
        question=question,
        commit_hash=commit_hash,
        output_dir=output_dir
    )
