"""Integration tests for CLI entry point."""

import subprocess
import tempfile
from pathlib import Path


def test_cli_entry_point_help():
    """Test that the CLI entry point works via uv run."""
    result = subprocess.run(
        ["uv", "run", "git-batch-analyzer", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "Git Batch Analyzer" in result.stdout
    assert "CONFIG_FILE" in result.stdout


def test_cli_entry_point_dry_run():
    """Test that the CLI entry point works with dry run."""
    config_yaml = """
repositories:
  - "https://github.com/example/test-repo.git"
period_days: 7
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        result = subprocess.run(
            ["uv", "run", "git-batch-analyzer", f.name, "--dry-run"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "DRY RUN SUMMARY" in result.stdout
        assert "test-repo.git" in result.stdout


def test_cli_module_invocation():
    """Test that the CLI can be invoked as a module."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "git_batch_analyzer.main", "--help"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    assert "Git Batch Analyzer" in result.stdout