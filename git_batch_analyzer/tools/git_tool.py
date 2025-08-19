"""Git operations tool for repository analysis."""

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..types import ToolResponse, MergeCommit, DiffStats, BranchInfo

logger = logging.getLogger(__name__)


class GitTool:
    """Tool for performing git operations with structured JSON responses."""

    def __init__(self, repo_path: Path):
        """Initialize GitTool with repository path.

        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = Path(repo_path)
    
    def _should_exclude_file(self, filename: str) -> bool:
        """Check if a file should be excluded from analysis.
        
        Args:
            filename: Path to the file
            
        Returns:
            True if file should be excluded, False otherwise
        """
        # Exclude projen-generated files and directories
        if filename.startswith('.projen/') or filename == '.projenrc.py':
            return True
        
        # Exclude other common generated/build files
        excluded_patterns = [
            'node_modules/',
            '.git/',
            'dist/',
            'build/',
            'out/',
            '.vscode/',
            '.idea/',
            '__pycache__/',
            '*.pyc',
            '.DS_Store'
        ]
        
        for pattern in excluded_patterns:
            if pattern.endswith('/'):
                # Directory pattern
                if filename.startswith(pattern):
                    return True
            elif pattern.startswith('*.'):
                # File extension pattern
                if filename.endswith(pattern[1:]):
                    return True
            else:
                # Exact match
                if filename == pattern:
                    return True
        
        return False

    def _run_git_command(
        self, args: List[str], cwd: Optional[Path] = None
    ) -> ToolResponse:
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
                cmd, cwd=work_dir, capture_output=True, text=True, check=True
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
            depth: Fetch depth for shallow clone (use None for full clone)

        Returns:
            ToolResponse indicating success or failure
        """
        # Ensure parent directory exists
        self.repo_path.parent.mkdir(parents=True, exist_ok=True)

        # Remove existing directory if it exists
        if self.repo_path.exists():
            import shutil

            shutil.rmtree(self.repo_path)

        # For multi-branch analysis, do a full clone to get all branches
        if depth is None or depth <= 0:
            args = ["clone", url, str(self.repo_path)]
        else:
            args = ["clone", "--depth", str(depth), url, str(self.repo_path)]

        try:
            result = subprocess.run(
                ["git"] + args, capture_output=True, text=True, check=True
            )
            return ToolResponse.success_response(
                {
                    "message": f"Successfully cloned {url}",
                    "path": str(self.repo_path),
                    "depth": depth,
                }
            )
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

        # First fetch all branches (including remote branches not locally tracked)
        response = self._run_git_command(["fetch", "--all"])
        if not response.success:
            # Try alternative fetch strategies for corrupted repositories
            logger.warning(
                f"Standard fetch failed, trying shallow fetch: {response.data}"
            )

            # Try shallow fetch as fallback
            shallow_response = self._run_git_command(["fetch", "--all", "--depth=1"])
            if not shallow_response.success:
                # Try unshallow if shallow fetch worked
                logger.warning(
                    f"Shallow fetch failed, repository may be corrupted: {shallow_response.data}"
                )
                return ToolResponse.error_response(
                    f"Failed to fetch updates: {response.data}"
                )
            else:
                # Try to unshallow the repository
                unshallow_response = self._run_git_command(["fetch", "--unshallow"])
                if not unshallow_response.success:
                    logger.warning(
                        "Could not unshallow repository, continuing with shallow clone"
                    )
                response = shallow_response

        # If a specific branch is requested, ensure it's available locally
        if branch:
            # Check if branch exists locally
            local_check = self._run_git_command(["rev-parse", "--verify", branch])

            if not local_check.success:
                # Branch doesn't exist locally, create it from remote
                create_response = self._run_git_command(
                    ["checkout", "-b", branch, f"origin/{branch}"]
                )
                if not create_response.success:
                    return create_response
            else:
                # Branch exists locally, just checkout and pull
                checkout_response = self._run_git_command(["checkout", branch])
                if not checkout_response.success:
                    return checkout_response

                # Configure pull strategy to handle divergent branches
                config_response = self._run_git_command(
                    ["config", "pull.rebase", "false"]
                )
                if not config_response.success:
                    logger.warning(f"Could not configure pull strategy: {config_response.data}")
                
                # Pull with merge strategy to handle divergent branches
                pull_response = self._run_git_command(
                    ["pull", "origin", branch]
                )
                if not pull_response.success:
                    # If pull fails due to divergent branches, try reset to remote
                    logger.warning(
                        f"Pull failed, trying reset to remote: {pull_response.data}"
                    )
                    reset_response = self._run_git_command(
                        ["reset", "--hard", f"origin/{branch}"]
                    )
                    if not reset_response.success:
                        # If reset also fails, try force pull with merge
                        logger.warning(
                            f"Reset failed, trying force pull: {reset_response.data}"
                        )
                        force_pull_response = self._run_git_command(
                            [
                                "pull",
                                "--no-rebase",
                                "--allow-unrelated-histories",
                                "origin",
                                branch,
                            ]
                        )
                        if not force_pull_response.success:
                            # Last resort: create a new branch from remote and replace local
                            logger.warning(
                                f"Force pull failed, recreating branch from remote: {force_pull_response.data}"
                            )
                            backup_branch = f"{branch}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                            # Backup current branch
                            backup_response = self._run_git_command(
                                ["branch", "-m", backup_branch]
                            )
                            if backup_response.success:
                                # Create new branch from remote
                                recreate_response = self._run_git_command(
                                    ["checkout", "-b", branch, f"origin/{branch}"]
                                )
                                if recreate_response.success:
                                    logger.info(
                                        f"Successfully recreated branch '{branch}' from remote. Original branch backed up as '{backup_branch}'"
                                    )
                                else:
                                    return ToolResponse.error_response(
                                        f"Failed to recreate branch from remote: {recreate_response.error}"
                                    )
                            else:
                                return ToolResponse.error_response(
                                    f"Failed to backup divergent branch: {backup_response.error}"
                                )
                        else:
                            logger.info(f"Force pull successful for branch '{branch}'")
                    else:
                        logger.info(f"Reset to remote successful for branch '{branch}'")

        return ToolResponse.success_response(
            {"message": "Successfully fetched from remote", "branch": branch}
        )

    def checkout(self, branch: str) -> ToolResponse:
        """Checkout a specific branch.

        Args:
            branch: Branch name to checkout

        Returns:
            ToolResponse indicating success or failure
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")

        # Check if branch exists locally
        local_check = self._run_git_command(["rev-parse", "--verify", branch])

        if not local_check.success:
            # Branch doesn't exist locally, create it from remote
            create_response = self._run_git_command(
                ["checkout", "-b", branch, f"origin/{branch}"]
            )
            if not create_response.success:
                return ToolResponse.error_response(
                    f"Failed to create branch '{branch}': {create_response.error}"
                )
        else:
            # Branch exists locally, just checkout
            checkout_response = self._run_git_command(["checkout", branch])
            if not checkout_response.success:
                return ToolResponse.error_response(
                    f"Failed to checkout branch '{branch}': {checkout_response.error}"
                )

        return ToolResponse.success_response(
            {"message": f"Successfully checked out branch '{branch}'", "branch": branch}
        )

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
            branch,  # Use local branch instead of origin/{branch}
        ]

        response = self._run_git_command(args)
        if not response.success:
            return response

        merge_commits = []
        if response.data:
            for line in response.data.split("\n"):
                if line.strip():
                    parts = line.split("|", 4)
                    if len(parts) == 5:
                        hash_val, timestamp_str, message, parents_str, author = parts

                        # Convert timestamp
                        timestamp = datetime.fromtimestamp(
                            int(timestamp_str), tz=timezone.utc
                        )

                        # Parse parents
                        parents = parents_str.split() if parents_str else []

                        merge_commit = MergeCommit(
                            hash=hash_val,
                            timestamp=timestamp,
                            message=message,
                            parents=parents,
                            author=author,
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
            for line in response.data.split("\n"):
                line = line.strip()
                if line and not line.startswith("commit"):
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        try:
                            # Handle binary files (marked with '-')
                            add_str, del_str, filename = parts[0], parts[1], parts[2]
                            
                            # Skip excluded files (projen, build artifacts, etc.)
                            if self._should_exclude_file(filename):
                                continue
                            
                            if add_str != "-" and del_str != "-":
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
            total_changes=insertions + deletions,
        )

        return ToolResponse.success_response(diff_stats.to_dict())

    def remote_branches(self) -> ToolResponse:
        """Get information about all remote branches.

        Returns:
            ToolResponse with list of BranchInfo data
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")

        # Get remote URL from git config
        remote_url_response = self._run_git_command(
            ["config", "--get", "remote.origin.url"]
        )
        if not remote_url_response.success:
            return ToolResponse.error_response(
                "Could not get remote URL from git config"
            )

        remote_url = remote_url_response.data

        # Use ls-remote to get all branch heads from remote
        ls_remote_response = self._run_git_command(["ls-remote", "--heads", remote_url])
        if not ls_remote_response.success:
            return ToolResponse.error_response(
                f"Failed to list remote branches: {ls_remote_response.error}"
            )

        # Parse ls-remote output to get branch names
        remote_branches: List[str] = []
        if ls_remote_response.data:
            lines = ls_remote_response.data.split("\n")
            for line in lines:
                line = line.strip()
                if line:
                    parts = line.split("\t")
                    if len(parts) == 2 and parts[1] and parts[1].startswith("refs/heads/"):
                        branch_name = parts[1].replace("refs/heads/", "")
                        remote_branches.append(branch_name)

        # Now fetch each remote branch to make it available locally
        for branch in remote_branches:
            fetch_branch_response = self._run_git_command(["fetch", "origin", branch])
            if not fetch_branch_response.success:
                print(
                    f"Warning: Failed to fetch branch {branch}: {fetch_branch_response.error}"
                )

        # Get all branches (local and remote) with last commit info
        # Format: hash|timestamp|branch_name
        args = [
            "for-each-ref",
            "--format=%(objectname)|%(committerdate:unix)|%(refname:short)",
            "refs/heads",  # Local branches
            "refs/remotes/origin",  # Remote branches
        ]

        response = self._run_git_command(args)
        if not response.success:
            return response

        branches = []
        seen_branches = set()  # Track unique branch names

        if response.data:
            for line in response.data.split("\n"):
                line = line.strip()
                if line and not line.endswith("/HEAD"):
                    parts = line.split("|", 2)
                    if len(parts) == 3:
                        hash_val, timestamp_str, ref_name = parts

                        # Clean up branch name
                        branch_name = ref_name
                        if branch_name.startswith("origin/"):
                            branch_name = branch_name.replace("origin/", "", 1)

                        # Skip duplicates (prefer local branch info over remote)
                        if branch_name not in seen_branches and branch_name != "HEAD":
                            seen_branches.add(branch_name)

                            # Convert timestamp
                            timestamp = datetime.fromtimestamp(
                                int(timestamp_str), tz=timezone.utc
                            )

                            branch_info = BranchInfo(
                                name=branch_name,
                                last_commit_hash=hash_val,
                                last_commit_timestamp=timestamp,
                            )
                            branches.append(branch_info.to_dict())

        return ToolResponse.success_response(branches)

    def get_default_branch(self) -> ToolResponse:
        """Get the default branch of the repository.

        Returns:
            ToolResponse with the default branch name
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")

        # Get the default branch from remote
        response = self._run_git_command(["symbolic-ref", "refs/remotes/origin/HEAD"])
        if response.success and response.data:
            # Output format: refs/remotes/origin/main
            default_branch = response.data.split("/")[-1]
            return ToolResponse.success_response(default_branch)

        # Fallback: try to get the current branch
        response = self._run_git_command(["branch", "--show-current"])
        if response.success and response.data:
            return ToolResponse.success_response(response.data)

        # Final fallback: assume 'main' or 'master'
        # Check which one exists
        main_check = self._run_git_command(["rev-parse", "--verify", "origin/main"])
        if main_check.success:
            return ToolResponse.success_response("main")

        master_check = self._run_git_command(["rev-parse", "--verify", "origin/master"])
        if master_check.success:
            return ToolResponse.success_response("master")

        return ToolResponse.error_response("Could not determine default branch")

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
            branch,
        ]

        response = self._run_git_command(args)
        if not response.success:
            return response

        commits = []
        if response.data:
            for line in response.data.split("\n"):
                if line.strip():
                    parts = line.split("|", 4)
                    if len(parts) == 5:
                        hash_val, timestamp_str, message, author_name, author_email = (
                            parts
                        )

                        # Convert timestamp
                        try:
                            timestamp = datetime.fromtimestamp(
                                int(timestamp_str), tz=timezone.utc
                            )
                        except (ValueError, OSError):
                            continue

                        commits.append(
                            {
                                "hash": hash_val,
                                "timestamp": timestamp.isoformat(),
                                "message": message,
                                "author_name": author_name,
                                "author_email": author_email,
                            }
                        )

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
            for line in response.data.split("\n"):
                line = line.strip()
                if line:
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        try:
                            add_str, del_str, filename = parts[0], parts[1], parts[2]

                            # Skip excluded files (projen, build artifacts, etc.)
                            if self._should_exclude_file(filename):
                                continue

                            # Handle binary files (marked with '-')
                            if add_str == "-" or del_str == "-":
                                additions = 0
                                deletions = 0
                                is_binary = True
                            else:
                                additions = int(add_str) if add_str else 0
                                deletions = int(del_str) if del_str else 0
                                is_binary = False

                            file_changes.append(
                                {
                                    "filename": filename,
                                    "additions": additions,
                                    "deletions": deletions,
                                    "total_changes": additions + deletions,
                                    "is_binary": is_binary,
                                }
                            )
                        except ValueError:
                            # Skip lines that can't be parsed
                            continue

        return ToolResponse.success_response(file_changes)

    def get_committers(self, since_days: int, branch: Optional[str] = None) -> ToolResponse:
        """Get the names and email addresses of committers within a given period.

        Args:
            since_days: Number of days to look back.
            branch: Optional branch to check committers for. If None, uses current branch.

        Returns:
            ToolResponse with a list of unique committer emails.
        """
        if not self.repo_path.exists():
            return ToolResponse.error_response("Repository path does not exist")

        # Format for git log: author_email
        format_str = "%ae"
        args = [
            "log",
            f"--since={since_days} days ago",
            f"--format={format_str}",
        ]

        # If specific branch is provided, add it to the git log command
        if branch:
            # Check if branch exists first
            check_response = self._run_git_command(
                ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"]
            )
            if check_response.success:
                args.append(branch)
                logger.debug(f"Getting committers from branch: {branch}")
            else:
                # Try as remote branch
                remote_check = self._run_git_command(
                    ["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"]
                )
                if remote_check.success:
                    args.append(f"origin/{branch}")
                    logger.debug(
                        f"Getting committers from remote branch: origin/{branch}"
                    )
                else:
                    logger.warning(f"Branch {branch} not found, using current branch")

        response = self._run_git_command(args)
        if not response.success:
            return response

        if response.data:
            # Split by newline and filter out empty strings
            emails = set(filter(None, response.data.split("\n")))
            logger.debug(f"Found {len(emails)} unique committers: {list(emails)}")
            return ToolResponse.success_response(list(emails))

        return ToolResponse.success_response([])
