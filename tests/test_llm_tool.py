"""Unit tests for LLMTool with mocked LLM responses."""

import os
from unittest.mock import Mock, patch, MagicMock
import pytest

from git_batch_analyzer.tools.llm_tool import LLMTool
from git_batch_analyzer.types import ToolResponse


class TestLLMTool:
    """Test cases for LLMTool class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock environment variable for tests
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            self.llm_tool = LLMTool()
    
    def test_init_with_api_key(self):
        """Test LLMTool initialization with provided API key."""
        with patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI') as mock_chat:
            llm_tool = LLMTool(api_key="custom-key")
            
            assert os.environ["OPENAI_API_KEY"] == "custom-key"
            mock_chat.assert_called_once_with(
                model="gpt-3.5-turbo",
                temperature=0.7
            )
    
    def test_init_with_env_api_key(self):
        """Test LLMTool initialization with environment API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            with patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI') as mock_chat:
                llm_tool = LLMTool()
                
                mock_chat.assert_called_once_with(
                    model="gpt-3.5-turbo",
                    temperature=0.7
                )
    
    def test_init_no_api_key_raises_error(self):
        """Test that initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key not provided"):
                LLMTool()
    
    def test_init_unsupported_provider_raises_error(self):
        """Test that unsupported provider raises error."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with pytest.raises(ValueError, match="Unsupported LLM provider: anthropic"):
                LLMTool(provider="anthropic")
    
    def test_init_custom_parameters(self):
        """Test LLMTool initialization with custom parameters."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI') as mock_chat:
                llm_tool = LLMTool(
                    model="gpt-4",
                    temperature=0.3
                )
                
                mock_chat.assert_called_once_with(
                    model="gpt-4",
                    temperature=0.3
                )
    
    def test_validate_no_source_code_safe_data(self):
        """Test source code validation with safe data."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            safe_data = {
                "total_prs": 10,
                "lead_time_p50": 24.5,
                "weekly_counts": {"2024-W01": 5, "2024-W02": 3}
            }
            
            assert llm_tool._validate_no_source_code(safe_data) is True
    
    def test_validate_no_source_code_detects_python(self):
        """Test source code validation detects Python code."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            unsafe_data = {
                "code": "def hello_world():\n    print('Hello')",
                "total_prs": 10
            }
            
            assert llm_tool._validate_no_source_code(unsafe_data) is False
    
    def test_validate_no_source_code_detects_javascript(self):
        """Test source code validation detects JavaScript code."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            unsafe_data = {
                "script": "function test() { console.log('test'); }",
                "metrics": {"total": 5}
            }
            
            assert llm_tool._validate_no_source_code(unsafe_data) is False
    
    def test_validate_no_source_code_detects_sql(self):
        """Test source code validation detects SQL code."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            unsafe_data = {
                "query": "SELECT * FROM users WHERE id = 1",
                "count": 100
            }
            
            assert llm_tool._validate_no_source_code(unsafe_data) is False
    
    @patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI')
    def test_generate_executive_summary_success(self, mock_chat_class):
        """Test successful executive summary generation."""
        # Setup mock LLM
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "This is a comprehensive executive summary of development metrics showing strong team productivity with 15 total PRs processed. Lead times averaged 24.5 hours at the 50th percentile, indicating efficient code review processes. Change sizes remained manageable with median modifications of 150 lines. Weekly activity shows consistent delivery patterns with peak productivity in week 2. The team demonstrates excellent velocity and code quality maintenance. Overall metrics suggest a well-functioning development workflow with room for minor optimizations in review cycles."
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            pr_metrics = {
                "total_prs": 15,
                "lead_time_p50": 24.5,
                "lead_time_p75": 48.0,
                "change_size_p50": 150,
                "change_size_p75": 300
            }
            
            weekly_data = {
                "2024-W01": 7,
                "2024-W02": 8
            }
            
            response = llm_tool.generate_executive_summary(pr_metrics, weekly_data)
            
            assert response.success is True
            assert "comprehensive executive summary" in response.data
            assert len(response.data.split()) <= 130  # Allow small buffer
            mock_llm.invoke.assert_called_once()
    
    @patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI')
    def test_generate_executive_summary_too_long(self, mock_chat_class):
        """Test executive summary generation with response too long."""
        # Setup mock LLM with very long response
        mock_llm = Mock()
        mock_response = Mock()
        # Generate a response with more than 130 words
        long_response = " ".join(["word"] * 150)
        mock_response.content = long_response
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            pr_metrics = {"total_prs": 10}
            weekly_data = {"2024-W01": 5}
            
            response = llm_tool.generate_executive_summary(pr_metrics, weekly_data)
            
            assert response.success is False
            assert "Generated summary too long" in response.error
    
    @patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI')
    def test_generate_executive_summary_unsafe_data(self, mock_chat_class):
        """Test executive summary generation with unsafe data."""
        mock_chat_class.return_value = Mock()
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            # Data containing source code
            unsafe_pr_metrics = {
                "total_prs": 10,
                "code": "def process_data(): return True"
            }
            
            weekly_data = {"2024-W01": 5}
            
            response = llm_tool.generate_executive_summary(unsafe_pr_metrics, weekly_data)
            
            assert response.success is False
            assert "Safety check failed" in response.error
    
    @patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI')
    def test_generate_executive_summary_llm_error(self, mock_chat_class):
        """Test executive summary generation with LLM error."""
        # Setup mock LLM that raises an exception
        mock_llm = Mock()
        mock_llm.invoke.side_effect = Exception("API rate limit exceeded")
        mock_chat_class.return_value = mock_llm
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            pr_metrics = {"total_prs": 10}
            weekly_data = {"2024-W01": 5}
            
            response = llm_tool.generate_executive_summary(pr_metrics, weekly_data)
            
            assert response.success is False
            assert "Failed to generate executive summary" in response.error
            assert "API rate limit exceeded" in response.error
    
    @patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI')
    def test_generate_organizational_trends_success(self, mock_chat_class):
        """Test successful organizational trends generation."""
        # Setup mock LLM
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = """
        ## Organizational Development Insights
        
        **Development Velocity Trends:**
        The data shows consistent delivery patterns across repositories with an average of 12 PRs per week.
        
        **Team Productivity Patterns:**
        Peak productivity occurs mid-week with Tuesday-Thursday showing highest commit volumes.
        
        **Code Quality Indicators:**
        Lead times under 48 hours suggest efficient review processes and good code quality.
        
        **Resource Allocation Observations:**
        Teams are well-balanced with no single repository showing bottlenecks.
        
        **Recommendations:**
        1. Maintain current review velocity
        2. Consider automated testing to reduce lead times further
        3. Monitor for potential burnout during peak periods
        """
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            weekly_data = [
                {
                    "week": "2024-W01",
                    "total_prs": 12,
                    "avg_lead_time": 36.5,
                    "repositories": ["repo1", "repo2"]
                },
                {
                    "week": "2024-W02", 
                    "total_prs": 15,
                    "avg_lead_time": 42.0,
                    "repositories": ["repo1", "repo2", "repo3"]
                }
            ]
            
            response = llm_tool.generate_organizational_trends(weekly_data)
            
            assert response.success is True
            assert "Development Velocity Trends" in response.data
            assert "Team Productivity Patterns" in response.data
            assert "Recommendations" in response.data
            mock_llm.invoke.assert_called_once()
    
    @patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI')
    def test_generate_organizational_trends_unsafe_data(self, mock_chat_class):
        """Test organizational trends generation with unsafe data."""
        mock_chat_class.return_value = Mock()
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            # Data containing source code
            unsafe_weekly_data = [
                {
                    "week": "2024-W01",
                    "code_snippet": "import pandas as pd",
                    "total_prs": 10
                }
            ]
            
            response = llm_tool.generate_organizational_trends(unsafe_weekly_data)
            
            assert response.success is False
            assert "Safety check failed" in response.error
    
    @patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI')
    def test_generate_organizational_trends_llm_error(self, mock_chat_class):
        """Test organizational trends generation with LLM error."""
        # Setup mock LLM that raises an exception
        mock_llm = Mock()
        mock_llm.invoke.side_effect = Exception("Network timeout")
        mock_chat_class.return_value = mock_llm
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            weekly_data = [{"week": "2024-W01", "total_prs": 10}]
            
            response = llm_tool.generate_organizational_trends(weekly_data)
            
            assert response.success is False
            assert "Failed to generate organizational trends" in response.error
            assert "Network timeout" in response.error


class TestLLMToolIntegration:
    """Integration tests for LLMTool with realistic scenarios."""
    
    @patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI')
    def test_complete_workflow_simulation(self, mock_chat_class):
        """Test complete LLM workflow with realistic data."""
        # Setup mock LLM with different responses for different calls
        mock_llm = Mock()
        
        def mock_invoke(messages):
            prompt = messages[0].content.lower()
            mock_response = Mock()
            
            if "executive summary" in prompt:
                mock_response.content = "Development team shows strong productivity with 25 total PRs processed this period. Lead times average 28 hours at median, indicating efficient review cycles. Change sizes remain manageable with 180 line median modifications. Weekly patterns show consistent delivery with slight uptick in recent weeks. Code quality metrics suggest well-maintained standards. Team velocity demonstrates sustainable pace with room for optimization. Overall performance indicates healthy development practices and effective collaboration workflows across all monitored repositories."
            elif "organizational" in prompt:
                mock_response.content = """
                ## Organizational Development Analysis
                
                **Velocity Trends:** Consistent 20% week-over-week growth in PR throughput
                **Productivity Patterns:** Peak efficiency Tuesday-Thursday, 15% higher than Monday/Friday
                **Quality Indicators:** Sub-30 hour lead times indicate mature review processes
                **Resource Allocation:** Balanced workload distribution across 3 active repositories
                **Recommendations:** Maintain current velocity, consider automation for routine tasks
                """
            else:
                mock_response.content = "Generic LLM response"
            
            return mock_response
        
        mock_llm.invoke.side_effect = mock_invoke
        mock_chat_class.return_value = mock_llm
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool(model="gpt-4", temperature=0.5)
            
            # Test executive summary
            pr_metrics = {
                "total_prs": 25,
                "lead_time_p50": 28.0,
                "lead_time_p75": 45.0,
                "change_size_p50": 180,
                "change_size_p75": 350,
                "weekly_pr_counts": {"2024-W01": 10, "2024-W02": 15},
                "top_files": [
                    {"file": "src/main.py", "changes": 8},
                    {"file": "tests/test_main.py", "changes": 5}
                ]
            }
            
            weekly_data = {"2024-W01": 10, "2024-W02": 15}
            
            summary_response = llm_tool.generate_executive_summary(pr_metrics, weekly_data)
            assert summary_response.success is True
            assert "Development team shows strong productivity" in summary_response.data
            assert len(summary_response.data.split()) <= 130
            
            # Test organizational trends
            org_data = [
                {
                    "week": "2024-W01",
                    "total_prs": 10,
                    "avg_lead_time": 32.0,
                    "repositories": ["repo1", "repo2"]
                },
                {
                    "week": "2024-W02",
                    "total_prs": 15,
                    "avg_lead_time": 28.0,
                    "repositories": ["repo1", "repo2", "repo3"]
                }
            ]
            
            trends_response = llm_tool.generate_organizational_trends(org_data)
            assert trends_response.success is True
            assert "Organizational Development Analysis" in trends_response.data
            assert "Velocity Trends" in trends_response.data
            assert "Recommendations" in trends_response.data
            
            # Verify both calls were made
            assert mock_llm.invoke.call_count == 2
    
    @patch('git_batch_analyzer.tools.llm_tool.ChatOpenAI')
    def test_safety_validation_comprehensive(self, mock_chat_class):
        """Test comprehensive safety validation scenarios."""
        # Setup mock LLM that would work if safety checks pass
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Safe response"
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            llm_tool = LLMTool()
            
            # Test various unsafe data patterns
            unsafe_patterns = [
                {"code": "function test() { return true; }"},
                {"script": "#!/bin/bash\necho 'hello'"},
                {"query": "CREATE TABLE users (id INT)"},
                {"html": "<script>alert('xss')</script>"},
                {"python": "import os\nos.system('rm -rf /')"},
                {"php": "<?php echo 'hello'; ?>"}
            ]
            
            for unsafe_data in unsafe_patterns:
                # Test executive summary
                response = llm_tool.generate_executive_summary(unsafe_data, {})
                assert response.success is False
                assert "Safety check failed" in response.error
                
                # Test organizational trends
                response = llm_tool.generate_organizational_trends([unsafe_data])
                assert response.success is False
                assert "Safety check failed" in response.error
            
            # Test safe data passes validation
            safe_data = {
                "metrics": {"total": 100, "average": 25.5},
                "weekly_counts": {"2024-W01": 10},
                "percentiles": [25, 50, 75, 90]
            }
            
            # Should not trigger safety checks (though may fail for other reasons)
            summary_response = llm_tool.generate_executive_summary(safe_data, {})
            trends_response = llm_tool.generate_organizational_trends([safe_data])
            
            # Safety checks should pass (errors would be from LLM calls, not safety)
            if summary_response.success is False:
                assert "Safety check failed" not in summary_response.error
            if trends_response.success is False:
                assert "Safety check failed" not in trends_response.error