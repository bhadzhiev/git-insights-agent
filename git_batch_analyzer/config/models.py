"""Configuration data models for Git Batch Analyzer."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import os


@dataclass
class RepositoryConfig:
    """Configuration for a single repository."""
    url: str
    branch: Optional[str] = None  # If None, use remote HEAD


@dataclass
class LLMConfig:
    """Configuration for LLM integration."""
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # For custom API endpoints like OpenRouter
    max_tokens: Optional[int] = None  # For controlling response length


@dataclass
class EmailConfig:
    """Configuration for sending email notifications."""
    sender_email: str
    sender_name: str = "Git Batch Analyzer"
    provider: str = "smtp"  # 'smtp' or 'mailjet'
    
    # Common fields
    api_key: Optional[str] = None  # Mailjet API key or SMTP username
    api_secret: Optional[str] = None  # Mailjet API secret or SMTP password
    
    # SMTP-specific fields
    smtp_server: Optional[str] = None  # e.g., smtp.gmail.com
    smtp_port: int = 587
    smtp_password: Optional[str] = None  # Alias for api_secret for clarity


@dataclass
class AnalysisConfig:
    """Main configuration for the Git Batch Analyzer."""
    repositories: List[RepositoryConfig]
    period_days: int = 7
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "git-analyzer")
    output_file: Path = field(default_factory=lambda: Path("report.md"))
    stale_days: Optional[int] = None  # Defaults to period_days if not specified
    fetch_depth: int = 200
    top_k_files: int = 10
    llm: Optional[LLMConfig] = None
    email: Optional[EmailConfig] = None
    max_workers: int = 4  # Number of parallel workers for repository processing
    
    def __post_init__(self):
        """Post-initialization processing."""
        # Convert string paths to Path objects
        if isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)
        if isinstance(self.output_file, str):
            self.output_file = Path(self.output_file)
            
        # Set stale_days default to period_days if not specified
        if self.stale_days is None:
            self.stale_days = self.period_days
            
        # Expand user paths
        self.cache_dir = self.cache_dir.expanduser()
        self.output_file = self.output_file.expanduser()
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def effective_stale_days(self) -> int:
        """Get the effective stale_days value (defaults to period_days)."""
        return self.stale_days if self.stale_days is not None else self.period_days
    
    def get_repo_cache_dir(self, repo_url: str) -> Path:
        """Get the cache directory for a specific repository."""
        # Extract repository name from URL for cache directory
        repo_name = repo_url.rstrip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        # Sanitize repo name for filesystem
        import re
        repo_name = re.sub(r'[^\w\-_.]', '_', repo_name)
        
        return self.cache_dir / repo_name