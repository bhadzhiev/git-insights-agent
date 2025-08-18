"""Git operations tool for repository analysis."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..types import ToolResponse, MergeCommit, DiffStats, BranchInfo


class GitTool:
    """Tool for performing git operations with structured JSON responses."""
    
    def __init__(self, repo_path: Path):
        """Initialize GitTool with repository path.
        
        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = Path(repo_path)
    
    def _run_git_command(self, args: List[str], cwd: Optional[Path] = None) -> ToolResponse:
        """Run a git command and return structured response.
        
        Args:
            args: Git command arguments (without 'git')
            cwd: Working directory for the command
            
        Returns:
            ToolResponse with command output or error
        """
        cmd = ["git"] + args
        work_dir = cwd or self.repo_path
        
        try:
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return ToolResponse.success_response(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            error_msg = f"Git command failed: {' '.join(cmd)}\nError: {e.stderr}"
            return ToolResponse.error_response(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error running git command: {' '.join(cmd)}\nError: {str(e)}"
            return ToolResponse.error_response(error_msg)
    
    def clone(self, url: str, depth: int = 200) -> ToolResponse:
        """Clone a repository with shallow clone support.
        
        Args:
            url: Repository URL to clone
            depth: Fetch depth for shallow clone
            
        Returns:
            ToolResponse indicating success or failure
        """
        # Ensure parent directory exists
        self.repo_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing directory if it exists
        if self.repo_path.exists():
            import shutil
            shutil.rmtree(self.repo_path)
        
        args = ["clone", "--depth", str(depth), url, str(self.repo_path)]
        
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                check=True
            )
            return ToolResponse.success_response({
                "message": f"Successfully cloned {url}",
                "path": str(self.repo_path),
                "depth": depth
            })
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to clone {url}: {e.stderr}"
            return ToolResponse.error_response(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error cloning {url}: {str(e)}"
            return ToolResponse.error_response(error_msg)
    
    def fetch(self, branch: Optional[str] = None) -> ToolResponse:
        """Fetch latest changes from remote and checkout branch if specified.
        
        Args:
            branch: Specific branch to fetch and checkout, or None for all branches
            
        Returns:
            ToolResponse indicating success or failure
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")
        
        # First fetch all branches
        response = self._run_git_command(["fetch", "origin"])
        if not response.success:
            return response
        
        # If a specific branch is requested, ensure it's available locally
        if branch:
            # Check if branch exists locally
            local_check = self._run_git_command(["rev-parse", "--verify", branch])
            
            if not local_check.success:
                # Branch doesn't exist locally, create it from remote
                create_response = self._run_git_command(["checkout", "-b", branch, f"origin/{branch}"])
                if not create_response.success:
                    return create_response
            else:
                # Branch exists locally, just checkout and pull
                checkout_response = self._run_git_command(["checkout", branch])
                if not checkout_response.success:
                    return checkout_response
                
                pull_response = self._run_git_command(["pull", "origin", branch])
                if not pull_response.success:
                    return pull_response
        
        return ToolResponse.success_response({
            "message": "Successfully fetched from remote",
            "branch": branch
        })
    
    def log_merges(self, branch: str, since_days: int) -> ToolResponse:
        """Get merge commits from the specified branch and time period.
        
        Args:
            branch: Branch to analyze
            since_days: Number of days to look back
            
        Returns:
            ToolResponse with list of MergeCommit data
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")
        
        # Format for git log: hash|timestamp|message|parents|author
        format_str = "%H|%ct|%s|%P|%an"
        args = [
            "log",
            f"--since={since_days} days ago",
            "--merges",
            f"--format={format_str}",
            branch  # Use local branch instead of origin/{branch}
        ]
        
        response = self._run_git_command(args)
        if not response.success:
            return response
        
        merge_commits = []
        if response.data:
            for line in response.data.split('\n'):
                if line.strip():
                    parts = line.split('|', 4)
                    if len(parts) == 5:
                        hash_val, timestamp_str, message, parents_str, author = parts
                        
                        # Convert timestamp
                        timestamp = datetime.fromtimestamp(int(timestamp_str), tz=timezone.utc)
                        
                        # Parse parents
                        parents = parents_str.split() if parents_str else []
                        
                        merge_commit = MergeCommit(
                            hash=hash_val,
                            timestamp=timestamp,
                            message=message,
                            parents=parents,
                            author=author
                        )
                        merge_commits.append(merge_commit.to_dict())
        
        return ToolResponse.success_response(merge_commits)
    
    def diff_stats(self, commit_hash: str) -> ToolResponse:
        """Get diff statistics for a specific commit.
        
        Args:
            commit_hash: Hash of the commit to analyze
            
        Returns:
            ToolResponse with DiffStats data
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")
        
        # Get numstat for the commit
        args = ["show", "--numstat", "--format=", commit_hash]
        response = self._run_git_command(args)
        
        if not response.success:
            return response
        
        files_changed = 0
        insertions = 0
        deletions = 0
        
        if response.data:
            for line in response.data.split('\n'):
                line = line.strip()
                if line and not line.startswith('commit'):
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        try:
                            # Handle binary files (marked with '-')
                            add_str, del_str = parts[0], parts[1]
                            if add_str != '-' and del_str != '-':
                                insertions += int(add_str) if add_str else 0
                                deletions += int(del_str) if del_str else 0
                            files_changed += 1
                        except ValueError:
                            # Skip lines that can't be parsed
                            continue
        
        diff_stats = DiffStats(
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
            total_changes=insertions + deletions
        )
        
        return ToolResponse.success_response(diff_stats.to_dict())
    
    def remote_branches(self) -> ToolResponse:
        """Get information about all remote branches.
        
        Returns:
            ToolResponse with list of BranchInfo data
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")
        
        # Get remote branches with last commit info
        # Format: hash|timestamp|branch_name
        args = [
            "for-each-ref",
            "--format=%(objectname)|%(committerdate:unix)|%(refname:short)",
            "refs/remotes/origin"
        ]
        
        response = self._run_git_command(args)
        if not response.success:
            return response
        
        branches = []
        if response.data:
            for line in response.data.split('\n'):
                line = line.strip()
                if line and not line.endswith('/HEAD'):
                    parts = line.split('|', 2)
                    if len(parts) == 3:
                        hash_val, timestamp_str, ref_name = parts
                        
                        # Remove 'origin/' prefix from branch name
                        branch_name = ref_name.replace('origin/', '', 1)
                        
                        # Convert timestamp
                        timestamp = datetime.fromtimestamp(int(timestamp_str), tz=timezone.utc)
                        
                        branch_info = BranchInfo(
                            name=branch_name,
                            last_commit_hash=hash_val,
                            last_commit_timestamp=timestamp
                        )
                        branches.append(branch_info.to_dict())
        
        return ToolResponse.success_response(branches)
    
    def log_all_commits(self, branch: str, since_days: int) -> ToolResponse:
        """Get all commits (not just merges) from the specified branch and time period.
        
        Args:
            branch: Branch to analyze
            since_days: Number of days to look back
            
        Returns:
            ToolResponse with list of commit data including author info
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")
        
        # Format for git log: hash|timestamp|message|author_name|author_email
        format_str = "%H|%ct|%s|%an|%ae"
        args = [
            "log",
            f"--since={since_days} days ago",
            f"--format={format_str}",
            branch
        ]
        
        response = self._run_git_command(args)
        if not response.success:
            return response
        
        commits = []
        if response.data:
            for line in response.data.split('\n'):
                if line.strip():
                    parts = line.split('|', 4)
                    if len(parts) == 5:
                        hash_val, timestamp_str, message, author_name, author_email = parts
                        
                        # Convert timestamp
                        try:
                            timestamp = datetime.fromtimestamp(int(timestamp_str), tz=timezone.utc)
                        except (ValueError, OSError):
                            continue
                        
                        commits.append({
                            "hash": hash_val,
                            "timestamp": timestamp.isoformat(),
                            "message": message,
                            "author_name": author_name,
                            "author_email": author_email
                        })
        
        return ToolResponse.success_response(commits)
    
    def get_commit_files(self, commit_hash: str) -> ToolResponse:
        """Get the list of files changed in a specific commit with change stats.
        
        Args:
            commit_hash: Hash of the commit to analyze
            
        Returns:
            ToolResponse with list of file changes
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")
        
        # Get files changed with stats: additions, deletions, filename
        args = ["show", "--numstat", "--format=", commit_hash]
        
        response = self._run_git_command(args)
        if not response.success:
            return response
        
        file_changes = []
        if response.data:
            for line in response.data.split('\n'):
                line = line.strip()
                if line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        try:
                            add_str, del_str, filename = parts[0], parts[1], parts[2]
                            
                            # Handle binary files (marked with '-')
                            if add_str == '-' or del_str == '-':
                                additions = 0
                                deletions = 0
                                is_binary = True
                            else:
                                additions = int(add_str) if add_str else 0
                                deletions = int(del_str) if del_str else 0
                                is_binary = False
                            
                            file_changes.append({
                                "filename": filename,
                                "additions": additions,
                                "deletions": deletions,
                                "total_changes": additions + deletions,
                                "is_binary": is_binary
                            })
                        except ValueError:
                            # Skip lines that can't be parsed
                            continue
        
        return ToolResponse.success_response(file_changes)