"""Unit tests for LangGraph workflow nodes."""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from git_batch_analyzer.workflow.nodes import sync_node, collect_node, metrics_node, stale_node
from git_batch_analyzer.types import AnalysisState, ToolResponse, create_initial_state


class TestSyncNode:
    """Test cases for sync_node."""
    
    def test_sync_node_success_new_repo(self):
        """Test successful sync with new repository."""
        # Create test state
        state = create_initial_state(
            config={"fetch_depth": 100},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        
        with patch('git_batch_analyzer.workflow.nodes.GitTool') as mock_git_tool_class:
            mock_git_tool = Mock()
            mock_git_tool_class.return_value = mock_git_tool
            
            # Mock repository doesn't exist
            with patch.object(Path, 'exists', return_value=False):
                # Mock successful clone and fetch
                mock_git_tool.clone.return_value = ToolResponse.success_response({"message": "cloned"})
                mock_git_tool.fetch.return_value = ToolResponse.success_response({"message": "fetched"})
                
                result = sync_node(state)
                
                # Verify calls
                mock_git_tool.clone.assert_called_once_with("https://github.com/test/repo.git", depth=100)
                mock_git_tool.fetch.assert_called_once_with("main")
                
                # Verify result
                assert result["sync_completed"] is True
                assert "errors" not in result or not result["errors"]
    
    def test_sync_node_success_existing_repo(self):
        """Test successful sync with existing repository."""
        state = create_initial_state(
            config={"fetch_depth": 200},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="develop",
            cache_path=Path("/tmp/test-repo")
        )
        
        with patch('git_batch_analyzer.workflow.nodes.GitTool') as mock_git_tool_class:
            mock_git_tool = Mock()
            mock_git_tool_class.return_value = mock_git_tool
            
            # Mock repository exists
            with patch.object(Path, 'exists', return_value=True):
                # Mock successful fetch (no clone needed)
                mock_git_tool.fetch.return_value = ToolResponse.success_response({"message": "fetched"})
                
                result = sync_node(state)
                
                # Verify clone was not called
                mock_git_tool.clone.assert_not_called()
                mock_git_tool.fetch.assert_called_once_with("develop")
                
                # Verify result
                assert result["sync_completed"] is True
    
    def test_sync_node_clone_failure(self):
        """Test sync node with clone failure."""
        state = create_initial_state(
            config={"fetch_depth": 100},
            repository_url="https://github.com/test/invalid.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        
        with patch('git_batch_analyzer.workflow.nodes.GitTool') as mock_git_tool_class:
            mock_git_tool = Mock()
            mock_git_tool_class.return_value = mock_git_tool
            
            with patch.object(Path, 'exists', return_value=False):
                # Mock failed clone
                mock_git_tool.clone.return_value = ToolResponse.error_response("Clone failed")
                
                result = sync_node(state)
                
                # Verify result
                assert result["sync_completed"] is False
                assert len(result["errors"]) == 1
                assert "Failed to clone repository" in result["errors"][0]
    
    def test_sync_node_fetch_failure(self):
        """Test sync node with fetch failure."""
        state = create_initial_state(
            config={"fetch_depth": 100},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        
        with patch('git_batch_analyzer.workflow.nodes.GitTool') as mock_git_tool_class:
            mock_git_tool = Mock()
            mock_git_tool_class.return_value = mock_git_tool
            
            with patch.object(Path, 'exists', return_value=True):
                # Mock failed fetch
                mock_git_tool.fetch.return_value = ToolResponse.error_response("Fetch failed")
                
                result = sync_node(state)
                
                # Verify result
                assert result["sync_completed"] is False
                assert len(result["errors"]) == 1
                assert "Failed to fetch updates" in result["errors"][0]


class TestCollectNode:
    """Test cases for collect_node."""
    
    def test_collect_node_success(self):
        """Test successful data collection."""
        state = create_initial_state(
            config={"period_days": 7},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        state["sync_completed"] = True
        
        # Mock data
        mock_commits = [
            {"hash": "abc123", "timestamp": "2024-01-01T12:00:00Z", "message": "Merge PR #1"},
            {"hash": "def456", "timestamp": "2024-01-02T12:00:00Z", "message": "Merge PR #2"}
        ]
        mock_diff_stats = [
            {"files_changed": 3, "insertions": 50, "deletions": 10, "total_changes": 60},
            {"files_changed": 2, "insertions": 30, "deletions": 5, "total_changes": 35}
        ]
        mock_branches = [
            {"name": "main", "last_commit_hash": "abc123", "last_commit_timestamp": "2024-01-01T12:00:00Z"},
            {"name": "feature-1", "last_commit_hash": "def456", "last_commit_timestamp": "2024-01-02T12:00:00Z"}
        ]
        
        with patch('git_batch_analyzer.workflow.nodes.GitTool') as mock_git_tool_class:
            mock_git_tool = Mock()
            mock_git_tool_class.return_value = mock_git_tool
            
            # Mock successful responses
            mock_git_tool.log_merges.return_value = ToolResponse.success_response(mock_commits)
            mock_git_tool.diff_stats.side_effect = [
                ToolResponse.success_response(mock_diff_stats[0]),
                ToolResponse.success_response(mock_diff_stats[1])
            ]
            mock_git_tool.remote_branches.return_value = ToolResponse.success_response(mock_branches)
            
            result = collect_node(state)
            
            # Verify calls
            mock_git_tool.log_merges.assert_called_once_with("main", 7)
            assert mock_git_tool.diff_stats.call_count == 2
            mock_git_tool.remote_branches.assert_called_once()
            
            # Verify result
            assert result["collect_completed"] is True
            assert result["merge_commits"] == mock_commits
            assert result["diff_stats"] == mock_diff_stats
            assert result["branches"] == mock_branches
    
    def test_collect_node_sync_not_completed(self):
        """Test collect node when sync is not completed."""
        state = create_initial_state(
            config={"period_days": 7},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        # sync_completed is False by default
        
        result = collect_node(state)
        
        assert result["collect_completed"] is False
        assert len(result["errors"]) == 1
        assert "Cannot collect data: sync not completed" in result["errors"][0]
    
    def test_collect_node_merge_commits_failure(self):
        """Test collect node with merge commits collection failure."""
        state = create_initial_state(
            config={"period_days": 7},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        state["sync_completed"] = True
        
        with patch('git_batch_analyzer.workflow.nodes.GitTool') as mock_git_tool_class:
            mock_git_tool = Mock()
            mock_git_tool_class.return_value = mock_git_tool
            
            # Mock failed merge commits collection
            mock_git_tool.log_merges.return_value = ToolResponse.error_response("Git log failed")
            
            result = collect_node(state)
            
            assert result["collect_completed"] is False
            assert len(result["errors"]) == 1
            assert "Failed to collect merge commits" in result["errors"][0]


class TestMetricsNode:
    """Test cases for metrics_node."""
    
    def test_metrics_node_success(self):
        """Test successful metrics calculation."""
        state = create_initial_state(
            config={"period_days": 7, "top_k_files": 5},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        state["collect_completed"] = True
        state["merge_commits"] = [
            {"hash": "abc123", "timestamp": "2024-01-01T12:00:00Z", "parents": ["parent1", "parent2"]},
            {"hash": "def456", "timestamp": "2024-01-02T12:00:00Z", "parents": ["parent3", "parent4"]}
        ]
        state["diff_stats"] = [
            {"files_changed": 3, "insertions": 50, "deletions": 10, "total_changes": 60},
            {"files_changed": 2, "insertions": 30, "deletions": 5, "total_changes": 35}
        ]
        
        with patch('git_batch_analyzer.workflow.nodes.CalcTool') as mock_calc_tool_class:
            mock_calc_tool = Mock()
            mock_calc_tool_class.return_value = mock_calc_tool
            
            # Mock successful calculations
            mock_calc_tool.lead_time.return_value = ToolResponse.success_response({
                "count": 2, "p50": 24.0, "p75": 36.0
            })
            mock_calc_tool.percentile.side_effect = [
                ToolResponse.success_response(47.5),  # 50th percentile
                ToolResponse.success_response(57.5)   # 75th percentile
            ]
            mock_calc_tool.group_by_iso_week.return_value = ToolResponse.success_response({
                "2024-W01": [state["merge_commits"][0]],
                "2024-W01": [state["merge_commits"][1]]
            })
            
            result = metrics_node(state)
            
            # Verify calls
            mock_calc_tool.lead_time.assert_called_once_with(state["merge_commits"])
            assert mock_calc_tool.percentile.call_count == 2
            mock_calc_tool.group_by_iso_week.assert_called_once_with(state["merge_commits"])
            
            # Verify result
            assert result["metrics_completed"] is True
            pr_metrics = result["pr_metrics"]
            assert pr_metrics["total_prs"] == 2
            assert pr_metrics["lead_time_p50"] == 24.0
            assert pr_metrics["lead_time_p75"] == 36.0
            assert pr_metrics["change_size_p50"] == 47
            assert pr_metrics["change_size_p75"] == 57
    
    def test_metrics_node_collect_not_completed(self):
        """Test metrics node when data collection is not completed."""
        state = create_initial_state(
            config={"period_days": 7},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        # collect_completed is False by default
        
        result = metrics_node(state)
        
        assert result["metrics_completed"] is False
        assert len(result["errors"]) == 1
        assert "Cannot calculate metrics: data collection not completed" in result["errors"][0]
    
    def test_metrics_node_lead_time_failure(self):
        """Test metrics node with lead time calculation failure."""
        state = create_initial_state(
            config={"period_days": 7},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        state["collect_completed"] = True
        state["merge_commits"] = []
        state["diff_stats"] = []
        
        with patch('git_batch_analyzer.workflow.nodes.CalcTool') as mock_calc_tool_class:
            mock_calc_tool = Mock()
            mock_calc_tool_class.return_value = mock_calc_tool
            
            # Mock failed lead time calculation
            mock_calc_tool.lead_time.return_value = ToolResponse.error_response("Lead time calculation failed")
            
            result = metrics_node(state)
            
            assert result["metrics_completed"] is False
            assert len(result["errors"]) == 1
            assert "Failed to calculate lead time" in result["errors"][0]


class TestStaleNode:
    """Test cases for stale_node."""
    
    def test_stale_node_success(self):
        """Test successful stale branch identification."""
        # Create timestamps
        now = datetime.now(timezone.utc)
        recent_time = now - timedelta(days=2)
        stale_time = now - timedelta(days=10)
        
        state = create_initial_state(
            config={"stale_days": 7},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        state["collect_completed"] = True
        state["branches"] = [
            {
                "name": "main",
                "last_commit_hash": "abc123",
                "last_commit_timestamp": recent_time.isoformat(),
                "is_stale": False
            },
            {
                "name": "old-feature",
                "last_commit_hash": "def456",
                "last_commit_timestamp": stale_time.isoformat(),
                "is_stale": False
            }
        ]
        
        result = stale_node(state)
        
        # Verify result
        assert result["stale_completed"] is True
        stale_branches = result["stale_branches"]
        assert len(stale_branches) == 1
        assert stale_branches[0]["name"] == "old-feature"
        assert stale_branches[0]["is_stale"] is True
    
    def test_stale_node_collect_not_completed(self):
        """Test stale node when data collection is not completed."""
        state = create_initial_state(
            config={"stale_days": 7},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        # collect_completed is False by default
        
        result = stale_node(state)
        
        assert result["stale_completed"] is False
        assert len(result["errors"]) == 1
        assert "Cannot identify stale branches: data collection not completed" in result["errors"][0]
    
    def test_stale_node_no_stale_branches(self):
        """Test stale node when no branches are stale."""
        now = datetime.now(timezone.utc)
        recent_time = now - timedelta(days=2)
        
        state = create_initial_state(
            config={"stale_days": 7},
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        state["collect_completed"] = True
        state["branches"] = [
            {
                "name": "main",
                "last_commit_hash": "abc123",
                "last_commit_timestamp": recent_time.isoformat(),
                "is_stale": False
            },
            {
                "name": "feature-1",
                "last_commit_hash": "def456",
                "last_commit_timestamp": recent_time.isoformat(),
                "is_stale": False
            }
        ]
        
        result = stale_node(state)
        
        # Verify result
        assert result["stale_completed"] is True
        assert len(result["stale_branches"]) == 0
    
    def test_stale_node_uses_period_days_default(self):
        """Test stale node uses period_days when stale_days not specified."""
        now = datetime.now(timezone.utc)
        stale_time = now - timedelta(days=10)
        
        state = create_initial_state(
            config={"period_days": 8},  # No stale_days specified
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-repo")
        )
        state["collect_completed"] = True
        state["branches"] = [
            {
                "name": "old-branch",
                "last_commit_hash": "abc123",
                "last_commit_timestamp": stale_time.isoformat(),
                "is_stale": False
            }
        ]
        
        result = stale_node(state)
        
        # Should identify as stale since 10 days > 8 days (period_days)
        assert result["stale_completed"] is True
        assert len(result["stale_branches"]) == 1
        assert result["stale_branches"][0]["name"] == "old-branch"