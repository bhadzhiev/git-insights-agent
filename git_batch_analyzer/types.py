"""Core data types and state management for Git Batch Analyzer."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict, Union
from pathlib import Path


@dataclass
class ToolResponse:
    """Consistent response format for all tool operations."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    
    @classmethod
    def success_response(cls, data: Any = None) -> "ToolResponse":
        """Create a successful response."""
        return cls(success=True, data=data)
    
    @classmethod
    def error_response(cls, error: str) -> "ToolResponse":
        """Create an error response."""
        return cls(success=False, error=error)


@dataclass
class MergeCommit:
    """Represents a merge commit with its metadata."""
    hash: str
    timestamp: datetime
    message: str
    parents: List[str]
    author: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "hash": self.hash,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "parents": self.parents,
            "author": self.author
        }


@dataclass
class DiffStats:
    """Statistics about code changes in a commit or PR."""
    files_changed: int
    insertions: int
    deletions: int
    total_changes: int
    
    def __post_init__(self):
        """Calculate total changes."""
        self.total_changes = self.insertions + self.deletions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "files_changed": self.files_changed,
            "insertions": self.insertions,
            "deletions": self.deletions,
            "total_changes": self.total_changes
        }


@dataclass
class BranchInfo:
    """Information about a git branch."""
    name: str
    last_commit_hash: str
    last_commit_timestamp: datetime
    is_stale: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "last_commit_hash": self.last_commit_hash,
            "last_commit_timestamp": self.last_commit_timestamp.isoformat(),
            "is_stale": self.is_stale
        }


@dataclass
class CommitClassification:
    """Classification of a commit's work type."""
    commit_hash: str
    work_type: str  # feature, bugfix, refactor, docs, test, chore, etc.
    confidence: float  # 0.0-1.0 confidence score
    reasoning: Optional[str] = None  # Why this classification was chosen
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "commit_hash": self.commit_hash,
            "work_type": self.work_type,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


@dataclass
class UserStats:
    """Statistics and analysis for a specific user/developer."""
    username: str
    email: str
    total_commits: int
    total_merges: int
    total_changes: int  # Total lines added + deleted
    top_files: List[Dict[str, Union[str, int]]]  # Files this user modifies most
    commit_classifications: List[CommitClassification]
    commit_message_patterns: List[str]  # Common patterns in commit messages
    recommendations: List[str] = None  # LLM-generated recommendations (≤50 words each)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "username": self.username,
            "email": self.email,
            "total_commits": self.total_commits,
            "total_merges": self.total_merges,
            "total_changes": self.total_changes,
            "top_files": self.top_files,
            "commit_classifications": [c.to_dict() for c in self.commit_classifications],
            "commit_message_patterns": self.commit_message_patterns,
            "recommendations": self.recommendations or []
        }


@dataclass
class PRMetrics:
    """Aggregated metrics for pull requests/merge commits."""
    total_prs: int
    lead_time_p50: float  # 50th percentile lead time in hours
    lead_time_p75: float  # 75th percentile lead time in hours
    change_size_p50: int  # 50th percentile total changes
    change_size_p75: int  # 75th percentile total changes
    weekly_pr_counts: Dict[str, int]  # ISO week -> PR count
    top_files: List[Dict[str, Union[str, int]]]  # Top k files by change frequency
    user_stats: List[UserStats] = None  # Per-user statistics and recommendations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_prs": self.total_prs,
            "lead_time_p50": self.lead_time_p50,
            "lead_time_p75": self.lead_time_p75,
            "change_size_p50": self.change_size_p50,
            "change_size_p75": self.change_size_p75,
            "weekly_pr_counts": self.weekly_pr_counts,
            "top_files": self.top_files,
            "user_stats": [u.to_dict() for u in self.user_stats] if self.user_stats else []
        }


class AnalysisState(TypedDict):
    """State object passed between LangGraph workflow nodes."""
    # Configuration
    config: Dict[str, Any]  # AnalysisConfig as dict
    repository_url: str
    repository_name: str
    branch: str  # Configured branch (may be ignored)
    actual_branch: Optional[str]  # Branch actually analyzed (determined by git)
    cache_path: Path
    
    # Raw git data
    merge_commits: List[Dict[str, Any]]  # MergeCommit.to_dict() results
    all_commits: List[Dict[str, Any]]  # All commits (not just merges) during analysis period
    branches: List[Dict[str, Any]]  # BranchInfo.to_dict() results
    diff_stats: List[Dict[str, Any]]  # DiffStats.to_dict() results
    
    # Calculated metrics
    pr_metrics: Optional[Dict[str, Any]]  # PRMetrics.to_dict() result
    stale_branches: List[Dict[str, Any]]  # Filtered stale BranchInfo.to_dict() results
    
    # Report sections
    executive_summary: Optional[str]
    tables_markdown: Optional[str]
    org_trends: Optional[str]
    final_report: Optional[str]
    
    # Processing status
    sync_completed: bool
    collect_completed: bool
    metrics_completed: bool
    stale_completed: bool
    user_analysis_completed: bool
    tables_completed: bool
    exec_summary_completed: bool
    org_trend_completed: bool
    assembler_completed: bool
    
    # User analysis data
    user_stats: Optional[List[Dict[str, Any]]]
    
    # Error tracking
    errors: List[str]


def create_initial_state(
    config: Dict[str, Any],
    repository_url: str,
    repository_name: str,
    branch: str,
    cache_path: Path
) -> AnalysisState:
    """Create an initial analysis state for a repository."""
    return AnalysisState(
        # Configuration
        config=config,
        repository_url=repository_url,
        repository_name=repository_name,
        branch=branch,
        cache_path=cache_path,
        
        # Raw git data
        merge_commits=[],
        all_commits=[],
        branches=[],
        diff_stats=[],
        
        # Calculated metrics
        pr_metrics=None,
        stale_branches=[],
        
        # Report sections
        executive_summary=None,
        tables_markdown=None,
        org_trends=None,
        final_report=None,
        
        # Processing status
        sync_completed=False,
        collect_completed=False,
        metrics_completed=False,
        stale_completed=False,
        user_analysis_completed=False,
        tables_completed=False,
        exec_summary_completed=False,
        org_trend_completed=False,
        assembler_completed=False,
        
        # User analysis data
        user_stats=None,
        
        # Error tracking
        errors=[]
    )