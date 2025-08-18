"""Tests for report generation workflow nodes."""

import pytest
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from datetime import datetime, timezone

from git_batch_analyzer.workflow.nodes import (
    tables_node, exec_summary_node, org_trend_node, assembler_node
)
from git_batch_analyzer.types import AnalysisState, create_initial_state


@pytest.fixture
def sample_state():
    """Create a sample analysis state for testing."""
    config = {
        "period_days": 7,
        "stale_days": 14,
        "top_k_files": 10,
        "output_file": "test_report.md",
        "llm": {
            "enabled": True,
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7
        }
    }
    
    state = create_initial_state(
        config=config,
        repository_url="https://github.com/test/repo.git",
        repository_name="test-repo",
        branch="main",
        cache_path=Path("/tmp/test-repo")
    )
    
    # Set up completed prerequisites
    state["sync_completed"] = True
    state["collect_completed"] = True
    state["metrics_completed"] = True
    state["stale_completed"] = True
    
    # Add sample PR metrics
    state["pr_metrics"] = {
        "total_prs": 15,
        "lead_time_p50": 24.5,
        "lead_time_p75": 48.2,
        "change_size_p50": 125,
        "change_size_p75": 350,
        "weekly_pr_counts": {
            "2024-W01": 3,
            "2024-W02": 5,
            "2024-W03": 7
        },
        "top_files": [
            {"item": "src/main.py", "count": 8},
            {"item": "tests/test_main.py", "count": 5},
            {"item": "README.md", "count": 3}
        ]
    }
    
    # Add sample stale branches
    state["stale_branches"] = [
        {
            "name": "feature/old-branch",
            "last_commit_hash": "abc123def456",
            "last_commit_timestamp": "2024-01-01T12:00:00+00:00",
            "is_stale": True
        },
        {
            "name": "bugfix/ancient-fix",
            "last_commit_hash": "def456ghi789",
            "last_commit_timestamp": "2023-12-15T10:30:00+00:00",
            "is_stale": True
        }
    ]
    
    return state


class TestTablesNode:
    """Tests for tables_node function."""
    
    def test_tables_node_success(self, sample_state):
        """Test successful table generation."""
        result = tables_node(sample_state)
        
        assert result["tables_completed"] is True
        assert "tables_markdown" in result
        assert isinstance(result["tables_markdown"], str)
        assert len(result["tables_markdown"]) > 0
        
        # Check that tables contain expected content
        tables_content = result["tables_markdown"]
        assert "test-repo - PR Metrics" in tables_content
        assert "Total PRs" in tables_content
        assert "15" in tables_content  # total_prs value
        assert "24.5" in tables_content  # lead_time_p50 value
        
        # Check weekly counts table
        assert "test-repo - Weekly PR Counts" in tables_content
        assert "2024-W01" in tables_content
        assert "2024-W02" in tables_content
        
        # Check top files table
        assert "test-repo - Top Changed Files" in tables_content
        assert "src/main.py" in tables_content
        
        # Check stale branches table
        assert "test-repo - Stale Branches" in tables_content
        assert "feature/old-branch" in tables_content
    
    def test_tables_node_missing_prerequisites(self, sample_state):
        """Test tables_node with missing prerequisites."""
        sample_state["metrics_completed"] = False
        
        result = tables_node(sample_state)
        
        assert result["tables_completed"] is False
        assert "errors" in result
        assert any("metrics" in error for error in result["errors"])
    
    def test_tables_node_empty_data(self, sample_state):
        """Test tables_node with empty data."""
        sample_state["pr_metrics"] = {
            "total_prs": 0,
            "lead_time_p50": 0.0,
            "lead_time_p75": 0.0,
            "change_size_p50": 0,
            "change_size_p75": 0,
            "weekly_pr_counts": {},
            "top_files": []
        }
        sample_state["stale_branches"] = []
        
        result = tables_node(sample_state)
        
        assert result["tables_completed"] is True
        assert "tables_markdown" in result
        
        # Should still contain metrics table even with zero values
        tables_content = result["tables_markdown"]
        assert "test-repo - PR Metrics" in tables_content
        assert "Total PRs" in tables_content
    
    @patch('git_batch_analyzer.workflow.nodes.MdTool')
    def test_tables_node_md_tool_error(self, mock_md_tool, sample_state):
        """Test tables_node with MdTool error."""
        mock_instance = Mock()
        mock_instance.render_metrics_table.return_value.success = False
        mock_instance.render_metrics_table.return_value.error = "Render error"
        mock_md_tool.return_value = mock_instance
        
        result = tables_node(sample_state)
        
        assert result["tables_completed"] is False
        assert "errors" in result
        assert any("Render error" in error for error in result["errors"])


