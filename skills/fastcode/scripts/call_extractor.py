"""
Multi-language Call Extractor - Extract function calls using Tree-sitter
Simplified version for commit review skill
"""

import logging
from typing import List, Dict, Any, Set, Optional

try:
    from tree_sitter import Language, Parser
    HAS_TREE_SITTER = True
except ImportError:
    HAS_TREE_SITTER = False


# Built-in functions for each language (to filter out)
PYTHON_BUILTINS = {
    'abs', 'all', 'any', 'bin', 'bool', 'bytes', 'callable', 'chr',
    'complex', 'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval',
    'exec', 'filter', 'float', 'format', 'frozenset', 'getattr',
    'globals', 'hasattr', 'hash', 'hex', 'id', 'input', 'int',
    'isinstance', 'issubclass', 'iter', 'len', 'list', 'locals', 'map',
    'max', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'print',
    'property', 'range', 'repr', 'reversed', 'round', 'set', 'setattr',
    'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple',
    'type', 'vars', 'zip', 'print', 'True', 'False', 'None',
}

JS_BUILTINS = {
    'console', 'Math', 'JSON', 'Date', 'Array', 'Object', 'String',
    'Number', 'Boolean', 'Function', 'Symbol', 'Map', 'Set', 'WeakMap',
    'WeakSet', 'Promise', 'Proxy', 'Reflect', 'Error', 'parseInt',
    'parseFloat', 'isNaN', 'isFinite', 'encodeURI', 'decodeURI',
    'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval',
    'require', 'module', 'exports', 'process',
}

JAVA_BUILTINS = {
    'System', 'String', 'Integer', 'Long', 'Double', 'Float', 'Boolean',
    'Character', 'Object', 'Class', 'Thread', 'Runnable', 'List', 'Map',
    'Set', 'ArrayList', 'HashMap', 'HashSet', 'Arrays', 'Collections',
    'Math', 'StringBuilder', 'println', 'print',
}

GO_BUILTINS = {
    'fmt', 'print', 'println', 'printf', 'make', 'new', 'len', 'cap',
    'append', 'copy', 'delete', 'panic', 'recover', 'close', 'complex',
    'real', 'imag', 'nil', 'true', 'false', 'iota',
}

RUST_BUILTINS = {
    'println', 'print', 'format', 'vec', 'String', 'str', 'i32', 'i64',
    'u32', 'u64', 'f32', 'f64', 'bool', 'char', 'Some', 'None', 'Ok', 'Err',
    'Result', 'Option', 'Vec', 'Box', 'Rc', 'Arc', 'Cell', 'RefCell',
    'hashmap', 'HashMap', 'HashSet', 'BTreeMap', 'BTreeSet',
}

C_BUILTINS = {
    'printf', 'scanf', 'sprintf', 'sscanf', 'fprintf', 'fscanf',
    'malloc', 'calloc', 'realloc', 'free', 'memcpy', 'memmove', 'memset', 'memcmp', 'memchr',
    'strlen', 'strcpy', 'strncpy', 'strcat', 'strncat', 'strcmp', 'strncmp', 'strchr', 'strstr',
    'atoi', 'atol', 'atof', 'atoll', 'strtol', 'strtoul', 'strtoll', 'strtoull',
    'exit', 'abort', 'assert', 'sizeof', 'offsetof',
    'malloc', 'realloc', 'free', 'calloc',
    'printf', 'scanf', 'fopen', 'fclose', 'fread', 'fwrite', 'fprintf', 'fscanf',
    'getchar', 'putchar', 'gets', 'puts', 'fgets', 'fputs',
    'time', 'clock', 'difftime', 'mktime', 'strftime',
    'rand', 'srand', 'abs', 'labs', 'llabs',
    'signal', 'raise', 'atexit',
    'NULL',
}

CPP_BUILTINS = {
    'cout', 'cin', 'cerr', 'clog', 'endl',
    'printf', 'scanf', 'malloc', 'free', 'sizeof',
    'std', 'string', 'vector', 'map', 'set', 'list', 'deque',
    'pair', 'tuple', 'array', 'span',
    'make_pair', 'make_tuple', 'make_shared', 'make_unique',
    'shared_ptr', 'unique_ptr', 'weak_ptr',
    'ios', 'istream', 'ostream', 'iostream', 'fstream', 'sstream',
    'stringstream', 'ostringstream', 'istringstream',
    'begin', 'end', 'size', 'empty', 'clear', 'push_back', 'pop_back',
    'insert', 'erase', 'find', 'count', 'begin', 'end',
    'true', 'false', 'nullptr', 'this',
}


