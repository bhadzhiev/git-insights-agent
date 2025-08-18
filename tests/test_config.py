"""Tests for configuration loading."""

import pytest
import tempfile
import os
from pathlib import Path
from git_batch_analyzer.config.loader import load_config_from_yaml, ConfigurationError
from git_batch_analyzer.config.models import AnalysisConfig, RepositoryConfig, LLMConfig


def test_load_basic_config():
    """Test loading a basic configuration."""
    config_yaml = """
repositories:
  - url: "https://github.com/example/repo1.git"
    branch: "main"
  - "https://github.com/example/repo2.git"

period_days: 14
output_file: "custom-report.md"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        config = load_config_from_yaml(f.name)
        
        assert len(config.repositories) == 2
        assert config.repositories[0].url == "https://github.com/example/repo1.git"
        assert config.repositories[0].branch == "main"
        assert config.repositories[1].url == "https://github.com/example/repo2.git"
        assert config.repositories[1].branch is None
        assert config.period_days == 14
        assert config.output_file == Path("custom-report.md")
        assert config.stale_days == 14  # Should default to period_days


def test_load_config_with_llm():
    """Test loading configuration with LLM settings."""
    config_yaml = """
repositories:
  - "https://github.com/example/repo.git"

llm:
  provider: "openai"
  model: "gpt-4"
  temperature: 0.5
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        config = load_config_from_yaml(f.name)
        
        assert config.llm is not None
        assert config.llm.provider == "openai"
        assert config.llm.model == "gpt-4"
        assert config.llm.temperature == 0.5


def test_config_validation_errors():
    """Test configuration validation errors."""
    
    # Missing repositories
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("period_days: 7")
        f.flush()
        
        with pytest.raises(ConfigurationError, match="must specify 'repositories'"):
            load_config_from_yaml(f.name)
    
    # Invalid period_days
    config_yaml = """
repositories:
  - "https://github.com/example/repo.git"
period_days: -1
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        with pytest.raises(ConfigurationError, match="period_days must be a positive integer"):
            load_config_from_yaml(f.name)


def test_config_defaults():
    """Test that configuration defaults are applied correctly."""
    config_yaml = """
repositories:
  - "https://github.com/example/repo.git"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        config = load_config_from_yaml(f.name)
        
        assert config.period_days == 7
        assert config.fetch_depth == 200
        assert config.top_k_files == 10
        assert config.output_file == Path("report.md")
        assert config.stale_days == 7  # Should equal period_days
        assert config.llm is None


def test_stale_days_configuration():
    """Test stale_days configuration and defaults."""
    # Test explicit stale_days
    config_yaml = """
repositories:
  - "https://github.com/example/repo.git"
period_days: 7
stale_days: 30
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        config = load_config_from_yaml(f.name)
        assert config.stale_days == 30
        assert config.effective_stale_days == 30
    
    # Test stale_days defaults to period_days
    config_yaml = """
repositories:
  - "https://github.com/example/repo.git"
period_days: 14
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        config = load_config_from_yaml(f.name)
        assert config.stale_days == 14
        assert config.effective_stale_days == 14


def test_repository_url_validation():
    """Test repository URL validation."""
    
    # Valid URLs
    valid_urls = [
        "https://github.com/user/repo.git",
        "https://github.com/user/repo",
        "git@github.com:user/repo.git",
        "git@github.com:user/repo",
        "ssh://git@github.com/user/repo.git",
        "https://gitlab.com/user/repo.git",
    ]
    
    for url in valid_urls:
        config_yaml = f"""
repositories:
  - "{url}"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            config = load_config_from_yaml(f.name)  # Should not raise
            assert config.repositories[0].url == url
    
    # Invalid URLs
    invalid_urls_and_messages = [
        ("", "URL cannot be empty"),
        ("   ", "URL cannot be empty"),
        ("not-a-url", "Invalid git URL format"),
        ("ftp://example.com/repo", "Invalid git URL format"),
        ("https://", "Invalid git URL format"),
        ("github.com/user/repo", "Invalid git URL format"),  # Missing protocol
    ]
    
    for url, expected_message in invalid_urls_and_messages:
        config_yaml = f"""
repositories:
  - "{url}"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            with pytest.raises(ConfigurationError, match=expected_message):
                load_config_from_yaml(f.name)