class TestExecSummaryNode:
    """Tests for exec_summary_node function."""
    
    @patch('git_batch_analyzer.workflow.nodes.LLMTool')
    def test_exec_summary_node_success(self, mock_llm_tool, sample_state):
        """Test successful executive summary generation."""
        mock_instance = Mock()
        mock_instance.generate_executive_summary.return_value.success = True
        mock_instance.generate_executive_summary.return_value.data = "Test executive summary content."
        mock_llm_tool.return_value = mock_instance
        
        result = exec_summary_node(sample_state)
        
        assert result["exec_summary_completed"] is True
        assert result["executive_summary"] == "Test executive summary content."
        
        # Verify LLM tool was called with correct parameters (including new parameters)
        mock_llm_tool.assert_called_once_with(
            provider="openai",
            model="gpt-3.5-turbo",
            temperature=0.7,
            api_key=None,
            base_url=None,
            max_tokens=None
        )
        mock_instance.generate_executive_summary.assert_called_once()
    
    def test_exec_summary_node_llm_disabled(self, sample_state):
        """Test exec_summary_node with LLM disabled."""
        sample_state["config"]["llm"]["enabled"] = False
        
        result = exec_summary_node(sample_state)
        
        assert result["exec_summary_completed"] is True
        assert result["executive_summary"] is None
    
    def test_exec_summary_node_missing_prerequisites(self, sample_state):
        """Test exec_summary_node with missing prerequisites."""
        sample_state["metrics_completed"] = False
        
        result = exec_summary_node(sample_state)
        
        assert result["exec_summary_completed"] is False
        assert "errors" in result
        assert any("metrics not completed" in error for error in result["errors"])
    
    @patch('git_batch_analyzer.workflow.nodes.LLMTool')
    def test_exec_summary_node_llm_init_error(self, mock_llm_tool, sample_state):
        """Test exec_summary_node with LLM initialization error."""
        mock_llm_tool.side_effect = ValueError("API key not found")
        
        result = exec_summary_node(sample_state)
        
        assert result["exec_summary_completed"] is False
        assert "errors" in result
        assert any("Failed to initialize LLM tool" in error for error in result["errors"])
    
    @patch('git_batch_analyzer.workflow.nodes.LLMTool')
    def test_exec_summary_node_generation_error(self, mock_llm_tool, sample_state):
        """Test exec_summary_node with generation error."""
        mock_instance = Mock()
        mock_instance.generate_executive_summary.return_value.success = False
        mock_instance.generate_executive_summary.return_value.error = "Generation failed"
        mock_llm_tool.return_value = mock_instance
        
        result = exec_summary_node(sample_state)
        
        assert result["exec_summary_completed"] is False
        assert "errors" in result
        assert any("Generation failed" in error for error in result["errors"])


class TestOrgTrendNode:
    """Tests for org_trend_node function."""
    
    @patch('git_batch_analyzer.workflow.nodes.LLMTool')
    def test_org_trend_node_success(self, mock_llm_tool, sample_state):
        """Test successful organizational trends generation."""
        mock_instance = Mock()
        mock_instance.generate_organizational_trends.return_value.success = True
        mock_instance.generate_organizational_trends.return_value.data = "Test organizational trends analysis."
        mock_llm_tool.return_value = mock_instance
        
        result = org_trend_node(sample_state)
        
        assert result["org_trend_completed"] is True
        assert result["org_trends"] == "Test organizational trends analysis."
        
        # Verify LLM tool was called with aggregated data
        mock_instance.generate_organizational_trends.assert_called_once()
        call_args = mock_instance.generate_organizational_trends.call_args[0][0]
        
        # Check that weekly aggregated data was properly formatted
        assert isinstance(call_args, list)
        assert len(call_args) == 3  # Three weeks of data
        assert all("week" in item for item in call_args)
        assert all("repository" in item for item in call_args)
        assert all("pr_count" in item for item in call_args)
    
    def test_org_trend_node_llm_disabled(self, sample_state):
        """Test org_trend_node with LLM disabled."""
        sample_state["config"]["llm"]["enabled"] = False
        
        result = org_trend_node(sample_state)
        
        assert result["org_trend_completed"] is True
        assert result["org_trends"] is None
    
    def test_org_trend_node_missing_prerequisites(self, sample_state):
        """Test org_trend_node with missing prerequisites."""
        sample_state["metrics_completed"] = False
        
        result = org_trend_node(sample_state)
        
        assert result["org_trend_completed"] is False
        assert "errors" in result
        assert any("metrics not completed" in error for error in result["errors"])
    
    @patch('git_batch_analyzer.workflow.nodes.LLMTool')
    def test_org_trend_node_generation_error(self, mock_llm_tool, sample_state):
        """Test org_trend_node with generation error."""
        mock_instance = Mock()
        mock_instance.generate_organizational_trends.return_value.success = False
        mock_instance.generate_organizational_trends.return_value.error = "Trends generation failed"
        mock_llm_tool.return_value = mock_instance
        
        result = org_trend_node(sample_state)
        
        assert result["org_trend_completed"] is False
        assert "errors" in result
        assert any("Trends generation failed" in error for error in result["errors"])