def _get_builtins(language: str) -> Set[str]:
    """Get built-in functions for a language."""
    lang_lower = language.lower()
    if lang_lower == 'python':
        return PYTHON_BUILTINS
    elif lang_lower in ('javascript', 'typescript', 'tsx'):
        return JS_BUILTINS
    elif lang_lower == 'java':
        return JAVA_BUILTINS
    elif lang_lower == 'go':
        return GO_BUILTINS
    elif lang_lower == 'rust':
        return RUST_BUILTINS
    elif lang_lower == 'c':
        return C_BUILTINS
    elif lang_lower in ('cpp', 'cxx', 'cc', 'hpp'):
        return CPP_BUILTINS
    return set()


# Language configurations for call extraction
LANGUAGE_CONFIGS = {
    'python': {
        'call_node': 'call',
        'function_field': 'function',
        'identifier_node': 'identifier',
        'attribute_node': 'attribute',
        'attribute_name_field': 'attribute',
        'function_def_node': 'function_definition',
        'function_name_field': 'name',
        'class_def_node': 'class_definition',
        'method_name_field': 'name',
        'scope_nodes': ['function_definition', 'class_definition'],
    },
    'javascript': {
        'call_node': 'call_expression',
        'function_field': 'function',
        'identifier_node': 'identifier',
        'attribute_node': 'member_expression',
        'attribute_name_field': 'property',
        'function_def_node': 'function_declaration',
        'function_name_field': 'name',
        'class_def_node': 'class_declaration',
        'method_name_field': 'name',
        'scope_nodes': ['function_declaration', 'class_declaration', 'method_definition'],
    },
    'typescript': {
        'call_node': 'call_expression',
        'function_field': 'function',
        'identifier_node': 'identifier',
        'attribute_node': 'member_expression',
        'attribute_name_field': 'property',
        'function_def_node': 'function_declaration',
        'function_name_field': 'name',
        'class_def_node': 'class_declaration',
        'method_name_field': 'name',
        'scope_nodes': ['function_declaration', 'class_declaration', 'method_definition'],
    },
    'java': {
        'call_node': 'method_invocation',
        'function_field': 'name',
        'identifier_node': 'identifier',
        'attribute_node': 'method_invocation',
        'attribute_name_field': 'name',
        'function_def_node': 'method_declaration',
        'function_name_field': 'name',
        'class_def_node': 'class_declaration',
        'method_name_field': 'name',
        'scope_nodes': ['method_declaration', 'class_declaration'],
    },
    'go': {
        'call_node': 'call_expression',
        'function_field': 'function',
        'identifier_node': 'identifier',
        'attribute_node': 'selector_expression',
        'attribute_name_field': 'field',
        'function_def_node': 'function_declaration',
        'function_name_field': 'name',
        'class_def_node': 'type_declaration',
        'method_name_field': 'name',
        'scope_nodes': ['function_declaration'],
    },
    'rust': {
        'call_node': 'call_expression',
        'function_field': 'function',
        'identifier_node': 'identifier',
        'attribute_node': 'method_declaration',
        'attribute_name_field': 'field',
        'function_def_node': 'function_item',
        'function_name_field': 'declarator',
        'class_def_node': 'impl_item',
        'method_name_field': 'name',
        'scope_nodes': ['function_item', 'impl_item'],
    },
    'c': {
        'call_node': 'call_expression',
        'function_field': 'function',
        'identifier_node': 'identifier',
        'attribute_node': 'call_expression',
        'attribute_name_field': 'function',
        'function_def_node': 'function_definition',
        'function_name_field': 'declarator',
        'class_def_node': None,
        'method_name_field': 'declarator',
        'scope_nodes': ['function_definition'],
    },
    'cpp': {
        'call_node': 'call_expression',
        'function_field': 'function',
        'identifier_node': 'identifier',
        'attribute_node': 'call_expression',
        'attribute_name_field': 'function',
        'function_def_node': 'function_definition',
        'function_name_field': 'declarator',
        'class_def_node': 'class_specifier',
        'method_name_field': 'declarator',
        'scope_nodes': ['function_definition', 'class_specifier'],
    },
}


def _get_language_config(language: str) -> Optional[Dict]:
    """Get extraction config for a language."""
    lang_lower = language.lower()
    # TypeScript uses same config as JavaScript
    if lang_lower in ('typescript', 'tsx'):
        return LANGUAGE_CONFIGS.get('typescript')
    # C++ aliases
    if lang_lower in ('cpp', 'cxx', 'cc', 'h', 'hpp'):
        return LANGUAGE_CONFIGS.get('cpp')
    return LANGUAGE_CONFIGS.get(lang_lower)


