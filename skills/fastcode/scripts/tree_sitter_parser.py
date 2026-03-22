"""
Tree-sitter Parser Wrapper
Provides a simple interface for parsing code with tree-sitter
Supports multiple programming languages
"""

from typing import Optional, Dict
import logging

try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False
    Parser = None
    Language = None


# Language name to module mapping (同 FastCode)
LANGUAGE_MODULES = {
    'python': ('tree_sitter_python', 'language'),
    'javascript': ('tree_sitter_javascript', 'language'),
    'typescript': ('tree_sitter_typescript', 'language_typescript'),
    'tsx': ('tree_sitter_typescript', 'language_tsx'),
    'c': ('tree_sitter_c', 'language'),
    'cpp': ('tree_sitter_cpp', 'language'),
    'cxx': ('tree_sitter_cpp', 'language'),
    'rust': ('tree_sitter_rust', 'language'),
    'csharp': ('tree_sitter_csharp', 'language'),
    'cs': ('tree_sitter_csharp', 'language'),
    'java': ('tree_sitter_java', 'language'),
    'go': ('tree_sitter_go', 'language'),
}


class TSParser:
    """
    Tree-sitter parser wrapper for multiple languages
    """
    
    def __init__(self, language: str = 'python'):
        self.logger = logging.getLogger(__name__)
        self.current_language_name = language.lower()
        self.parser = None
        self.language = None
        self.languages_cache: Dict[str, Language] = {}
        self._initialize_parser()
    
    def _initialize_parser(self):
        """Initialize tree-sitter parser and language"""
        if not HAS_TREE_SITTER:
            self.logger.warning("tree-sitter not installed, parser will be limited")
            return
            
        try:
            self.language = self._load_language(self.current_language_name)
            if self.language:
                self.parser = Parser(self.language)
                self.logger.debug(f"Tree-sitter {self.current_language_name} parser initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize tree-sitter parser: {e}")
    
    def _load_language(self, language_name: str) -> Optional[Language]:
        """Load a tree-sitter language"""
        if language_name in self.languages_cache:
            return self.languages_cache[language_name]
        
        if not HAS_TREE_SITTER:
            return None
        
        if language_name not in LANGUAGE_MODULES:
            self.logger.warning(f"Unsupported language: {language_name}")
            return None
        
        try:
            module_name, func_name = LANGUAGE_MODULES[language_name]
            import importlib
            mod = importlib.import_module(module_name)
            
            # Get the language function
            lang_func = getattr(mod, func_name)
            lang = Language(lang_func())
            
            self.languages_cache[language_name] = lang
            self.logger.debug(f"Loaded language: {language_name}")
            return lang
            
        except ImportError as e:
            self.logger.warning(f"Language module not installed for {language_name}: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to load {language_name}: {e}")
        
        return None
    
    def is_healthy(self) -> bool:
        """Check if parser is properly initialized"""
        return self.parser is not None and self.language is not None
    
    def parse(self, code: str):
        """Parse code and return tree"""
        if self.parser is None:
            return None
        return self.parser.parse(bytes(code, "utf8"))
    
    def get_language(self) -> str:
        """Get current language name"""
        return self.current_language_name
    
    def set_language(self, language_name: str):
        """
        Switch the parser to a different language
        
        Args:
            language_name: Name of the language to switch to
        """
        if language_name == self.current_language_name:
            return
        
        self.current_language_name = language_name.lower()
        self.language = self._load_language(language_name)
        if self.language:
            self.parser = Parser(self.language)
        else:
            self.parser = None