class TestAssemblerNode:
    """Tests for assembler_node function."""
    
    @patch("builtins.open", new_callable=mock_open)
    @patch('git_batch_analyzer.workflow.nodes.MdTool')
    def test_assembler_node_success(self, mock_md_tool, mock_file, sample_state):
        """Test successful report assembly."""
        # Set up completed report sections
        sample_state["tables_completed"] = True
        sample_state["exec_summary_completed"] = True
        sample_state["org_trend_completed"] = True
        sample_state["executive_summary"] = "Test executive summary."
        sample_state["tables_markdown"] = "Test tables content."
        sample_state["org_trends"] = "Test organizational trends."
        
        # Mock MdTool responses
        mock_instance = Mock()
        
        # Mock render_section calls
        mock_instance.render_section.side_effect = [
            Mock(success=True, data="## Executive Summary\n\nTest executive summary."),
            Mock(success=True, data="## Repository Metrics\n\nTest tables content."),
            Mock(success=True, data="## Organizational Trends\n\nTest organizational trends.")
        ]
        
        # Mock combine_sections call
        mock_instance.combine_sections.return_value = Mock(
            success=True, 
            data="# Git Analysis Report - test-repo\n\nGenerated on: 2024-01-01 12:00:00 UTC\n\n## Executive Summary\n\nTest executive summary.\n\n## Repository Metrics\n\nTest tables content.\n\n## Organizational Trends\n\nTest organizational trends."
        )
        
        mock_md_tool.return_value = mock_instance
        
        result = assembler_node(sample_state)
        
        assert result["assembler_completed"] is True
        assert "final_report" in result
        
        # Verify file was written
        mock_file.assert_called_once_with("test_report.md", "w", encoding="utf-8")
        mock_file().write.assert_called_once()
        
        # Verify report structure
        final_report = result["final_report"]
        assert "# Git Analysis Report - test-repo" in final_report
        assert "Generated on:" in final_report
        assert "## Executive Summary" in final_report
        assert "## Repository Metrics" in final_report
        assert "## Organizational Trends" in final_report
    
    def test_assembler_node_missing_prerequisites(self, sample_state):
        """Test assembler_node with missing prerequisites."""
        sample_state["tables_completed"] = False
        
        result = assembler_node(sample_state)
        
        assert result["assembler_completed"] is False
        assert "errors" in result
        assert any("not all sections completed" in error for error in result["errors"])
    
    @patch("builtins.open", new_callable=mock_open)
    @patch('git_batch_analyzer.workflow.nodes.MdTool')
    def test_assembler_node_partial_content(self, mock_md_tool, mock_file, sample_state):
        """Test assembler_node with only some sections available."""
        # Set up completed status but only tables content
        sample_state["tables_completed"] = True
        sample_state["exec_summary_completed"] = True  # Completed but no content
        sample_state["org_trend_completed"] = True     # Completed but no content
        sample_state["executive_summary"] = None       # LLM disabled
        sample_state["tables_markdown"] = "Test tables content."
        sample_state["org_trends"] = None             # LLM disabled
        
        # Mock MdTool responses
        mock_instance = Mock()
        mock_instance.render_section.return_value = Mock(
            success=True, 
            data="## Repository Metrics\n\nTest tables content."
        )
        mock_instance.combine_sections.return_value = Mock(
            success=True, 
            data="# Git Analysis Report - test-repo\n\nGenerated on: 2024-01-01 12:00:00 UTC\n\n## Repository Metrics\n\nTest tables content."
        )
        mock_md_tool.return_value = mock_instance
        
        result = assembler_node(sample_state)
        
        assert result["assembler_completed"] is True
        assert "final_report" in result
        
        # Should only include available sections
        final_report = result["final_report"]
        assert "# Git Analysis Report - test-repo" in final_report
        assert "## Repository Metrics" in final_report
    
    @patch('git_batch_analyzer.workflow.nodes.MdTool')
    @patch("builtins.open", side_effect=IOError("Permission denied"))
    def test_assembler_node_file_write_error(self, mock_open, mock_md_tool, sample_state):
        """Test assembler_node with file write error."""
        # Set up completed report sections
        sample_state["tables_completed"] = True
        sample_state["exec_summary_completed"] = True
        sample_state["org_trend_completed"] = True
        sample_state["tables_markdown"] = "Test content."
        
        # Mock MdTool
        mock_instance = Mock()
        mock_instance.render_section.return_value = Mock(success=True, data="Test section")
        mock_instance.combine_sections.return_value = Mock(success=True, data="Test report")
        mock_md_tool.return_value = mock_instance
        
        result = assembler_node(sample_state)
        
        assert result["assembler_completed"] is False
        assert "errors" in result
        assert any("Permission denied" in error for error in result["errors"])
    
    @patch('git_batch_analyzer.workflow.nodes.MdTool')
    def test_assembler_node_md_tool_error(self, mock_md_tool, sample_state):
        """Test assembler_node with MdTool error."""
        # Set up completed report sections
        sample_state["tables_completed"] = True
        sample_state["exec_summary_completed"] = True
        sample_state["org_trend_completed"] = True
        sample_state["tables_markdown"] = "Test content."
        
        # Mock MdTool error
        mock_instance = Mock()
        mock_instance.render_section.return_value = Mock(success=True, data="Test section")
        mock_instance.combine_sections.return_value = Mock(success=False, error="Combine error")
        mock_md_tool.return_value = mock_instance
        
        result = assembler_node(sample_state)
        
        assert result["assembler_completed"] is False
        assert "errors" in result
        assert any("Combine error" in error for error in result["errors"])


