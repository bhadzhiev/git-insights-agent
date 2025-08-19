"""End-to-end tests for the main CLI interface."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from git_batch_analyzer.main import cli
from git_batch_analyzer.config.models import AnalysisConfig, RepositoryConfig, LLMConfig


@pytest.fixture
def sample_config_yaml():
    """Sample configuration YAML for testing."""
    return """
repositories:
  - url: "https://github.com/example/repo1.git"
    branch: "main"
  - url: "https://github.com/example/repo2.git"

period_days: 7
stale_days: 14
cache_dir: "/tmp/test-cache"
output_file: "test-report.md"

llm:
  provider: "openai"
  model: "gpt-3.5-turbo"
  temperature: 0.7
"""


@pytest.fixture
def minimal_config_yaml():
    """Minimal configuration YAML for testing."""
    return """
repositories:
  - "https://github.com/example/repo.git"
"""


@pytest.fixture
def mock_successful_results():
    """Mock successful processing results."""
    return {
        "successful_repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/example/repo1.git",
                "final_state": {
                    "final_report": "# Repository Analysis\n\nSample report content for repo1.",
                    "assembler_completed": True
                }
            },
            {
                "name": "repo2", 
                "url": "https://github.com/example/repo2.git",
                "final_state": {
                    "final_report": "# Repository Analysis\n\nSample report content for repo2.",
                    "assembler_completed": True
                }
            }
        ],
        "failed_repositories": [],
        "errors": []
    }


@pytest.fixture
def mock_mixed_results():
    """Mock mixed success/failure processing results."""
    return {
        "successful_repositories": [
            {
                "name": "repo1",
                "url": "https://github.com/example/repo1.git", 
                "final_state": {
                    "final_report": "# Repository Analysis\n\nSample report content for repo1.",
                    "assembler_completed": True
                }
            }
        ],
        "failed_repositories": [
            {
                "name": "repo2",
                "url": "https://github.com/example/repo2.git",
                "errors": ["Repository not found", "Access denied"]
            }
        ],
        "errors": ["repo2: Repository not found", "repo2: Access denied"]
    }


class TestCLIBasicFunctionality:
    """Test basic CLI functionality."""
    
    def test_cli_help(self):
        """Test that CLI help is displayed correctly."""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert "Git Batch Analyzer" in result.output
        assert "CONFIG_FILE" in result.output
        assert "--verbose" in result.output
        assert "--dry-run" in result.output
    
    def test_missing_config_file(self):
        """Test error handling for missing config file."""
        runner = CliRunner()
        result = runner.invoke(cli, ['nonexistent-config.yaml'])
        
        assert result.exit_code == 2  # Click validation error
        assert "does not exist" in result.output
    
    def test_invalid_yaml_config(self):
        """Test error handling for invalid YAML."""
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            
            result = runner.invoke(cli, [f.name])
            
            assert result.exit_code == 1
            assert "Configuration error" in result.output


class TestCLIDryRun:
    """Test CLI dry run functionality."""
    
    def test_dry_run_basic(self, sample_config_yaml):
        """Test basic dry run functionality."""
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_config_yaml)
            f.flush()
            
            result = runner.invoke(cli, [f.name, '--dry-run'])
            
            assert result.exit_code == 0
            assert "DRY RUN SUMMARY" in result.output
            assert "repo1.git" in result.output
            assert "repo2.git" in result.output
            assert "Period: 7 days" in result.output
            assert "Stale threshold: 14 days" in result.output
    
    def test_dry_run_minimal_config(self, minimal_config_yaml):
        """Test dry run with minimal configuration."""
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(minimal_config_yaml)
            f.flush()
            
            result = runner.invoke(cli, [f.name, '--dry-run'])
            
            assert result.exit_code == 0
            assert "DRY RUN SUMMARY" in result.output
            assert "LLM: Disabled" in result.output
    
    def test_dry_run_with_overrides(self, sample_config_yaml):
        """Test dry run with CLI option overrides."""
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_config_yaml)
            f.flush()
            
            result = runner.invoke(cli, [
                f.name, 
                '--dry-run',
                '--period-days', '14',
                '--output', 'custom-output.md',
                '--cache-dir', '/tmp/custom-cache'
            ])
            
            assert result.exit_code == 0
            assert "Period: 14 days" in result.output
            assert "custom-output.md" in result.output
            assert "/tmp/custom-cache" in result.output


class TestCLIProcessing:
    """Test CLI processing functionality."""
    
    @patch('git_batch_analyzer.main.process_repositories')
    def test_successful_processing(self, mock_process, sample_config_yaml, mock_successful_results):
        """Test successful processing of all repositories."""
        mock_process.return_value = mock_successful_results
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.yaml"
            output_file = Path(temp_dir) / "test-report.md"
            
            # Update config to use temp directory
            config_content = sample_config_yaml.replace(
                'output_file: "test-report.md"',
                f'output_file: "{output_file}"'
            )
            
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            result = runner.invoke(cli, [str(config_file)])
            
            assert result.exit_code == 0
            assert "Successfully processed: repo1" in result.output
            assert "Successfully processed: repo2" in result.output
            assert "ANALYSIS COMPLETE" in result.output
            assert "Successfully processed: 2" in result.output
            
            # Verify summary report was written
            assert output_file.exists()
            report_content = output_file.read_text()
            assert "Git Batch Analysis Summary Report" in report_content
            assert "repo1" in report_content
            assert "repo2" in report_content
            assert "Active Repositories (with PRs/commits)" in report_content
    
    @patch('git_batch_analyzer.main.process_repositories')
    def test_mixed_processing_results(self, mock_process, sample_config_yaml, mock_mixed_results):
        """Test processing with some failures."""
        mock_process.return_value = mock_mixed_results
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.yaml"
            output_file = Path(temp_dir) / "test-report.md"
            
            config_content = sample_config_yaml.replace(
                'output_file: "test-report.md"',
                f'output_file: "{output_file}"'
            )
            
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            result = runner.invoke(cli, [str(config_file)])
            
            assert result.exit_code == 0
            assert "Successfully processed: repo1" in result.output
            assert "Failed to process: repo2" in result.output
            assert "Repository not found" in result.output
            assert "Successfully processed: 1" in result.output
            assert "Failed: 1" in result.output
            
            # Verify summary report was still written for successful repository
            assert output_file.exists()
            report_content = output_file.read_text()
            assert "repo1" in report_content
            assert "Git Batch Analysis Summary Report" in report_content
    
    @patch('git_batch_analyzer.main.process_repositories')
    def test_all_repositories_failed(self, mock_process, sample_config_yaml):
        """Test handling when all repositories fail."""
        mock_process.return_value = {
            "successful_repositories": [],
            "failed_repositories": [
                {"name": "repo1", "url": "https://github.com/example/repo1.git", "errors": ["Failed"]},
                {"name": "repo2", "url": "https://github.com/example/repo2.git", "errors": ["Failed"]}
            ],
            "errors": ["repo1: Failed", "repo2: Failed"]
        }
        
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_config_yaml)
            f.flush()
            
            result = runner.invoke(cli, [f.name])
            
            assert result.exit_code == 0  # CLI should not fail, just log errors
            assert "No repositories were successfully processed" in result.output
            assert "Failed to process: repo1" in result.output
            assert "Failed to process: repo2" in result.output


class TestCLIOptions:
    """Test CLI option handling."""
    
    @patch('git_batch_analyzer.main.process_repositories')
    def test_verbose_logging(self, mock_process, minimal_config_yaml, mock_successful_results):
        """Test verbose logging option."""
        mock_process.return_value = mock_successful_results
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(minimal_config_yaml)
            f.flush()
            
            result = runner.invoke(cli, [f.name, '--verbose'])
            
            assert result.exit_code == 0
            assert "Verbose logging enabled" in result.output
    
    @patch('git_batch_analyzer.main.process_repositories')
    def test_output_override(self, mock_process, minimal_config_yaml, mock_successful_results):
        """Test output file override option."""
        mock_process.return_value = mock_successful_results
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.yaml"
            custom_output = Path(temp_dir) / "custom-report.md"
            
            with open(config_file, 'w') as f:
                f.write(minimal_config_yaml)
            
            result = runner.invoke(cli, [
                str(config_file),
                '--output', str(custom_output)
            ])
            
            assert result.exit_code == 0
            assert custom_output.exists()
    
    @patch('git_batch_analyzer.main.process_repositories')
    def test_cache_dir_override(self, mock_process, minimal_config_yaml, mock_successful_results):
        """Test cache directory override option."""
        mock_process.return_value = mock_successful_results
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_file = Path(temp_dir) / "config.yaml"
            custom_cache = Path(temp_dir) / "custom-cache"
            
            with open(config_file, 'w') as f:
                f.write(minimal_config_yaml)
            
            result = runner.invoke(cli, [
                str(config_file),
                '--cache-dir', str(custom_cache)
            ])
            
            assert result.exit_code == 0
            # Cache directory should be created
            assert custom_cache.exists()
    
    @patch('git_batch_analyzer.main.process_repositories')
    def test_period_days_override(self, mock_process, minimal_config_yaml, mock_successful_results):
        """Test period days override option."""
        mock_process.return_value = mock_successful_results
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(minimal_config_yaml)
            f.flush()
            
            result = runner.invoke(cli, [
                f.name,
                '--period-days', '21',
                '--dry-run'
            ])
            
            assert result.exit_code == 0
            assert "Period: 21 days" in result.output


class TestCLIErrorHandling:
    """Test CLI error handling."""
    
    def test_keyboard_interrupt(self, sample_config_yaml):
        """Test handling of keyboard interrupt."""
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_config_yaml)
            f.flush()
            
            with patch('git_batch_analyzer.main.process_repositories') as mock_process:
                mock_process.side_effect = KeyboardInterrupt()
                
                result = runner.invoke(cli, [f.name])
                
                assert result.exit_code == 130
                assert "interrupted by user" in result.output
    
    def test_unexpected_error(self, sample_config_yaml):
        """Test handling of unexpected errors."""
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_config_yaml)
            f.flush()
            
            with patch('git_batch_analyzer.main.process_repositories') as mock_process:
                mock_process.side_effect = RuntimeError("Unexpected error")
                
                result = runner.invoke(cli, [f.name])
                
                assert result.exit_code == 1
                assert "Unexpected error" in result.output
    
    def test_unexpected_error_verbose(self, sample_config_yaml):
        """Test handling of unexpected errors with verbose logging."""
        runner = CliRunner()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(sample_config_yaml)
            f.flush()
            
            with patch('git_batch_analyzer.main.process_repositories') as mock_process:
                mock_process.side_effect = RuntimeError("Unexpected error")
                
                result = runner.invoke(cli, [f.name, '--verbose'])
                
                assert result.exit_code == 1
                assert "Unexpected error" in result.output
                assert "Full traceback" in result.output


class TestReportGeneration:
    """Test report generation functionality."""
    
    def test_create_summary_report_content(self):
        """Test creating summary report content."""
        from git_batch_analyzer.main import _create_summary_report_content
        from git_batch_analyzer.config.models import AnalysisConfig, RepositoryConfig
        
        successful_repos = [
            {
                "name": "repo1",
                "url": "https://github.com/example/repo1.git",
                "branch": "main",
                "total_prs": 5
            },
            {
                "name": "repo2", 
                "url": "https://github.com/example/repo2.git",
                "branch": "develop",
                "total_prs": 3
            }
        ]
        
        inactive_repos = [
            {
                "name": "repo3",
                "url": "https://github.com/example/repo3.git",
                "branch": "main",
                "total_prs": 0
            }
        ]
        
        failed_repos = [
            {
                "name": "repo4",
                "url": "https://github.com/example/repo4.git",
                "error": "Repository not found"
            }
        ]
        
        config = AnalysisConfig(
            repositories=[
                RepositoryConfig(url="https://github.com/example/repo1.git"),
                RepositoryConfig(url="https://github.com/example/repo2.git"),
                RepositoryConfig(url="https://github.com/example/repo3.git"),
                RepositoryConfig(url="https://github.com/example/repo4.git")
            ],
            period_days=7
        )
        
        summary = _create_summary_report_content(successful_repos, inactive_repos, failed_repos, config)
        
        assert "Git Batch Analysis Summary Report" in summary
        assert "Analysis Period:** 7 days" in summary
        assert "Total Repositories:** 4" in summary
        assert "Successful:** 3" in summary
        assert "Failed:** 1" in summary
        assert "Active Repositories (with PRs/commits)" in summary
        assert "Inactive Repositories (no PRs/commits)" in summary
        assert "Failed Repositories" in summary
        assert "repo1" in summary
        assert "repo2" in summary
        assert "repo3" in summary
        assert "repo4" in summary
        assert "Repository not found" in summary
    
    def test_empty_repositories_handling(self):
        """Test handling of empty repositories lists."""
        from git_batch_analyzer.main import _create_summary_report_content
        from git_batch_analyzer.config.models import AnalysisConfig, RepositoryConfig
        
        config = AnalysisConfig(
            repositories=[RepositoryConfig(url="https://github.com/example/repo.git")],
            period_days=7
        )
        
        summary = _create_summary_report_content([], [], [], config)
        
        assert "Git Batch Analysis Summary Report" in summary
        assert "Total Repositories:** 0" in summary
        assert "Successful:** 0" in summary
        assert "Failed:** 0" in summary