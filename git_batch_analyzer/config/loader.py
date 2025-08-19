"""Configuration loading utilities for Git Batch Analyzer."""

import yaml
import re
from pathlib import Path
from typing import Any, Dict, List, Union, Optional
from urllib.parse import urlparse
from .models import AnalysisConfig, RepositoryConfig, LLMConfig, EmailConfig


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


def load_config_from_yaml(config_path: Union[str, Path]) -> AnalysisConfig:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        AnalysisConfig: Parsed configuration object
        
    Raises:
        ConfigurationError: If configuration is invalid or file cannot be read
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in configuration file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error reading configuration file: {e}")
    
    if not isinstance(raw_config, dict):
        raise ConfigurationError("Configuration file must contain a YAML object")
    
    return _parse_config_dict(raw_config)


def _parse_config_dict(config_dict: Dict[str, Any]) -> AnalysisConfig:
    """
    Parse configuration dictionary into AnalysisConfig object.
    
    Args:
        config_dict: Raw configuration dictionary
        
    Returns:
        AnalysisConfig: Parsed configuration object
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    # Validate required fields
    if 'repositories' not in config_dict:
        raise ConfigurationError("Configuration must specify 'repositories'")
    
    repositories_data = config_dict['repositories']
    if not isinstance(repositories_data, list):
        raise ConfigurationError("'repositories' must be a list")
    
    if not repositories_data:
        raise ConfigurationError("'repositories' cannot be empty")
    
    # Parse repositories
    repositories = []
    for i, repo_data in enumerate(repositories_data):
        try:
            if isinstance(repo_data, str):
                # Simple string format: just URL
                repositories.append(RepositoryConfig(url=repo_data.strip()))
            elif isinstance(repo_data, dict):
                # Dictionary format with url and optional branch
                if 'url' not in repo_data:
                    raise ConfigurationError(f"Repository {i}: missing required 'url' field")
                
                url = repo_data['url']
                if not isinstance(url, str):
                    raise ConfigurationError(f"Repository {i}: 'url' must be a string")
                
                branch = repo_data.get('branch')
                if branch is not None and not isinstance(branch, str):
                    raise ConfigurationError(f"Repository {i}: 'branch' must be a string")
                
                # Validate branch before creating the config
                if branch is not None and not branch.strip():
                    raise ConfigurationError(f"Repository {i}: Branch name cannot be empty")
                
                repositories.append(RepositoryConfig(
                    url=url.strip(),
                    branch=branch.strip() if branch and branch.strip() else None
                ))
            else:
                raise ConfigurationError(
                    f"Repository {i}: must be a string URL or dictionary with 'url' field"
                )
        except ConfigurationError:
            raise
        except Exception as e:
            raise ConfigurationError(f"Repository {i}: error parsing configuration - {e}")
    
    # Parse and validate numeric parameters
    period_days = _parse_int_param(config_dict, 'period_days', 7, 'period_days')
    stale_days = _parse_optional_int_param(config_dict, 'stale_days', 'stale_days')
    fetch_depth = _parse_int_param(config_dict, 'fetch_depth', 200, 'fetch_depth')
    top_k_files = _parse_int_param(config_dict, 'top_k_files', 10, 'top_k_files')
    
    # Parse path parameters
    cache_dir = _parse_path_param(config_dict, 'cache_dir', 
                                  Path.home() / ".cache" / "git-analyzer", 'cache_dir')
    output_file = _parse_path_param(config_dict, 'output_file', 
                                    Path('report.md'), 'output_file')
    
    # Parse LLM configuration if present
    llm_config = None
    if 'llm' in config_dict:
        llm_data = config_dict['llm']
        if llm_data is None:
            # Explicitly set to None - disable LLM
            llm_config = None
        elif isinstance(llm_data, dict):
            llm_config = _parse_llm_config(llm_data)
        else:
            raise ConfigurationError("'llm' must be a dictionary or null")

    # Parse Email configuration if present
    email_config = None
    if 'email' in config_dict:
        email_data = config_dict['email']
        if email_data is not None:
            if isinstance(email_data, dict):
                email_config = _parse_email_config(email_data)
            else:
                raise ConfigurationError("'email' must be a dictionary")
    
    # Build configuration with validated parameters
    try:
        config = AnalysisConfig(
            repositories=repositories,
            period_days=period_days,
            cache_dir=cache_dir,
            output_file=output_file,
            stale_days=stale_days,
            fetch_depth=fetch_depth,
            top_k_files=top_k_files,
            llm=llm_config,
            email=email_config
        )
    except Exception as e:
        raise ConfigurationError(f"Error creating configuration: {e}")
    
    # Validate configuration values
    _validate_config(config)
    
    return config


def _parse_int_param(config_dict: Dict[str, Any], key: str, default: int, param_name: str) -> int:
    """Parse and validate an integer parameter."""
    value = config_dict.get(key, default)
    
    if not isinstance(value, int):
        if isinstance(value, float):
            raise ConfigurationError(f"'{param_name}' must be an integer, not a float")
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ConfigurationError(f"'{param_name}' must be an integer")
    
    return value


def _parse_optional_int_param(config_dict: Dict[str, Any], key: str, param_name: str) -> Optional[int]:
    """Parse and validate an optional integer parameter."""
    if key not in config_dict:
        return None
    
    value = config_dict[key]
    if value is None:
        return None
    
    if not isinstance(value, int):
        if isinstance(value, float):
            raise ConfigurationError(f"'{param_name}' must be an integer, not a float")
        try:
            value = int(value)
        except (ValueError, TypeError):
            raise ConfigurationError(f"'{param_name}' must be an integer or null")
    
    return value


def _parse_path_param(config_dict: Dict[str, Any], key: str, default: Path, param_name: str) -> Path:
    """Parse and validate a path parameter."""
    value = config_dict.get(key)
    
    if value is None:
        return default
    
    if not isinstance(value, str):
        raise ConfigurationError(f"'{param_name}' must be a string path")
    
    try:
        return Path(value)
    except Exception as e:
        raise ConfigurationError(f"'{param_name}' is not a valid path: {e}")


def _parse_email_config(email_data: Dict[str, Any]) -> EmailConfig:
    """Parse email configuration dictionary."""
    sender_email = email_data.get('sender_email')
    sender_name = email_data.get('sender_name', 'Git Batch Analyzer')
    provider = email_data.get('provider', 'smtp').lower()
    
    # Common fields
    api_key = email_data.get('api_key')
    api_secret = email_data.get('api_secret')
    
    # SMTP-specific fields
    smtp_server = email_data.get('smtp_server')
    smtp_port = email_data.get('smtp_port', 587)
    smtp_password = email_data.get('smtp_password') or api_secret

    # Validate required fields
    if not sender_email or not isinstance(sender_email, str):
        raise ConfigurationError("Email 'sender_email' must be a non-empty string")
    if not isinstance(sender_name, str):
        raise ConfigurationError("Email 'sender_name' must be a string")
    
    if provider not in ['smtp', 'mailjet']:
        raise ConfigurationError("Email 'provider' must be either 'smtp' or 'mailjet'")
    
    # Provider-specific validation
    if provider == 'mailjet':
        if not api_key or not isinstance(api_key, str):
            raise ConfigurationError("Mailjet provider requires 'api_key'")
        if not api_secret or not isinstance(api_secret, str):
            raise ConfigurationError("Mailjet provider requires 'api_secret'")
    
    elif provider == 'smtp':
        if not smtp_server or not isinstance(smtp_server, str):
            raise ConfigurationError("SMTP provider requires 'smtp_server'")
        # Allow SMTP relays without authentication (smtp_password optional)

    return EmailConfig(
        sender_email=sender_email,
        sender_name=sender_name,
        provider=provider,
        api_key=api_key,
        api_secret=api_secret,
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        smtp_password=smtp_password
    )


def _parse_llm_config(llm_data: Dict[str, Any]) -> LLMConfig:
    """Parse LLM configuration dictionary."""
    provider = llm_data.get('provider', 'openai')
    model = llm_data.get('model', 'gpt-3.5-turbo')
    temperature = llm_data.get('temperature', 0.7)
    api_key = llm_data.get('api_key')
    base_url = llm_data.get('base_url')
    max_tokens = llm_data.get('max_tokens')
    
    # Validate types
    if not isinstance(provider, str):
        raise ConfigurationError("LLM 'provider' must be a string")
    
    if not isinstance(model, str):
        raise ConfigurationError("LLM 'model' must be a string")
    
    if not isinstance(temperature, (int, float)):
        raise ConfigurationError("LLM 'temperature' must be a number")
    
    if api_key is not None and not isinstance(api_key, str):
        raise ConfigurationError("LLM 'api_key' must be a string or null")
    
    if base_url is not None and not isinstance(base_url, str):
        raise ConfigurationError("LLM 'base_url' must be a string or null")
    
    if max_tokens is not None and not isinstance(max_tokens, int):
        raise ConfigurationError("LLM 'max_tokens' must be an integer or null")
    
    # Set default base_url for OpenRouter
    if provider.lower() == 'openrouter' and base_url is None:
        base_url = 'https://openrouter.ai/api/v1'
    
    return LLMConfig(
        provider=provider.strip(),
        model=model.strip(),
        temperature=float(temperature),
        api_key=api_key.strip() if api_key else None,
        base_url=base_url.strip() if base_url else None,
        max_tokens=max_tokens
    )


def _validate_config(config: AnalysisConfig) -> None:
    """
    Validate configuration values.
    
    Args:
        config: Configuration to validate
        
    Raises:
        ConfigurationError: If configuration is invalid
    """
    # Validate numeric parameters
    if config.period_days <= 0:
        raise ConfigurationError("period_days must be a positive integer")
    
    if config.period_days > 365:
        raise ConfigurationError("period_days cannot exceed 365 days")
    
    if config.stale_days is not None and config.stale_days <= 0:
        raise ConfigurationError("stale_days must be a positive integer")
    
    if config.stale_days is not None and config.stale_days > 365:
        raise ConfigurationError("stale_days cannot exceed 365 days")
    
    if config.fetch_depth <= 0:
        raise ConfigurationError("fetch_depth must be a positive integer")
    
    if config.fetch_depth > 10000:
        raise ConfigurationError("fetch_depth cannot exceed 10000 commits")
    
    if config.top_k_files <= 0:
        raise ConfigurationError("top_k_files must be a positive integer")
    
    if config.top_k_files > 100:
        raise ConfigurationError("top_k_files cannot exceed 100")
    
    # Validate repository URLs and branches
    for i, repo in enumerate(config.repositories):
        _validate_repository_config(repo, i)
    
    # Validate paths
    _validate_paths(config)
    
    # Validate LLM configuration if present
    if config.llm:
        _validate_llm_config(config.llm)


def _validate_repository_config(repo: RepositoryConfig, index: int) -> None:
    """
    Validate a single repository configuration.
    
    Args:
        repo: Repository configuration to validate
        index: Index of repository in list (for error messages)
        
    Raises:
        ConfigurationError: If repository configuration is invalid
    """
    if not repo.url or not repo.url.strip():
        raise ConfigurationError(f"Repository {index}: URL cannot be empty")
    
    url = repo.url.strip()
    
    # Validate URL format
    if not _is_valid_git_url(url):
        raise ConfigurationError(
            f"Repository {index}: Invalid git URL format '{url}'. "
            "Must be a valid HTTP(S) or SSH git URL"
        )
    
    # Validate branch name if specified
    if repo.branch is not None:
        if not repo.branch.strip():
            raise ConfigurationError(f"Repository {index}: Branch name cannot be empty")
        
        branch = repo.branch.strip()
        if not _is_valid_branch_name(branch):
            raise ConfigurationError(
                f"Repository {index}: Invalid branch name '{branch}'. "
                "Branch names cannot contain spaces, control characters, or certain special characters"
            )


def _validate_paths(config: AnalysisConfig) -> None:
    """
    Validate file and directory paths.
    
    Args:
        config: Configuration to validate
        
    Raises:
        ConfigurationError: If paths are invalid
    """
    # Validate cache directory
    try:
        cache_dir = config.cache_dir.expanduser().resolve()
        # Check if parent directory exists or can be created
        cache_dir.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        raise ConfigurationError(f"Invalid cache_dir: {e}")
    
    # Validate output file path
    try:
        output_file = config.output_file.expanduser().resolve()
        # Check if parent directory exists or can be created
        output_file.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        raise ConfigurationError(f"Invalid output_file path: {e}")


def _validate_llm_config(llm: LLMConfig) -> None:
    """
    Validate LLM configuration.
    
    Args:
        llm: LLM configuration to validate
        
    Raises:
        ConfigurationError: If LLM configuration is invalid
    """
    if not llm.provider or not llm.provider.strip():
        raise ConfigurationError("LLM provider cannot be empty")
    
    if not llm.model or not llm.model.strip():
        raise ConfigurationError("LLM model cannot be empty")
    
    if llm.temperature < 0 or llm.temperature > 2:
        raise ConfigurationError("LLM temperature must be between 0 and 2")
    
    # Validate max_tokens if specified
    if llm.max_tokens is not None:
        if llm.max_tokens <= 0:
            raise ConfigurationError("LLM max_tokens must be positive")
        if llm.max_tokens > 100000:  # Reasonable upper limit
            raise ConfigurationError("LLM max_tokens cannot exceed 100000")
    
    # Validate base_url if specified
    if llm.base_url is not None:
        if not llm.base_url.strip():
            raise ConfigurationError("LLM base_url cannot be empty")
        # Basic URL validation
        if not llm.base_url.startswith(('http://', 'https://')):
            raise ConfigurationError("LLM base_url must be a valid HTTP(S) URL")
    
    # Validate provider-specific requirements
    provider = llm.provider.lower().strip()
    if provider == "openai":
        if not llm.model.strip():
            raise ConfigurationError("OpenAI model name cannot be empty")
    elif provider == "openrouter":
        if not llm.model.strip():
            raise ConfigurationError("OpenRouter model name cannot be empty")
        # OpenRouter requires an API key
        if not llm.api_key:
            raise ConfigurationError("OpenRouter provider requires an API key")
    elif provider not in ["openai", "anthropic", "azure", "openrouter"]:
        raise ConfigurationError(
            f"Unsupported LLM provider '{provider}'. "
            "Supported providers: openai, anthropic, azure, openrouter"
        )


def _is_valid_git_url(url: str) -> bool:
    """
    Check if a URL is a valid git repository URL.
    
    Args:
        url: URL to validate
        
    Returns:
        bool: True if URL appears to be a valid git URL
    """
    url = url.strip()
    
    # Check for common git URL patterns
    git_patterns = [
        r'^https?://[^/]+/.+\.git$',  # HTTPS with .git suffix
        r'^https?://[^/]+/.+$',       # HTTPS without .git suffix (GitHub, etc.)
        r'^git@[^:]+:.+\.git$',       # SSH with .git suffix
        r'^git@[^:]+:.+$',            # SSH without .git suffix
        r'^ssh://git@[^/]+/.+$',      # SSH protocol
    ]
    
    for pattern in git_patterns:
        if re.match(pattern, url):
            return True
    
    # Additional validation using urlparse for HTTP(S) URLs
    if url.startswith(('http://', 'https://')):
        try:
            parsed = urlparse(url)
            return (
                parsed.netloc and 
                parsed.path and 
                len(parsed.path) > 1  # More than just "/"
            )
        except Exception:
            return False
    
    return False


def _is_valid_branch_name(branch: str) -> bool:
    """
    Check if a branch name is valid according to git naming rules.
    
    Args:
        branch: Branch name to validate
        
    Returns:
        bool: True if branch name is valid
    """
    branch = branch.strip()
    
    # Basic validation - git branch names cannot:
    # - Be empty
    # - Start or end with a slash
    # - Contain consecutive slashes
    # - Contain certain special characters
    # - Be just dots
    
    if not branch:
        return False
    
    if branch.startswith('/') or branch.endswith('/'):
        return False
    
    if '//' in branch:
        return False
    
    if branch in ['.', '..']:
        return False
    
    # Check for invalid characters
    invalid_chars = [' ', '\t', '\n', '\r', '~', '^', ':', '?', '*', '[', '\\', '@']
    for char in invalid_chars:
        if char in branch:
            return False
    
    # Check for control characters
    if any(ord(c) < 32 or ord(c) == 127 for c in branch):
        return False
    
    return True