class TestReportNodesIntegration:
    """Integration tests for report generation nodes."""
    
    @patch("builtins.open", new_callable=mock_open)
    @patch('git_batch_analyzer.workflow.nodes.LLMTool')
    def test_full_report_generation_flow(self, mock_llm_tool, mock_file, sample_state):
        """Test complete flow through all report generation nodes."""
        # Mock LLM tool
        mock_llm_instance = Mock()
        mock_llm_instance.generate_executive_summary.return_value = Mock(
            success=True, data="Executive summary content."
        )
        mock_llm_instance.generate_organizational_trends.return_value = Mock(
            success=True, data="Organizational trends content."
        )
        mock_llm_tool.return_value = mock_llm_instance
        
        # Run through all nodes in sequence
        result1 = tables_node(sample_state)
        assert result1["tables_completed"] is True
        sample_state.update(result1)
        
        result2 = exec_summary_node(sample_state)
        assert result2["exec_summary_completed"] is True
        sample_state.update(result2)
        
        result3 = org_trend_node(sample_state)
        assert result3["org_trend_completed"] is True
        sample_state.update(result3)
        
        result4 = assembler_node(sample_state)
        assert result4["assembler_completed"] is True
        
        # Verify final report was written
        mock_file.assert_called_once_with("test_report.md", "w", encoding="utf-8")
        
        # Verify all sections are present in final report
        final_report = result4["final_report"]
        assert "# Git Analysis Report - test-repo" in final_report
        assert "Executive Summary" in final_report
        assert "Repository Metrics" in final_report
        assert "Organizational Trends" in final_report
    
    @patch("builtins.open", new_callable=mock_open)
    def test_report_generation_with_llm_disabled(self, mock_file, sample_state):
        """Test report generation with LLM disabled."""
        sample_state["config"]["llm"]["enabled"] = False
        
        # Run through all nodes
        result1 = tables_node(sample_state)
        sample_state.update(result1)
        
        result2 = exec_summary_node(sample_state)
        sample_state.update(result2)
        
        result3 = org_trend_node(sample_state)
        sample_state.update(result3)
        
        result4 = assembler_node(sample_state)
        
        # All should complete successfully
        assert result1["tables_completed"] is True
        assert result2["exec_summary_completed"] is True
        assert result3["org_trend_completed"] is True
        assert result4["assembler_completed"] is True
        
        # Executive summary and org trends should be None
        assert sample_state["executive_summary"] is None
        assert sample_state["org_trends"] is None
        
        # But tables should be present
        assert sample_state["tables_markdown"] is not None
        
        # Final report should still be generated
        final_report = result4["final_report"]
        assert "# Git Analysis Report - test-repo" in final_report
        assert "Repository Metrics" in final_report