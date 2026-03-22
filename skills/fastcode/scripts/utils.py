"""
Utils - Minimal utility functions for FastCode skill
"""

import os
import logging
from typing import Dict, Any


def setup_logging(config: Dict[str, Any] = None) -> logging.Logger:
    """Setup logging"""
    if config is None:
        config = {}
    
    log_level = config.get("log_level", "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def ensure_dir(directory: str):
    """Ensure directory exists"""
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Estimate token count (rough approximation)
    Real implementation should use tiktoken or similar
    """
    # Rough estimate: ~4 characters per token for English, ~2 for Chinese
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 2 + other_chars / 4)


def truncate_to_tokens(text: str, max_tokens: int, model: str = "gpt-4") -> str:
    """Truncate text to max tokens"""
    tokens = count_tokens(text, model)
    if tokens <= max_tokens:
        return text
    
    # Binary search for the right length
    target_chars = int(len(text) * max_tokens / tokens)
    while count_tokens(text[:target_chars], model) > max_tokens and target_chars > 0:
        target_chars -= 100
    
    return text[:max(0, target_chars)]