def test_branch_name_validation():
    """Test branch name validation."""
    
    # Valid branch names
    valid_branches = [
        "main",
        "develop",
        "feature/new-feature",
        "release/v1.0.0",
        "hotfix/bug-123",
        "user/john/feature",
    ]
    
    for branch in valid_branches:
        config_yaml = f"""
repositories:
  - url: "https://github.com/user/repo.git"
    branch: "{branch}"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            config = load_config_from_yaml(f.name)  # Should not raise
            assert config.repositories[0].branch == branch
    
    # Invalid branch names
    invalid_branches_and_messages = [
        ("", "Branch name cannot be empty"),
        ("   ", "Branch name cannot be empty"),
        ("branch with spaces", "Invalid branch name"),
        ("branch\twith\ttabs", "Invalid branch name"),
        ("branch\nwith\nnewlines", "Invalid branch name"),
        ("/leading-slash", "Invalid branch name"),
        ("trailing-slash/", "Invalid branch name"),
        ("double//slash", "Invalid branch name"),
        ("branch~with~tildes", "Invalid branch name"),
        ("branch^with^carets", "Invalid branch name"),
        ("branch:with:colons", "Invalid branch name"),
        ("branch?with?questions", "Invalid branch name"),
        ("branch*with*asterisks", "Invalid branch name"),
        ("branch[with]brackets", "Invalid branch name"),
        ("branch@with@at", "Invalid branch name"),
        (".", "Invalid branch name"),
        ("..", "Invalid branch name"),
    ]
    
    for branch, expected_message in invalid_branches_and_messages:
        config_yaml = f"""repositories:
  - url: "https://github.com/user/repo.git"
    branch: "{branch}"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            with pytest.raises(ConfigurationError, match=expected_message):
                load_config_from_yaml(f.name)


def test_numeric_parameter_validation():
    """Test validation of numeric parameters."""
    
    # Test period_days validation
    invalid_period_days_and_messages = [
        (-1, "period_days must be a positive integer"),
        (0, "period_days must be a positive integer"),
        (366, "period_days cannot exceed 365 days"),
        (3.14, "'period_days' must be an integer, not a float"),
    ]
    
    for value, expected_message in invalid_period_days_and_messages:
        config_yaml = f"""repositories:
  - "https://github.com/user/repo.git"
period_days: {value}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            with pytest.raises(ConfigurationError, match=expected_message):
                load_config_from_yaml(f.name)
    
    # Test string value for period_days
    config_yaml = """repositories:
  - "https://github.com/user/repo.git"
period_days: "not-a-number"
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        with pytest.raises(ConfigurationError, match="'period_days' must be an integer"):
            load_config_from_yaml(f.name)
    
    # Test stale_days validation
    invalid_stale_days_and_messages = [
        (-1, "stale_days must be a positive integer"),
        (0, "stale_days must be a positive integer"),
        (366, "stale_days cannot exceed 365 days"),
    ]
    
    for value, expected_message in invalid_stale_days_and_messages:
        config_yaml = f"""repositories:
  - "https://github.com/user/repo.git"
stale_days: {value}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            with pytest.raises(ConfigurationError, match=expected_message):
                load_config_from_yaml(f.name)
    
    # Test fetch_depth validation
    invalid_fetch_depths_and_messages = [
        (-1, "fetch_depth must be a positive integer"),
        (0, "fetch_depth must be a positive integer"),
        (10001, "fetch_depth cannot exceed 10000 commits"),
    ]
    
    for value, expected_message in invalid_fetch_depths_and_messages:
        config_yaml = f"""repositories:
  - "https://github.com/user/repo.git"
fetch_depth: {value}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            with pytest.raises(ConfigurationError, match=expected_message):
                load_config_from_yaml(f.name)
    
    # Test top_k_files validation
    invalid_top_k_and_messages = [
        (-1, "top_k_files must be a positive integer"),
        (0, "top_k_files must be a positive integer"),
        (101, "top_k_files cannot exceed 100"),
    ]
    
    for value, expected_message in invalid_top_k_and_messages:
        config_yaml = f"""repositories:
  - "https://github.com/user/repo.git"
top_k_files: {value}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            with pytest.raises(ConfigurationError, match=expected_message):
                load_config_from_yaml(f.name)


def test_llm_configuration_validation():
    """Test LLM configuration validation."""
    
    # Valid LLM configurations
    valid_llm_configs = [
        {
            "provider": "openai",
            "model": "gpt-4",
            "temperature": 0.5,
        },
        {
            "provider": "anthropic",
            "model": "claude-3",
            "temperature": 0.0,
        },
        {
            "provider": "azure",
            "model": "gpt-35-turbo",
            "temperature": 1.0,
            "api_key": "test-key",
        },
        {
            "provider": "openrouter",
            "model": "anthropic/claude-3.5-sonnet",
            "temperature": 0.3,
            "api_key": "sk-or-v1-test-key",
            "base_url": "https://openrouter.ai/api/v1",
            "max_tokens": 4000,
        },
    ]
    
    for llm_config in valid_llm_configs:
        config_yaml = f"""