class CallExtractor:
    """
    Extract function calls from code using Tree-sitter.
    Supports multiple programming languages.
    """
    
    def __init__(self, language: str = 'python'):
        self.logger = logging.getLogger(__name__)
        self.current_language = language.lower()
        self.parser = None
        self.language_obj = None
        self._initialized = False
        self._builtin_functions = _get_builtins(language)
    
    def _initialize(self):
        """Lazy initialization of tree-sitter parser."""
        if self._initialized:
            return
        
        if not HAS_TREE_SITTER:
            self.logger.warning("tree-sitter not installed, call extraction disabled")
            self._initialized = True
            return
        
        try:
            from tree_sitter_parser import TSParser
            ts_parser = TSParser(self.current_language)
            
            if ts_parser.is_healthy():
                self.parser = ts_parser.parser
                self.language_obj = ts_parser.language
                self._builtin_functions = _get_builtins(self.current_language)
                self.logger.debug(f"CallExtractor initialized for {self.current_language}")
            else:
                self.logger.warning(f"Failed to initialize parser for {self.current_language}")
                
        except ImportError as e:
            self.logger.warning(f"tree_sitter_parser not installed: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to initialize CallExtractor: {e}")
        
        self._initialized = True
    
    def is_available(self) -> bool:
        """Check if call extraction is available."""
        self._initialize()
        return self.parser is not None
    
    def set_language(self, language: str):
        """Switch to a different language."""
        if language.lower() == self.current_language:
            return
        self.current_language = language.lower()
        self._initialized = False
        self._initialize()
    
    def extract_calls(self, code: str, file_path: str = "") -> List[Dict[str, Any]]:
        """
        Extract function calls from code.
        
        Args:
            code: Source code string
            file_path: Path to the source file (for context)
        
        Returns:
            List of call information dicts with: call_name, line, scope
        """
        self._initialize()
        
        if not self.parser:
            return []
        
        config = _get_language_config(self.current_language)
        if not config:
            self.logger.debug(f"No config for language: {self.current_language}")
            return []
        
        try:
            tree = self.parser.parse(bytes(code, "utf8"))
            if tree is None:
                return []
            
            calls = []
            scope_stack = []  # Stack of (scope_type, scope_name)
            
            self._find_calls(tree.root_node, calls, scope_stack, config, file_path)
            return calls
            
        except Exception as e:
            self.logger.debug(f"Failed to extract calls from {file_path}: {e}")
            return []
    
    def _find_calls(self, node, calls: List, scope_stack: List, config: Dict, file_path: str):
        """Recursively find function calls in the AST."""
        if node is None:
            return
        
        node_type = node.type
        
        # Track scope (function/class)
        if node_type in config.get('scope_nodes', []):
            name_node = node.child_by_field_name(config.get('function_name_field', 'name'))
            if name_node:
                scope_name = name_node.text.decode('utf8') if isinstance(name_node.text, bytes) else str(name_node.text)
                scope_stack.append(scope_name)
            self._process_children(node, calls, scope_stack, config, file_path)
            if scope_stack:
                scope_stack.pop()
            return
        
        # Check for call expression
        if node_type == config.get('call_node'):
            func_node = node.child_by_field_name(config.get('function_field', 'function'))
            if func_node:
                call_name = self._extract_call_name(func_node, config)
                if call_name and call_name not in self._builtin_functions:
                    scope = '.'.join(scope_stack) if scope_stack else 'global'
                    calls.append({
                        'call_name': call_name,
                        'line': node.start_point[0] + 1,
                        'scope': scope,
                        'file': file_path,
                    })
        
        # Recurse into children
        self._process_children(node, calls, scope_stack, config, file_path)
    
    def _extract_call_name(self, func_node, config: Dict) -> Optional[str]:
        """Extract function name from a function node."""
        node_type = func_node.type
        
        if node_type == config.get('identifier_node'):
            return func_node.text.decode('utf8') if isinstance(func_node.text, bytes) else str(func_node.text)
        
        elif node_type == config.get('attribute_node'):
            # Method call like obj.method() or self.method()
            attr_name = func_node.child_by_field_name(config.get('attribute_name_field', 'attribute'))
            if attr_name:
                return attr_name.text.decode('utf8') if isinstance(attr_name.text, bytes) else str(attr_name.text)
        
        return None
    
    def _process_children(self, node, calls: List, scope_stack: List, config: Dict, file_path: str):
        """Process all children of a node."""
        if hasattr(node, 'children') and node.children:
            for child in node.children:
                self._find_calls(child, calls, scope_stack, config, file_path)
