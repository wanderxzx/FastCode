"""
FastCode Commit Review Skill
"""

import os
import sys

# Dynamically find and add scripts directory to sys.path
# This works regardless of working directory and avoids namespace package conflicts
_current_file = os.path.abspath(__file__)
_scripts_dir = os.path.dirname(_current_file)  # .../fastcode/scripts
_skill_dir = os.path.dirname(_scripts_dir)     # .../fastcode
_workspace_dir = os.path.dirname(_skill_dir)  # .../workspace

# Add workspace/skills/fastcode to sys.path to enable "from skills.fastcode.scripts import ..."
_full_skill_path = os.path.join(_workspace_dir, 'skills', 'fastcode')
if _full_skill_path not in sys.path:
    sys.path.insert(0, _full_skill_path)

# Also add scripts dir directly
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from reviewer import FastCodeReviewer, load_and_index, review_commit
from config import SkillConfig
from llm_generator import LLMGenerator

__all__ = ["FastCodeReviewer", "load_and_index", "review_commit", "SkillConfig", "LLMGenerator"]