repositories:
  - "https://github.com/user/repo.git"
llm:
  provider: "{llm_config['provider']}"
  model: "{llm_config['model']}"
  temperature: {llm_config['temperature']}
"""
        if 'api_key' in llm_config:
            config_yaml += f'  api_key: "{llm_config["api_key"]}"\n'
        if 'base_url' in llm_config:
            config_yaml += f'  base_url: "{llm_config["base_url"]}"\n'
        if 'max_tokens' in llm_config:
            config_yaml += f'  max_tokens: {llm_config["max_tokens"]}\n'
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            config = load_config_from_yaml(f.name)  # Should not raise
            assert config.llm.provider == llm_config['provider']
            assert config.llm.model == llm_config['model']
            assert config.llm.temperature == llm_config['temperature']
    
    # Invalid LLM configurations
    invalid_configs = [
        {"provider": "", "model": "gpt-4", "temperature": 0.5},
        {"provider": "openai", "model": "", "temperature": 0.5},
        {"provider": "openai", "model": "gpt-4", "temperature": -0.1},
        {"provider": "openai", "model": "gpt-4", "temperature": 2.1},
        {"provider": "unsupported", "model": "gpt-4", "temperature": 0.5},
        {"provider": "openrouter", "model": "anthropic/claude-3.5-sonnet", "temperature": 0.5},  # Missing API key
    ]
    
    for llm_config in invalid_configs:
        config_yaml = f"""
repositories:
  - "https://github.com/user/repo.git"
llm:
  provider: "{llm_config['provider']}"
  model: "{llm_config['model']}"
  temperature: {llm_config['temperature']}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_yaml)
            f.flush()
            
            with pytest.raises(ConfigurationError):
                load_config_from_yaml(f.name)


def test_repository_format_variations():
    """Test different repository configuration formats."""
    
    # Mixed string and dictionary formats
    config_yaml = """
repositories:
  - "https://github.com/user/repo1.git"
  - url: "https://github.com/user/repo2.git"
    branch: "develop"
  - url: "git@github.com:user/repo3.git"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        config = load_config_from_yaml(f.name)
        
        assert len(config.repositories) == 3
        assert config.repositories[0].url == "https://github.com/user/repo1.git"
        assert config.repositories[0].branch is None
        assert config.repositories[1].url == "https://github.com/user/repo2.git"
        assert config.repositories[1].branch == "develop"
        assert config.repositories[2].url == "git@github.com:user/repo3.git"
        assert config.repositories[2].branch is None


def test_empty_and_invalid_repositories():
    """Test handling of empty and invalid repository configurations."""
    
    # Empty repositories list
    config_yaml = """
repositories: []
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        with pytest.raises(ConfigurationError, match="'repositories' cannot be empty"):
            load_config_from_yaml(f.name)
    
    # Repositories not a list
    config_yaml = """
repositories: "not-a-list"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        with pytest.raises(ConfigurationError, match="'repositories' must be a list"):
            load_config_from_yaml(f.name)
    
    # Repository missing URL
    config_yaml = """
repositories:
  - branch: "main"
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        with pytest.raises(ConfigurationError, match="missing required 'url' field"):
            load_config_from_yaml(f.name)


def test_file_not_found():
    """Test handling of missing configuration files."""
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        load_config_from_yaml("nonexistent-file.yaml")


def test_invalid_yaml():
    """Test handling of invalid YAML files."""
    invalid_yaml = """
repositories:
  - url: "https://github.com/user/repo.git"
    branch: "main
    # Missing closing quote
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(invalid_yaml)
        f.flush()
        
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            load_config_from_yaml(f.name)


def test_config_model_methods():
    """Test additional methods on AnalysisConfig."""
    config_yaml = """
repositories:
  - "https://github.com/user/repo.git"
period_days: 7
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_yaml)
        f.flush()
        
        config = load_config_from_yaml(f.name)
        
        # Test effective_stale_days property
        assert config.effective_stale_days == 7
        
        # Test get_repo_cache_dir method
        cache_dir = config.get_repo_cache_dir("https://github.com/user/repo.git")
        expected_path = config.cache_dir / "repo"
        assert cache_dir == expected_path
        
        # Test with .git suffix
        cache_dir = config.get_repo_cache_dir("https://github.com/user/my-repo.git")
        expected_path = config.cache_dir / "my-repo"
        assert cache_dir == expected_path