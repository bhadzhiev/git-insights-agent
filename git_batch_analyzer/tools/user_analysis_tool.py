"""User analysis tool for personalized developer insights and recommendations."""

import re
from collections import defaultdict, Counter
from typing import Dict, List, Any, Tuple
from pathlib import Path

from ..types import ToolResponse, UserStats, CommitClassification
from .git_tool import GitTool


class UserAnalysisTool:
    """Tool for analyzing individual developer patterns and generating personalized recommendations."""
    
    def __init__(self, repo_path: Path):
        """Initialize UserAnalysisTool with repository path.
        
        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = Path(repo_path)
        self.git_tool = GitTool(repo_path)
        
        # Classification patterns for commit messages
        self.work_type_patterns = {
            'feature': [
                r'feat(?:ure)?[:\s]',
                r'add(?:ed|ing)?[:\s]',
                r'implement(?:ed|ing)?[:\s]',
                r'new[:\s]',
                r'create(?:d|ing)?[:\s]',
                r'introduce[:\s]'
            ],
            'bugfix': [
                r'fix(?:ed|es|ing)?[:\s]',
                r'bug[:\s]',
                r'resolve(?:d|s)?[:\s]',
                r'patch[:\s]',
                r'repair[:\s]',
                r'hotfix[:\s]'
            ],
            'refactor': [
                r'refactor(?:ed|ing)?[:\s]',
                r'restructure[:\s]',
                r'rewrite[:\s]',
                r'reorganize[:\s]',
                r'cleanup[:\s]',
                r'clean up[:\s]'
            ],
            'docs': [
                r'docs?[:\s]',
                r'documentation[:\s]',
                r'readme[:\s]',
                r'comment(?:ed|ing)?[:\s]',
                r'document[:\s]'
            ],
            'test': [
                r'test(?:ed|ing|s)?[:\s]',
                r'spec[:\s]',
                r'coverage[:\s]',
                r'unit[:\s]test',
                r'integration[:\s]test'
            ],
            'style': [
                r'style[:\s]',
                r'format(?:ted|ting)?[:\s]',
                r'linting?[:\s]',
                r'whitespace[:\s]',
                r'typo[:\s]'
            ],
            'chore': [
                r'chore[:\s]',
                r'maintenance[:\s]',
                r'update[:\s](?:dependencies|deps)',
                r'bump[:\s]',
                r'version[:\s]',
                r'config[:\s]'
            ]
        }

    def analyze_all_users(self, branch: str, since_days: int) -> ToolResponse:
        """Analyze all users who have committed to the repository.
        
        Args:
            branch: Branch to analyze
            since_days: Number of days to look back
            
        Returns:
            ToolResponse with list of UserStats for all users
        """
        try:
            # Get all commits (not just merges)
            all_commits_response = self.git_tool.log_all_commits(branch, since_days)
            if not all_commits_response.success:
                return all_commits_response
            
            commits = all_commits_response.data or []
            if not commits:
                return ToolResponse.success_response([])
            
            # Get merge commits for merge statistics
            merge_commits_response = self.git_tool.log_merges(branch, since_days)
            merge_commits = merge_commits_response.data or [] if merge_commits_response.success else []
            
            # Group commits by user
            user_commits = defaultdict(list)
            for commit in commits:
                user_key = (commit['author_name'], commit['author_email'])
                user_commits[user_key].append(commit)
            
            # Analyze each user
            user_stats_list = []
            for (username, email), commits in user_commits.items():
                user_stats = self._analyze_single_user(username, email, commits, merge_commits)
                if user_stats:
                    user_stats_list.append(user_stats.to_dict())
            
            return ToolResponse.success_response(user_stats_list)
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to analyze users: {str(e)}")

    def _analyze_single_user(
        self, 
        username: str, 
        email: str, 
        commits: List[Dict[str, Any]], 
        merge_commits: List[Dict[str, Any]]
    ) -> UserStats:
        """Analyze a single user's commit patterns.
        
        Args:
            username: User's name
            email: User's email
            commits: All commits by this user
            merge_commits: All merge commits to check against
            
        Returns:
            UserStats object with analysis results
        """
        try:
            # Count merges by this user
            user_merges = [mc for mc in merge_commits if mc.get('author') == username]
            
            # Get file hotspots for this user
            top_files = self._get_user_file_hotspots(commits)
            
            # Classify commits
            commit_classifications = self._classify_user_commits(commits)
            
            # Extract commit message patterns
            commit_message_patterns = self._extract_message_patterns(commits)
            
            # Calculate total changes (requires file-level analysis)
            total_changes = self._calculate_total_changes(commits)
            
            return UserStats(
                username=username,
                email=email,
                total_commits=len(commits),
                total_merges=len(user_merges),
                total_changes=total_changes,
                top_files=top_files,
                commit_classifications=commit_classifications,
                commit_message_patterns=commit_message_patterns,
                recommendations=None  # Will be filled by LLM
            )
            
        except Exception as e:
            # Return basic stats if detailed analysis fails
            return UserStats(
                username=username,
                email=email,
                total_commits=len(commits),
                total_merges=0,
                total_changes=0,
                top_files=[],
                commit_classifications=[],
                commit_message_patterns=[],
                recommendations=None
            )

    def _get_user_file_hotspots(self, commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify files this user modifies most frequently.
        
        Args:
            commits: User's commits
            
        Returns:
            List of files with change counts, sorted by frequency
        """
        file_counts = defaultdict(lambda: {'count': 0, 'total_changes': 0})
        
        # Files/directories to exclude from analysis
        excluded_patterns = [
            # IDE and editor files
            '.idea/',
            '.vscode/',
            '.git/',
            
            # Package management files
            'package.json',
            'package-lock.json',
            'yarn.lock',
            'pnpm-lock.yaml',
            'npm-shrinkwrap.json',
            
            # Python package management
            'requirements.txt',
            'requirements-dev.txt',
            'requirements/*.txt',
            'pyproject.toml',
            'setup.py',
            'setup.cfg',
            'Pipfile',
            'Pipfile.lock',
            'poetry.lock',
            'uv.lock',
            
            # Build and dependency directories
            'node_modules/',
            'target/',
            'build/',
            'dist/',
            '__pycache__/',
            '*.pyc',
            '.pytest_cache/',
            '.coverage',
            'htmlcov/',
            '.tox/',
            '.venv/',
            'venv/',
            '.env/',
            
            # System and temporary files
            '.DS_Store',
            'Thumbs.db',
            '*.log',
            '*.tmp',
            '*.temp',
            
            # Environment files
            '.env',
            '.env.local',
            '.env.development',
            '.env.production',
            '.env.*',
            
            # Documentation and config files that change frequently but aren't core code
            'README.md',
            'CHANGELOG.md',
            '.gitignore',
            '.dockerignore',
            'Dockerfile*',
            'docker-compose*.yml',
            '.editorconfig',
            '.prettierrc*',
            'eslint.config.*',
            '.eslintrc*',
            'tsconfig.json',
            'jsconfig.json'
        ]
        
        for commit in commits:
            # Get files changed in this commit
            files_response = self.git_tool.get_commit_files(commit['hash'])
            if files_response.success and files_response.data:
                for file_change in files_response.data:
                    filename = file_change['filename']
                    
                    # Skip excluded files/directories
                    if self._should_exclude_file(filename, excluded_patterns):
                        continue
                    
                    file_counts[filename]['count'] += 1
                    file_counts[filename]['total_changes'] += file_change['total_changes']
        
        # Sort by frequency and return top 10
        sorted_files = sorted(
            file_counts.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:10]
        
        return [
            {
                'filename': filename,
                'modification_count': stats['count'],
                'total_changes': stats['total_changes']
            }
            for filename, stats in sorted_files
        ]

    def _classify_user_commits(self, commits: List[Dict[str, Any]]) -> List[CommitClassification]:
        """Classify user's commits by work type.
        
        Args:
            commits: User's commits
            
        Returns:
            List of CommitClassification objects
        """
        classifications = []
        
        for commit in commits:
            message = commit['message'].lower()
            best_match = None
            best_confidence = 0.0
            best_reasoning = ""
            
            for work_type, patterns in self.work_type_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, message, re.IGNORECASE):
                        confidence = min(1.0, len(re.findall(pattern, message, re.IGNORECASE)) * 0.8)
                        if confidence > best_confidence:
                            best_match = work_type
                            best_confidence = confidence
                            best_reasoning = f"Matched pattern: {pattern}"
            
            # Default classification if no pattern matches
            if not best_match:
                best_match = 'chore'
                best_confidence = 0.3
                best_reasoning = "No specific pattern matched, defaulted to chore"
            
            classifications.append(CommitClassification(
                commit_hash=commit['hash'],
                work_type=best_match,
                confidence=best_confidence,
                reasoning=best_reasoning
            ))
        
        return classifications

    def _extract_message_patterns(self, commits: List[Dict[str, Any]]) -> List[str]:
        """Extract common patterns from commit messages.
        
        Args:
            commits: User's commits
            
        Returns:
            List of common message patterns
        """
        # Extract first words/phrases from commit messages
        patterns = []
        
        # Get first word patterns
        first_words = [commit['message'].split()[0].lower() for commit in commits if commit['message']]
        word_counts = Counter(first_words)
        
        # Return patterns that appear more than once
        common_patterns = [
            f"Often starts commits with '{word}' ({count} times)"
            for word, count in word_counts.most_common(3)
            if count > 1
        ]
        
        # Check for conventional commit patterns
        conventional_pattern = r'^(feat|fix|docs|style|refactor|test|chore)(\(.+\))?: '
        conventional_commits = [
            commit for commit in commits 
            if re.match(conventional_pattern, commit['message'], re.IGNORECASE)
        ]
        
        if len(conventional_commits) > len(commits) * 0.3:  # 30% or more use conventional commits
            common_patterns.append(f"Uses conventional commit format in {len(conventional_commits)}/{len(commits)} commits")
        
        return common_patterns[:5]  # Return top 5 patterns

    def _calculate_total_changes(self, commits: List[Dict[str, Any]]) -> int:
        """Calculate total lines changed by user across all commits.
        
        Args:
            commits: User's commits
            
        Returns:
            Total number of lines added + deleted
        """
        total_changes = 0
        
        for commit in commits:
            files_response = self.git_tool.get_commit_files(commit['hash'])
            if files_response.success and files_response.data:
                for file_change in files_response.data:
                    total_changes += file_change['total_changes']
        
        return total_changes

    def generate_user_recommendations(
        self, 
        user_stats: UserStats, 
        repository_metrics: Dict[str, Any]
    ) -> ToolResponse:
        """Generate personalized recommendations for a user using rule-based analysis.
        
        Args:
            user_stats: User's statistics and patterns
            repository_metrics: Overall repository metrics for context
            
        Returns:
            ToolResponse with list of recommendation strings
        """
        try:
            recommendations = []
            
            # Analyze commit patterns
            if user_stats.commit_classifications:
                work_types = [c.work_type for c in user_stats.commit_classifications]
                work_type_counts = Counter(work_types)
                
                # Feature/bugfix balance recommendation
                feature_count = work_type_counts.get('feature', 0)
                bugfix_count = work_type_counts.get('bugfix', 0)
                total_work = feature_count + bugfix_count
                
                if total_work > 0:
                    bug_ratio = bugfix_count / total_work
                    if bug_ratio > 0.6:
                        recommendations.append(
                            "High bug-to-feature ratio suggests focus on code quality and testing might help reduce future fixes."
                        )
                    elif bug_ratio < 0.2 and feature_count > 5:
                        recommendations.append(
                            "Strong focus on features - consider adding more tests to prevent future issues."
                        )
                
                # Test commitment recommendation
                test_count = work_type_counts.get('test', 0)
                if user_stats.total_commits > 10 and test_count == 0:
                    recommendations.append(
                        "No test-related commits detected. Adding tests could improve code reliability."
                    )
                elif test_count > total_work * 0.3:
                    recommendations.append(
                        "Excellent testing discipline! Your thorough testing approach helps team code quality."
                    )
                
                # Documentation recommendation
                docs_count = work_type_counts.get('docs', 0)
                if user_stats.total_commits > 10 and docs_count == 0:
                    recommendations.append(
                        "Consider adding documentation commits to help team knowledge sharing."
                    )
            
            # File hotspot recommendations
            if user_stats.top_files:
                top_file = user_stats.top_files[0]
                if top_file['modification_count'] > user_stats.total_commits * 0.4:
                    recommendations.append(
                        f"You modify {top_file['filename']} frequently. Consider if it needs refactoring to reduce complexity."
                    )
            
            # Commit frequency recommendations
            if user_stats.total_commits > 50:
                recommendations.append(
                    "High commit activity shows strong engagement. Consider mentoring newer team members."
                )
            elif user_stats.total_commits < 5:
                recommendations.append(
                    "Low commit activity detected. Consider breaking larger changes into smaller, more frequent commits."
                )
            
            # Message pattern recommendations
            conventional_commit_pattern = any(
                'conventional commit' in pattern.lower() 
                for pattern in user_stats.commit_message_patterns
            )
            if not conventional_commit_pattern and user_stats.total_commits > 5:
                recommendations.append(
                    "Consider adopting conventional commit format (feat:, fix:, docs:) for better change tracking."
                )
            
            return ToolResponse.success_response(recommendations[:5])  # Max 5 recommendations
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to generate recommendations: {str(e)}")

    def _should_exclude_file(self, filename: str, excluded_patterns: List[str]) -> bool:
        """Check if a file should be excluded from analysis based on patterns.
        
        Args:
            filename: File path to check
            excluded_patterns: List of patterns to exclude
            
        Returns:
            True if file should be excluded, False otherwise
        """
        import fnmatch
        
        for pattern in excluded_patterns:
            # Check if filename starts with pattern (for directories like .idea/)
            if pattern.endswith('/') and filename.startswith(pattern):
                return True
            # Check wildcard patterns (for files like *.log)
            elif '*' in pattern and fnmatch.fnmatch(filename, pattern):
                return True
            # Check exact filename matches
            elif filename == pattern:
                return True
            # Check if file is within excluded directory
            elif '/' in filename and pattern.rstrip('/') in filename.split('/'):
                return True
        
        return False