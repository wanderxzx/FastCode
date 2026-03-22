"""
Git Utils - Git operations for commit review
Extract and simplify from FastCode's loader.py
"""

import os
import logging
from typing import Dict, List, Optional, Any
from git import Repo

logger = logging.getLogger(__name__)


class GitUtils:
    """Git operations for commit analysis"""
    
    def __init__(self, repo_path: str):
        """
        Initialize GitUtils with a repository path
        
        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = repo_path
        self.repo = None
        self._init_repo()
    
    def _init_repo(self):
        """Initialize git repository"""
        if not os.path.exists(self.repo_path):
            raise ValueError(f"Repository path does not exist: {self.repo_path}")
        
        if not os.path.exists(os.path.join(self.repo_path, ".git")):
            raise ValueError(f"Not a git repository: {self.repo_path}")
        
        self.repo = Repo(self.repo_path)
        logger.info(f"Initialized git repo at: {self.repo_path}")
    
    def get_commit_list(self, max_count: int = 50) -> List[Dict[str, Any]]:
        """
        Get list of commits from the repository
        
        Args:
            max_count: Maximum number of commits to retrieve
        
        Returns:
            List of commit dictionaries with hash, message, author, date, etc.
        """
        try:
            commits = []
            
            for commit in self.repo.iter_commits(max_count=max_count):
                commit_info = {
                    "hash": commit.hexsha,
                    "short_hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": commit.author.name,
                    "author_email": commit.author.email,
                    "date": commit.committed_datetime.isoformat(),
                    "summary": commit.message.split('\n')[0].strip() if commit.message else "",
                }
                commits.append(commit_info)
            
            logger.info(f"Retrieved {len(commits)} commits from repository")
            return commits
            
        except Exception as e:
            logger.error(f"Failed to get commit list: {e}")
            return []
    
    def get_commit_diff(self, commit_hash: str) -> Dict[str, Any]:
        """
        Get diff information for a specific commit
        
        Args:
            commit_hash: Full or short commit hash
        
        Returns:
            Dictionary with diff information including changed files and diffs
        """
        try:
            commit = self.repo.commit(commit_hash)
            
            # Check if this is a shallow clone
            is_shallow = self.repo.git.rev_parse('--is-shallow-repository', '--quiet', with_exceptions=False) == 0
            
            # If shallow clone and commit has parents, try to fetch more history
            if is_shallow and commit.parents:
                logger.info("Repository is shallow clone, attempting to fetch more history...")
                try:
                    self.repo.git.fetch('--unshallow')
                    commit = self.repo.commit(commit_hash)
                    logger.info("Successfully fetched more history")
                except Exception as fetch_error:
                    logger.warning(f"Failed to fetch more history: {fetch_error}")
            
            # Get the diff with parent commit
            if not commit.parents:
                parent = None
                diff_items = list(commit.diff(None, create_patch=True, R=True))
            else:
                parent = commit.parents[0]
                try:
                    diff_items = list(commit.diff(parent, create_patch=True, R=True))
                except Exception as diff_error:
                    logger.error(f"Failed to get diff between commits: {diff_error}")
                    diff_items = []
            
            changed_files = []
            file_diffs = {}
            
            for diff_item in diff_items:
                file_path = diff_item.b_path or diff_item.a_path
                
                change_type = "modified"
                if diff_item.new_file:
                    change_type = "added"
                elif diff_item.deleted_file:
                    change_type = "deleted"
                elif diff_item.renamed_file:
                    change_type = "renamed"
                
                # Try to get diff text
                diff_text = ""
                try:
                    if diff_item.diff:
                        diff_text = diff_item.diff.decode('utf-8', errors='ignore')
                except Exception:
                    diff_text = ""
                
                # Count additions and deletions
                additions = 0
                deletions = 0
                
                if diff_text:
                    lines = diff_text.split('\n')
                    for line in lines:
                        if line.startswith('diff --git') or line.startswith('index ') or \
                           line.startswith('--- ') or line.startswith('+++ ') or line.startswith('@@'):
                            continue
                        
                        if line.startswith('+') and not line.startswith('+++'):
                            if line[1:].strip():
                                additions += 1
                        elif line.startswith('-') and not line.startswith('---'):
                            if line[1:].strip():
                                deletions += 1
                
                file_info = {
                    "path": file_path,
                    "change_type": change_type,
                    "additions": additions,
                    "deletions": deletions,
                }
                
                changed_files.append(file_info)
                file_diffs[file_path] = {
                    "diff": diff_text,
                    "change_type": change_type,
                }
            
            return {
                "commit_hash": commit.hexsha,
                "short_hash": commit.hexsha[:8],
                "message": commit.message.strip(),
                "author": commit.author.name,
                "date": commit.committed_datetime.isoformat(),
                "parent_hash": parent.hexsha if parent else None,
                "changed_files": changed_files,
                "file_diffs": file_diffs,
            }
            
        except Exception as e:
            logger.error(f"Failed to get commit diff: {e}")
            raise
    
    def checkout_commit(self, commit_hash: str) -> bool:
        """
        Checkout a specific commit
        
        Args:
            commit_hash: Full or short commit hash
        
        Returns:
            True if successful
        """
        try:
            self.repo.git.checkout(commit_hash)
            logger.info(f"Checked out commit {commit_hash}")
            return True
        except Exception as e:
            logger.error(f"Failed to checkout commit {commit_hash}: {e}")
            return False
