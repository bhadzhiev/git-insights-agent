"""User analysis tool for developer insights and recommendations."""

import re
from collections import Counter, defaultdict
from typing import Dict, List, Any, Tuple

from ..types import ToolResponse, UserStats, CommitClassification


class UserTool:
    """Tool for analyzing user/developer patterns and generating insights."""
    
    def __init__(self):
        """Initialize UserTool."""
        pass
    
    def analyze_users(self, commits: List[Dict[str, Any]], 
                     file_changes: Dict[str, List[Dict[str, Any]]]) -> ToolResponse:
        """Analyze user patterns from commits and file changes.
        
        Args:
            commits: List of commit data with author info
            file_changes: Dict mapping commit_hash -> list of file changes
            
        Returns:
            ToolResponse with list of UserStats
        """
        try:
            # Group commits by user
            user_commits = defaultdict(list)
            for commit in commits:
                user_key = (commit["author_name"], commit["author_email"])
                user_commits[user_key].append(commit)
            
            user_stats_list = []
            
            for (username, email), user_commit_list in user_commits.items():
                # Calculate basic stats
                total_commits = len(user_commit_list)
                total_merges = sum(1 for c in user_commit_list if self._is_merge_commit(c["message"]))
                
                # Analyze file patterns
                user_file_changes = []
                for commit in user_commit_list:
                    commit_files = file_changes.get(commit["hash"], [])
                    user_file_changes.extend(commit_files)
                
                # Calculate total changes
                total_changes = sum(fc.get("total_changes", 0) for fc in user_file_changes)
                
                # Get top files for this user
                top_files = self._get_user_top_files(user_file_changes)
                
                # Classify commits
                commit_classifications = self._classify_commits(user_commit_list)
                
                # Extract commit message patterns
                commit_patterns = self._extract_commit_patterns(user_commit_list)
                
                # Create UserStats object
                user_stats = UserStats(
                    username=username,
                    email=email,
                    total_commits=total_commits,
                    total_merges=total_merges,
                    total_changes=total_changes,
                    top_files=top_files,
                    commit_classifications=commit_classifications,
                    commit_message_patterns=commit_patterns,
                    recommendations=None  # Will be filled by LLM if enabled
                )
                
                user_stats_list.append(user_stats)
            
            # Sort by total commits (most active first)
            user_stats_list.sort(key=lambda u: u.total_commits, reverse=True)
            
            return ToolResponse.success_response(user_stats_list)
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to analyze users: {str(e)}")
    
    def _is_merge_commit(self, message: str) -> bool:
        """Check if a commit message indicates a merge commit."""
        merge_patterns = [
            r"^Merge pull request",
            r"^Merge branch",
            r"^Merge remote-tracking branch",
            r"^Merged in",
            r"^Merge.*into"
        ]
        
        for pattern in merge_patterns:
            if re.match(pattern, message, re.IGNORECASE):
                return True
        return False
    
    def _get_user_top_files(self, file_changes: List[Dict[str, Any]], k: int = 5) -> List[Dict[str, Any]]:
        """Get the top k files this user modifies most frequently.
        
        Args:
            file_changes: List of file change records
            k: Number of top files to return
            
        Returns:
            List of top files with change counts
        """
        file_counts = Counter()
        file_total_changes = defaultdict(int)
        
        for change in file_changes:
            filename = change.get("filename", "")
            if filename:
                file_counts[filename] += 1
                file_total_changes[filename] += change.get("total_changes", 0)
        
        # Get top k files by frequency
        top_files = []
        for filename, frequency in file_counts.most_common(k):
            top_files.append({
                "filename": filename,
                "frequency": frequency,
                "total_changes": file_total_changes[filename]
            })
        
        return top_files
    
    def _classify_commits(self, commits: List[Dict[str, Any]]) -> List[CommitClassification]:
        """Classify commits by work type using heuristic analysis.
        
        Args:
            commits: List of commit data
            
        Returns:
            List of CommitClassification objects
        """
        classifications = []
        
        for commit in commits:
            message = commit["message"].lower()
            work_type, confidence, reasoning = self._classify_commit_message(message)
            
            classification = CommitClassification(
                commit_hash=commit["hash"],
                work_type=work_type,
                confidence=confidence,
                reasoning=reasoning
            )
            classifications.append(classification)
        
        return classifications
    
    def _classify_commit_message(self, message: str) -> Tuple[str, float, str]:
        """Classify a single commit message.
        
        Args:
            message: Commit message (lowercase)
            
        Returns:
            Tuple of (work_type, confidence, reasoning)
        """
        # Define classification patterns with confidence scores
        patterns = [
            # Feature work
            (r"(feat|feature|add|implement|new)", "feature", 0.8, "Contains feature keywords"),
            
            # Bug fixes
            (r"(fix|bug|patch|resolve|correct)", "bugfix", 0.9, "Contains bugfix keywords"),
            
            # Refactoring
            (r"(refactor|cleanup|clean|reorganize|restructure)", "refactor", 0.8, "Contains refactoring keywords"),
            
            # Documentation
            (r"(doc|readme|comment|documentation)", "docs", 0.9, "Contains documentation keywords"),
            
            # Testing
            (r"(test|spec|coverage)", "test", 0.8, "Contains testing keywords"),
            
            # Configuration/Build
            (r"(config|build|deploy|ci|cd|pipeline)", "chore", 0.7, "Contains build/config keywords"),
            
            # Version/Release
            (r"(version|release|bump|tag)", "release", 0.8, "Contains release keywords"),
            
            # Merge commits
            (r"^merge", "merge", 0.9, "Merge commit"),
            
            # Performance
            (r"(perf|performance|optimize|speed)", "performance", 0.8, "Contains performance keywords"),
            
            # Security
            (r"(security|secure|vulnerability|auth)", "security", 0.8, "Contains security keywords")
        ]
        
        # Check patterns in order of specificity
        for pattern, work_type, confidence, reasoning in patterns:
            if re.search(pattern, message):
                return work_type, confidence, reasoning
        
        # Default classification for unmatched commits
        return "other", 0.3, "No specific pattern matched"
    
    def _extract_commit_patterns(self, commits: List[Dict[str, Any]], max_patterns: int = 3) -> List[str]:
        """Extract common patterns from commit messages.
        
        Args:
            commits: List of commit data
            max_patterns: Maximum number of patterns to return
            
        Returns:
            List of common commit message patterns
        """
        messages = [commit["message"] for commit in commits]
        
        # Extract common prefixes (e.g., "feat:", "fix:", etc.)
        prefixes = []
        for message in messages:
            # Look for conventional commit prefixes
            match = re.match(r"^([a-zA-Z]+)(\([^)]+\))?:", message)
            if match:
                prefix = match.group(1).lower()
                prefixes.append(f"{prefix}:")
            else:
                # Look for other common patterns
                words = message.split()
                if words:
                    first_word = words[0].lower()
                    if first_word in ["add", "fix", "update", "remove", "merge", "implement"]:
                        prefixes.append(f"{first_word}")
        
        # Count prefix frequencies
        prefix_counts = Counter(prefixes)
        
        # Get most common patterns
        patterns = []
        for prefix, count in prefix_counts.most_common(max_patterns):
            percentage = (count / len(messages)) * 100
            patterns.append(f"{prefix} ({count} commits, {percentage:.1f}%)")
        
        return patterns
    
    def generate_work_type_summary(self, user_stats_list: List[UserStats]) -> ToolResponse:
        """Generate a summary of work types across all users.
        
        Args:
            user_stats_list: List of UserStats objects
            
        Returns:
            ToolResponse with work type summary
        """
        try:
            work_type_counts = Counter()
            total_commits = 0
            
            for user_stats in user_stats_list:
                for classification in user_stats.commit_classifications:
                    work_type_counts[classification.work_type] += 1
                    total_commits += 1
            
            # Calculate percentages and create summary
            summary = []
            for work_type, count in work_type_counts.most_common():
                percentage = (count / total_commits) * 100 if total_commits > 0 else 0
                summary.append({
                    "work_type": work_type,
                    "count": count,
                    "percentage": percentage
                })
            
            return ToolResponse.success_response({
                "total_commits": total_commits,
                "work_type_distribution": summary
            })
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to generate work type summary: {str(e)}")