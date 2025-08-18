"""Integration tests for the complete LangGraph workflow."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime, timezone, timedelta

from git_batch_analyzer.workflow.graph import create_workflow, process_repositories
from git_batch_analyzer.types import create_initial_state, AnalysisState


class TestWorkflowIntegration:
    """Test the complete workflow execution."""
    
    def test_create_workflow_returns_compiled_graph(self):
        """Test that create_workflow returns a compiled LangGraph."""
        workflow = create_workflow()
        
        # Verify it's a compiled graph
        assert hasattr(workflow, 'invoke')
        assert hasattr(workflow, 'stream')
        
    @patch('builtins.open', create=True)
    @patch('git_batch_analyzer.workflow.nodes.GitTool')
    @patch('git_batch_analyzer.workflow.nodes.CalcTool')
    @patch('git_batch_analyzer.workflow.nodes.MdTool')
    @patch('git_batch_analyzer.workflow.nodes.LLMTool')
    def test_successful_workflow_execution(self, mock_llm_tool, mock_md_tool, mock_calc_tool, mock_git_tool, mock_open):
        """Test complete workflow execution with successful nodes."""
        # Setup file writing mock
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Setup mocks for successful execution
        self._setup_successful_mocks(mock_git_tool, mock_calc_tool, mock_md_tool, mock_llm_tool)
        
        # Create workflow and initial state
        workflow = create_workflow()
        initial_state = self._create_test_state()
        
        # Execute workflow
        final_state = workflow.invoke(initial_state)
        
        # Verify all nodes completed successfully
        assert final_state["sync_completed"] is True
        assert final_state["collect_completed"] is True
        assert final_state["metrics_completed"] is True
        assert final_state["stale_completed"] is True
        assert final_state["tables_completed"] is True
        assert final_state["exec_summary_completed"] is True
        assert final_state["org_trend_completed"] is True
        
        # Verify final report was generated (this indicates assembler completed)
        assert final_state.get("final_report") is not None
        assert "Git Analysis Report" in final_state["final_report"]
        
    @patch('git_batch_analyzer.workflow.nodes.GitTool')
    def test_workflow_stops_on_sync_failure(self, mock_git_tool):
        """Test that workflow stops when sync node fails."""
        # Setup git tool to fail on clone
        mock_git_instance = Mock()
        mock_git_instance.clone.return_value = Mock(success=False, error="Clone failed")
        mock_git_tool.return_value = mock_git_instance
        
        # Create workflow and initial state
        workflow = create_workflow()
        initial_state = self._create_test_state()
        
        # Execute workflow
        final_state = workflow.invoke(initial_state)
        
        # Verify workflow stopped at sync
        assert final_state["sync_completed"] is False
        assert "collect_completed" not in final_state or final_state["collect_completed"] is False
        assert len(final_state["errors"]) > 0
        assert "Clone failed" in str(final_state["errors"])
        
    @patch('git_batch_analyzer.workflow.nodes.GitTool')
    @patch('git_batch_analyzer.workflow.nodes.CalcTool')
    def test_workflow_stops_on_collect_failure(self, mock_calc_tool, mock_git_tool):
        """Test that workflow stops when collect node fails."""
        # Setup successful sync but failed collect
        mock_git_instance = Mock()
        mock_git_instance.clone.return_value = Mock(success=True)
        mock_git_instance.fetch.return_value = Mock(success=True)
        mock_git_instance.log_merges.return_value = Mock(success=False, error="Log failed")
        mock_git_tool.return_value = mock_git_instance
        
        # Create workflow and initial state
        workflow = create_workflow()
        initial_state = self._create_test_state()
        
        # Execute workflow
        final_state = workflow.invoke(initial_state)
        
        # Verify workflow stopped at collect
        assert final_state["sync_completed"] is True
        assert final_state["collect_completed"] is False
        assert "metrics_completed" not in final_state or final_state["metrics_completed"] is False
        assert len(final_state["errors"]) > 0
        
    @patch('builtins.open', create=True)
    @patch('git_batch_analyzer.workflow.nodes.GitTool')
    @patch('git_batch_analyzer.workflow.nodes.CalcTool')
    @patch('git_batch_analyzer.workflow.nodes.MdTool')
    def test_workflow_continues_with_llm_disabled(self, mock_md_tool, mock_calc_tool, mock_git_tool, mock_open):
        """Test that workflow completes successfully when LLM is disabled."""
        # Setup file writing mock
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Setup mocks for successful execution (no LLM mocking needed)
        self._setup_successful_mocks_no_llm(mock_git_tool, mock_calc_tool, mock_md_tool)
        
        # Create workflow and initial state with LLM disabled
        workflow = create_workflow()
        initial_state = self._create_test_state()
        initial_state["config"]["llm"] = {"enabled": False}
        
        # Execute workflow
        final_state = workflow.invoke(initial_state)
        
        # Verify workflow completed successfully
        assert final_state["sync_completed"] is True
        assert final_state["collect_completed"] is True
        assert final_state["metrics_completed"] is True
        assert final_state["stale_completed"] is True
        assert final_state["tables_completed"] is True
        assert final_state["exec_summary_completed"] is True  # Should complete but with None summary
        assert final_state["org_trend_completed"] is True  # Should complete but with None trends
        
        # Verify LLM sections are None but report still generated
        assert final_state["executive_summary"] is None
        assert final_state["org_trends"] is None
        assert final_state.get("final_report") is not None
        
    def test_process_repositories_handles_multiple_repos(self):
        """Test processing multiple repositories with mixed success/failure."""
        repositories = [
            {"url": "https://github.com/user/repo1.git", "name": "repo1"},
            {"url": "https://github.com/user/repo2.git", "name": "repo2"},
            {"url": "https://github.com/user/repo3.git", "name": "repo3"}
        ]
        config = {
            "cache_dir": "/tmp/test-cache",
            "period_days": 7,
            "llm": {"enabled": False}
        }
        
        # Mock the workflow to simulate mixed results
        with patch('git_batch_analyzer.workflow.graph.create_workflow') as mock_create_workflow:
            mock_workflow = Mock()
            
            # Setup different results for each repository
            def mock_invoke(state):
                repo_name = state["repository_name"]
                if repo_name == "repo1":
                    # Successful
                    return {**state, "assembler_completed": True, "errors": []}
                elif repo_name == "repo2":
                    # Failed
                    return {**state, "assembler_completed": False, "errors": ["Test error"]}
                else:
                    # Exception during processing
                    raise Exception("Unexpected error")
            
            mock_workflow.invoke.side_effect = mock_invoke
            mock_create_workflow.return_value = mock_workflow
            
            # Process repositories
            results = process_repositories(repositories, config)
            
            # Verify results
            assert len(results["successful_repositories"]) == 1
            assert len(results["failed_repositories"]) == 2
            assert len(results["errors"]) >= 2
            
            # Check successful repository
            assert results["successful_repositories"][0]["name"] == "repo1"
            
            # Check failed repositories
            failed_names = [repo["name"] for repo in results["failed_repositories"]]
            assert "repo2" in failed_names
            assert "repo3" in failed_names
    
    def test_process_repositories_continues_on_individual_failures(self):
        """Test that processing continues even when individual repositories fail."""
        repositories = [
            {"url": "https://github.com/user/good-repo.git"},
            {"url": "https://github.com/user/bad-repo.git"}
        ]
        config = {"cache_dir": "/tmp/test-cache"}
        
        with patch('git_batch_analyzer.workflow.graph.create_workflow') as mock_create_workflow:
            mock_workflow = Mock()
            
            def mock_invoke(state):
                if "good-repo" in state["repository_name"]:
                    return {**state, "assembler_completed": True, "errors": []}
                else:
                    return {**state, "assembler_completed": False, "errors": ["Repository failed"]}
            
            mock_workflow.invoke.side_effect = mock_invoke
            mock_create_workflow.return_value = mock_workflow
            
            results = process_repositories(repositories, config)
            
            # Should have processed both repositories
            assert len(results["successful_repositories"]) == 1
            assert len(results["failed_repositories"]) == 1
            assert results["successful_repositories"][0]["name"] == "good-repo"
            assert results["failed_repositories"][0]["name"] == "bad-repo"
    
    def _create_test_state(self) -> AnalysisState:
        """Create a test analysis state."""
        config = {
            "period_days": 7,
            "cache_dir": "/tmp/test-cache",
            "output_file": "test-report.md",
            "llm": {
                "enabled": True,
                "provider": "openai",
                "model": "gpt-3.5-turbo",
                "temperature": 0.7
            }
        }
        
        return create_initial_state(
            config=config,
            repository_url="https://github.com/test/repo.git",
            repository_name="test-repo",
            branch="main",
            cache_path=Path("/tmp/test-cache/test-repo")
        )
    
    def _setup_successful_mocks(self, mock_git_tool, mock_calc_tool, mock_md_tool, mock_llm_tool):
        """Setup mocks for successful workflow execution."""
        # Git tool mocks
        mock_git_instance = Mock()
        mock_git_instance.clone.return_value = Mock(success=True)
        mock_git_instance.fetch.return_value = Mock(success=True)
        mock_git_instance.log_merges.return_value = Mock(
            success=True,
            data=[{
                "hash": "abc123",
                "timestamp": "2024-01-01T12:00:00Z",
                "message": "Merge PR #1",
                "parents": ["def456", "ghi789"],
                "author": "test@example.com"
            }]
        )
        mock_git_instance.diff_stats.return_value = Mock(
            success=True,
            data={"files_changed": 2, "insertions": 10, "deletions": 5, "total_changes": 15}
        )
        mock_git_instance.remote_branches.return_value = Mock(
            success=True,
            data=[{
                "name": "main",
                "last_commit_hash": "abc123",
                "last_commit_timestamp": "2024-01-01T12:00:00Z"
            }]
        )
        mock_git_tool.return_value = mock_git_instance
        
        # Calc tool mocks
        mock_calc_instance = Mock()
        mock_calc_instance.lead_time.return_value = Mock(
            success=True,
            data={"p50": 24.0, "p75": 48.0}
        )
        mock_calc_instance.percentile.return_value = Mock(success=True, data=10)
        mock_calc_instance.group_by_iso_week.return_value = Mock(
            success=True,
            data={"2024-W01": [{"hash": "abc123"}]}
        )
        mock_calc_tool.return_value = mock_calc_instance
        
        # Markdown tool mocks
        mock_md_instance = Mock()
        mock_md_instance.render_metrics_table.return_value = Mock(success=True, data="| Metric | Value |")
        mock_md_instance.render_weekly_counts_table.return_value = Mock(success=True, data="| Week | Count |")
        mock_md_instance.render_top_files_table.return_value = Mock(success=True, data="| File | Changes |")
        mock_md_instance.render_stale_branches_table.return_value = Mock(success=True, data="| Branch | Last Commit |")
        mock_md_instance.render_section.return_value = Mock(success=True, data="## Section\nContent")
        mock_md_instance.combine_sections.return_value = Mock(success=True, data="# Git Analysis Report - test-repo\n\nGenerated on: 2024-01-01 12:00:00 UTC\n\n## Repository Metrics\n\nTest tables")
        mock_md_tool.return_value = mock_md_instance
        
        # LLM tool mocks
        mock_llm_instance = Mock()
        mock_llm_instance.generate_executive_summary.return_value = Mock(
            success=True,
            data="Executive summary of the analysis results."
        )
        mock_llm_instance.generate_organizational_trends.return_value = Mock(
            success=True,
            data="Organizational trends and insights."
        )
        mock_llm_tool.return_value = mock_llm_instance
        
        # Mock file writing (this needs to be done in the test method, not here)
    
    def _setup_successful_mocks_no_llm(self, mock_git_tool, mock_calc_tool, mock_md_tool):
        """Setup mocks for successful workflow execution without LLM."""
        # Same as above but without LLM mocks
        self._setup_successful_mocks(mock_git_tool, mock_calc_tool, mock_md_tool, Mock())