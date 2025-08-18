"""Tests for core data types and state management."""

import pytest
from datetime import datetime
from pathlib import Path

from git_batch_analyzer.types import (
    AnalysisState,
    BranchInfo,
    DiffStats,
    MergeCommit,
    PRMetrics,
    ToolResponse,
    create_initial_state,
)


class TestToolResponse:
    """Test ToolResponse dataclass."""
    
    def test_success_response(self):
        """Test creating a successful response."""
        response = ToolResponse.success_response({"key": "value"})
        assert response.success is True
        assert response.data == {"key": "value"}
        assert response.error is None
    
    def test_error_response(self):
        """Test creating an error response."""
        response = ToolResponse.error_response("Something went wrong")
        assert response.success is False
        assert response.data is None
        assert response.error == "Something went wrong"


class TestMergeCommit:
    """Test MergeCommit dataclass."""
    
    def test_merge_commit_creation(self):
        """Test creating a MergeCommit."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        commit = MergeCommit(
            hash="abc123",
            timestamp=timestamp,
            message="Merge pull request #123",
            parents=["def456", "ghi789"],
            author="John Doe"
        )
        
        assert commit.hash == "abc123"
        assert commit.timestamp == timestamp
        assert commit.message == "Merge pull request #123"
        assert commit.parents == ["def456", "ghi789"]
        assert commit.author == "John Doe"
    
    def test_merge_commit_to_dict(self):
        """Test converting MergeCommit to dictionary."""
        timestamp = datetime(2024, 1, 15, 10, 30, 0)
        commit = MergeCommit(
            hash="abc123",
            timestamp=timestamp,
            message="Merge pull request #123",
            parents=["def456", "ghi789"],
            author="John Doe"
        )
        
        result = commit.to_dict()
        expected = {
            "hash": "abc123",
            "timestamp": "2024-01-15T10:30:00",
            "message": "Merge pull request #123",
            "parents": ["def456", "ghi789"],
            "author": "John Doe"
        }
        assert result == expected


class TestDiffStats:
    """Test DiffStats dataclass."""
    
    def test_diff_stats_creation(self):
        """Test creating DiffStats with automatic total calculation."""
        stats = DiffStats(
            files_changed=5,
            insertions=100,
            deletions=50,
            total_changes=0  # This should be overridden by __post_init__
        )
        
        assert stats.files_changed == 5
        assert stats.insertions == 100
        assert stats.deletions == 50
        assert stats.total_changes == 150  # 100 + 50
    
    def test_diff_stats_to_dict(self):
        """Test converting DiffStats to dictionary."""
        stats = DiffStats(
            files_changed=3,
            insertions=75,
            deletions=25,
            total_changes=0
        )
        
        result = stats.to_dict()
        expected = {
            "files_changed": 3,
            "insertions": 75,
            "deletions": 25,
            "total_changes": 100
        }
        assert result == expected


class TestBranchInfo:
    """Test BranchInfo dataclass."""
    
    def test_branch_info_creation(self):
        """Test creating BranchInfo."""
        timestamp = datetime(2024, 1, 10, 15, 45, 0)
        branch = BranchInfo(
            name="feature/new-feature",
            last_commit_hash="xyz789",
            last_commit_timestamp=timestamp,
            is_stale=True
        )
        
        assert branch.name == "feature/new-feature"
        assert branch.last_commit_hash == "xyz789"
        assert branch.last_commit_timestamp == timestamp
        assert branch.is_stale is True
    
    def test_branch_info_to_dict(self):
        """Test converting BranchInfo to dictionary."""
        timestamp = datetime(2024, 1, 10, 15, 45, 0)
        branch = BranchInfo(
            name="main",
            last_commit_hash="abc123",
            last_commit_timestamp=timestamp
        )
        
        result = branch.to_dict()
        expected = {
            "name": "main",
            "last_commit_hash": "abc123",
            "last_commit_timestamp": "2024-01-10T15:45:00",
            "is_stale": False
        }
        assert result == expected


class TestPRMetrics:
    """Test PRMetrics dataclass."""
    
    def test_pr_metrics_creation(self):
        """Test creating PRMetrics."""
        metrics = PRMetrics(
            total_prs=25,
            lead_time_p50=24.5,
            lead_time_p75=48.0,
            change_size_p50=150,
            change_size_p75=300,
            weekly_pr_counts={"2024-W02": 5, "2024-W03": 8},
            top_files=[{"file": "src/main.py", "changes": 15}]
        )
        
        assert metrics.total_prs == 25
        assert metrics.lead_time_p50 == 24.5
        assert metrics.lead_time_p75 == 48.0
        assert metrics.change_size_p50 == 150
        assert metrics.change_size_p75 == 300
        assert metrics.weekly_pr_counts == {"2024-W02": 5, "2024-W03": 8}
        assert metrics.top_files == [{"file": "src/main.py", "changes": 15}]
    
    def test_pr_metrics_to_dict(self):
        """Test converting PRMetrics to dictionary."""
        metrics = PRMetrics(
            total_prs=10,
            lead_time_p50=12.0,
            lead_time_p75=24.0,
            change_size_p50=100,
            change_size_p75=200,
            weekly_pr_counts={"2024-W01": 3},
            top_files=[{"file": "test.py", "changes": 5}]
        )
        
        result = metrics.to_dict()
        expected = {
            "total_prs": 10,
            "lead_time_p50": 12.0,
            "lead_time_p75": 24.0,
            "change_size_p50": 100,
            "change_size_p75": 200,
            "weekly_pr_counts": {"2024-W01": 3},
            "top_files": [{"file": "test.py", "changes": 5}]
        }
        assert result == expected


class TestAnalysisState:
    """Test AnalysisState TypedDict and helper functions."""
    
    def test_create_initial_state(self):
        """Test creating initial analysis state."""
        config = {"period_days": 7, "stale_days": 14}
        cache_path = Path("/tmp/cache/repo")
        
        state = create_initial_state(
            config=config,
            repository_url="https://github.com/user/repo.git",
            repository_name="repo",
            branch="main",
            cache_path=cache_path
        )
        
        # Check configuration
        assert state["config"] == config
        assert state["repository_url"] == "https://github.com/user/repo.git"
        assert state["repository_name"] == "repo"
        assert state["branch"] == "main"
        assert state["cache_path"] == cache_path
        
        # Check initial empty data
        assert state["merge_commits"] == []
        assert state["branches"] == []
        assert state["diff_stats"] == []
        assert state["pr_metrics"] is None
        assert state["stale_branches"] == []
        
        # Check initial report sections
        assert state["executive_summary"] is None
        assert state["tables_markdown"] is None
        assert state["org_trends"] is None
        
        # Check initial processing status
        assert state["sync_completed"] is False
        assert state["collect_completed"] is False
        assert state["metrics_completed"] is False
        assert state["stale_completed"] is False
        assert state["tables_completed"] is False
        assert state["exec_summary_completed"] is False
        assert state["org_trend_completed"] is False
        
        # Check initial error tracking
        assert state["errors"] == []