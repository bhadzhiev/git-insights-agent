"""Unit tests for GitTool with mocked git operations."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest

from git_batch_analyzer.tools.git_tool import GitTool
from git_batch_analyzer.types import ToolResponse


class TestGitTool:
    """Test cases for GitTool class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.repo_path = Path("/tmp/test-repo")
        self.git_tool = GitTool(self.repo_path)
    
    @patch('subprocess.run')
    def test_run_git_command_success(self, mock_run):
        """Test successful git command execution."""
        # Mock successful subprocess result
        mock_result = Mock()
        mock_result.stdout = "test output"
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        response = self.git_tool._run_git_command(["status"])
        
        assert response.success is True
        assert response.data == "test output"
        assert response.error is None
        mock_run.assert_called_once_with(
            ["git", "status"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        )
    
    @patch('subprocess.run')
    def test_run_git_command_failure(self, mock_run):
        """Test git command execution failure."""
        # Mock subprocess failure
        error = subprocess.CalledProcessError(1, ["git", "status"])
        error.stderr = "fatal: not a git repository"
        mock_run.side_effect = error
        
        response = self.git_tool._run_git_command(["status"])
        
        assert response.success is False
        assert response.data is None
        assert "Git command failed" in response.error
        assert "fatal: not a git repository" in response.error
    
    @patch('subprocess.run')
    @patch('shutil.rmtree')
    @patch.object(Path, 'exists')
    @patch.object(Path, 'mkdir')
    def test_clone_success(self, mock_mkdir, mock_exists, mock_rmtree, mock_run):
        """Test successful repository cloning."""
        # Setup mocks
        mock_exists.return_value = False
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        url = "https://github.com/test/repo.git"
        response = self.git_tool.clone(url, depth=100)
        
        assert response.success is True
        assert response.data["message"] == f"Successfully cloned {url}"
        assert response.data["path"] == str(self.repo_path)
        assert response.data["depth"] == 100
        
        mock_run.assert_called_once_with(
            ["git", "clone", "--depth", "100", url, str(self.repo_path)],
            capture_output=True,
            text=True,
            check=True
        )
    
    @patch('subprocess.run')
    def test_clone_failure(self, mock_run):
        """Test repository cloning failure."""
        # Mock subprocess failure
        error = subprocess.CalledProcessError(1, ["git", "clone"])
        error.stderr = "fatal: repository not found"
        mock_run.side_effect = error
        
        url = "https://github.com/test/nonexistent.git"
        response = self.git_tool.clone(url)
        
        assert response.success is False
        assert "Failed to clone" in response.error
        assert "repository not found" in response.error
    
    @patch.object(GitTool, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_fetch_success(self, mock_exists, mock_run_git):
        """Test successful git fetch."""
        mock_exists.return_value = True
        mock_run_git.return_value = ToolResponse.success_response("fetch output")
        
        response = self.git_tool.fetch("main")
        
        assert response.success is True
        assert response.data["message"] == "Successfully fetched from remote"
        assert response.data["branch"] == "main"
        
        # Verify the sequence of git commands called
        expected_calls = [
            call(["fetch", "origin"]),
            call(["rev-parse", "--verify", "main"]),
            call(["checkout", "main"]),
            call(["pull", "origin", "main"])
        ]
        mock_run_git.assert_has_calls(expected_calls)
    
    @patch.object(Path, 'exists')
    def test_fetch_repo_not_exists(self, mock_exists):
        """Test fetch when repository doesn't exist."""
        mock_exists.return_value = False
        
        response = self.git_tool.fetch()
        
        assert response.success is False
        assert "Repository path does not exist" in response.error
    
    @patch.object(GitTool, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_log_merges_success(self, mock_exists, mock_run_git):
        """Test successful merge commit retrieval."""
        mock_exists.return_value = True
        
        # Mock git log output
        git_output = (
            "abc123|1640995200|Merge pull request #1|def456 ghi789|John Doe\n"
            "xyz789|1640908800|Merge branch 'feature'|jkl012 mno345|Jane Smith"
        )
        mock_run_git.return_value = ToolResponse.success_response(git_output)
        
        response = self.git_tool.log_merges("main", 7)
        
        assert response.success is True
        assert len(response.data) == 2
        
        # Check first merge commit
        first_commit = response.data[0]
        assert first_commit["hash"] == "abc123"
        assert first_commit["message"] == "Merge pull request #1"
        assert first_commit["parents"] == ["def456", "ghi789"]
        assert first_commit["author"] == "John Doe"
        
        # Verify git command (now uses local branch instead of origin/branch)
        expected_format = "%H|%ct|%s|%P|%an"
        mock_run_git.assert_called_once_with([
            "log",
            "--since=7 days ago",
            "--merges",
            f"--format={expected_format}",
            "main"
        ])
    
    @patch.object(GitTool, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_log_merges_empty_result(self, mock_exists, mock_run_git):
        """Test merge commit retrieval with no results."""
        mock_exists.return_value = True
        mock_run_git.return_value = ToolResponse.success_response("")
        
        response = self.git_tool.log_merges("main", 7)
        
        assert response.success is True
        assert response.data == []
    
    @patch.object(GitTool, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_diff_stats_success(self, mock_exists, mock_run_git):
        """Test successful diff statistics retrieval."""
        mock_exists.return_value = True
        
        # Mock git show --numstat output
        git_output = (
            "10\t5\tfile1.py\n"
            "20\t15\tfile2.js\n"
            "0\t3\tfile3.md"
        )
        mock_run_git.return_value = ToolResponse.success_response(git_output)
        
        response = self.git_tool.diff_stats("abc123")
        
        assert response.success is True
        assert response.data["files_changed"] == 3
        assert response.data["insertions"] == 30  # 10 + 20 + 0
        assert response.data["deletions"] == 23   # 5 + 15 + 3
        assert response.data["total_changes"] == 53  # 30 + 23
        
        mock_run_git.assert_called_once_with([
            "show", "--numstat", "--format=", "abc123"
        ])
    
    @patch.object(GitTool, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_diff_stats_binary_files(self, mock_exists, mock_run_git):
        """Test diff statistics with binary files."""
        mock_exists.return_value = True
        
        # Mock git show --numstat output with binary files
        git_output = (
            "10\t5\tfile1.py\n"
            "-\t-\tbinary_file.jpg\n"
            "20\t15\tfile2.js"
        )
        mock_run_git.return_value = ToolResponse.success_response(git_output)
        
        response = self.git_tool.diff_stats("abc123")
        
        assert response.success is True
        assert response.data["files_changed"] == 3  # Including binary file
        assert response.data["insertions"] == 30    # 10 + 20 (binary file ignored)
        assert response.data["deletions"] == 20     # 5 + 15 (binary file ignored)
        assert response.data["total_changes"] == 50
    
    @patch.object(GitTool, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_remote_branches_success(self, mock_exists, mock_run_git):
        """Test successful remote branches retrieval."""
        mock_exists.return_value = True
        
        # Mock git for-each-ref output
        git_output = (
            "abc123|1640995200|origin/main\n"
            "def456|1640908800|origin/feature-branch\n"
            "ghi789|1640822400|origin/develop"
        )
        mock_run_git.return_value = ToolResponse.success_response(git_output)
        
        response = self.git_tool.remote_branches()
        
        assert response.success is True
        assert len(response.data) == 3
        
        # Check first branch
        first_branch = response.data[0]
        assert first_branch["name"] == "main"
        assert first_branch["last_commit_hash"] == "abc123"
        
        # Check second branch
        second_branch = response.data[1]
        assert second_branch["name"] == "feature-branch"
        assert second_branch["last_commit_hash"] == "def456"
        
        mock_run_git.assert_called_once_with([
            "for-each-ref",
            "--format=%(objectname)|%(committerdate:unix)|%(refname:short)",
            "refs/remotes/origin"
        ])
    
    @patch.object(GitTool, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_remote_branches_filters_head(self, mock_exists, mock_run_git):
        """Test that remote branches filters out HEAD reference."""
        mock_exists.return_value = True
        
        # Mock git for-each-ref output including HEAD
        git_output = (
            "abc123|1640995200|origin/main\n"
            "abc123|1640995200|origin/HEAD\n"
            "def456|1640908800|origin/feature-branch"
        )
        mock_run_git.return_value = ToolResponse.success_response(git_output)
        
        response = self.git_tool.remote_branches()
        
        assert response.success is True
        assert len(response.data) == 2  # HEAD should be filtered out
        
        branch_names = [branch["name"] for branch in response.data]
        assert "main" in branch_names
        assert "feature-branch" in branch_names
        assert "HEAD" not in branch_names
    
    @patch.object(Path, 'exists')
    def test_operations_repo_not_exists(self, mock_exists):
        """Test that operations fail when repository doesn't exist."""
        mock_exists.return_value = False
        
        # Test log_merges
        response = self.git_tool.log_merges("main", 7)
        assert response.success is False
        assert "Repository path does not exist" in response.error
        
        # Test diff_stats
        response = self.git_tool.diff_stats("abc123")
        assert response.success is False
        assert "Repository path does not exist" in response.error
        
        # Test remote_branches
        response = self.git_tool.remote_branches()
        assert response.success is False
        assert "Repository path does not exist" in response.error


class TestGitToolIntegration:
    """Integration tests for GitTool with more realistic scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.repo_path = Path("/tmp/test-repo")
        self.git_tool = GitTool(self.repo_path)
    
    @patch.object(GitTool, '_run_git_command')
    @patch.object(Path, 'exists')
    def test_complete_workflow_simulation(self, mock_exists, mock_run_git):
        """Test a complete workflow simulation with realistic data."""
        mock_exists.return_value = True
        
        # Simulate different git commands returning appropriate responses
        def mock_git_command(args):
            if args[0] == "log":
                # Return merge commits
                return ToolResponse.success_response(
                    "abc123|1640995200|Merge pull request #1|def456 ghi789|John Doe\n"
                    "xyz789|1640908800|Merge branch 'feature'|jkl012 mno345|Jane Smith"
                )
            elif args[0] == "show":
                # Return diff stats
                return ToolResponse.success_response(
                    "15\t8\tsrc/main.py\n"
                    "5\t2\ttests/test_main.py"
                )
            elif args[0] == "for-each-ref":
                # Return branch info
                return ToolResponse.success_response(
                    "abc123|1640995200|origin/main\n"
                    "def456|1640908800|origin/feature\n"
                    "ghi789|1640822400|origin/old-feature"
                )
            else:
                return ToolResponse.success_response("")
        
        mock_run_git.side_effect = mock_git_command
        
        # Test merge commits
        merge_response = self.git_tool.log_merges("main", 7)
        assert merge_response.success is True
        assert len(merge_response.data) == 2
        
        # Test diff stats for first commit
        diff_response = self.git_tool.diff_stats("abc123")
        assert diff_response.success is True
        assert diff_response.data["files_changed"] == 2
        assert diff_response.data["total_changes"] == 30  # 15+8+5+2
        
        # Test remote branches
        branches_response = self.git_tool.remote_branches()
        assert branches_response.success is True
        assert len(branches_response.data) == 3
        
        # Verify all responses have correct structure
        for commit in merge_response.data:
            assert all(key in commit for key in ["hash", "timestamp", "message", "parents", "author"])
        
        assert all(key in diff_response.data for key in ["files_changed", "insertions", "deletions", "total_changes"])
        
        for branch in branches_response.data:
            assert all(key in branch for key in ["name", "last_commit_hash", "last_commit_timestamp", "is_stale"])