"""LLM integration tool for generating insights and summaries."""

import os
from typing import Dict, List, Optional, Any

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage

from ..types import ToolResponse


class LLMTool:
    """Tool for LLM-based analysis and summary generation."""
    
    def __init__(self, provider: str = "openai", model: str = "gpt-3.5-turbo", 
                 temperature: float = 0.7, api_key: Optional[str] = None,
                 base_url: Optional[str] = None, max_tokens: Optional[int] = None):
        """Initialize LLMTool with configuration.
        
        Args:
            provider: LLM provider ("openai", "openrouter", etc.)
            model: Model name to use
            temperature: Temperature for generation
            api_key: API key (if None, will use environment variable)
            base_url: Custom API base URL (for OpenRouter, etc.)
            max_tokens: Maximum tokens for response
        """
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        if provider not in ["openai", "openrouter"]:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        
        # Set up API key and base URL based on provider
        if provider == "openrouter":
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            elif not os.getenv("OPENAI_API_KEY"):
                raise ValueError("OpenRouter API key not provided and OPENAI_API_KEY environment variable not set")
            
            # Use OpenRouter's base URL
            base_url = base_url or "https://openrouter.ai/api/v1"
            
        elif provider == "openai":
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
            elif not os.getenv("OPENAI_API_KEY"):
                raise ValueError("OpenAI API key not provided and OPENAI_API_KEY environment variable not set")
        
        # Initialize the LLM with appropriate configuration
        llm_kwargs = {
            "model": model,
            "temperature": temperature
        }
        
        if base_url:
            llm_kwargs["base_url"] = base_url
            
        if max_tokens:
            llm_kwargs["max_tokens"] = max_tokens
        
        self.llm = ChatOpenAI(**llm_kwargs)
    
    def _validate_no_source_code(self, data: Any) -> bool:
        """Validate that data contains no source code.
        
        This is a safety check to ensure we never send source code to LLM.
        
        Args:
            data: Data to validate
            
        Returns:
            True if data is safe (no source code detected)
        """
        # Convert data to string for analysis
        data_str = str(data).lower()
        
        # Check for actual source code patterns (more specific to avoid false positives)
        code_indicators = [
            'def __init__(', 'function main(', 'class extends', 'import sys',
            'if __name__ == "__main__"', 'return null;', 'console.log(',
            '#!/usr/bin/', '<?php echo', '<script type=', '<html lang=',
            'select * from', 'insert into', 'create table if',
            'drop table if', 'rm -rf /', 'os.system(', 'eval(',
            'exec(', 'subprocess.call', '${', '<!--', '-->', '{%', '%}',
            'package.json:', 'requirements.txt:', 'import React'
        ]
        
        for indicator in code_indicators:
            if indicator in data_str:
                return False
        
        return True
    
    def generate_executive_summary(self, pr_metrics: Dict[str, Any], 
                                 weekly_data: Dict[str, int]) -> ToolResponse:
        """Generate an executive summary based on PR metrics and weekly data.
        
        Args:
            pr_metrics: Dictionary containing PR metrics (PRMetrics.to_dict() format)
            weekly_data: Dictionary of ISO week -> PR count
            
        Returns:
            ToolResponse with executive summary (120 words max) or error
        """
        # Safety check - ensure no source code is being sent
        if not self._validate_no_source_code(pr_metrics) or not self._validate_no_source_code(weekly_data):
            return ToolResponse.error_response("Safety check failed: potential source code detected in metrics data")
        
        try:
            # Prepare the prompt with aggregated metrics only
            prompt = f"""Based on the following development metrics, write a concise executive summary in exactly 120 words or less:

PR Metrics:
- Total PRs: {pr_metrics.get('total_prs', 0)}
- Lead Time 50th percentile: {pr_metrics.get('lead_time_p50', 0):.1f} hours
- Lead Time 75th percentile: {pr_metrics.get('lead_time_p75', 0):.1f} hours
- Change Size 50th percentile: {pr_metrics.get('change_size_p50', 0)} lines
- Change Size 75th percentile: {pr_metrics.get('change_size_p75', 0)} lines

Weekly PR Activity:
{weekly_data}

Focus on development velocity, code review efficiency, and overall team productivity trends. Keep it professional and data-driven. Maximum 120 words."""

            # Generate summary
            message = HumanMessage(content=prompt)
            response = self.llm.invoke([message])
            
            summary = response.content.strip()
            
            # Validate word count (approximately)
            word_count = len(summary.split())
            if word_count > 130:  # Allow small buffer
                return ToolResponse.error_response(f"Generated summary too long: {word_count} words (max 120)")
            
            return ToolResponse.success_response(summary)
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to generate executive summary: {str(e)}")
    
    def generate_organizational_trends(self, weekly_aggregated_data: List[Dict[str, Any]]) -> ToolResponse:
        """Generate organizational trend analysis based on weekly aggregated data.
        
        Args:
            weekly_aggregated_data: List of weekly aggregated metrics across repositories
            
        Returns:
            ToolResponse with organizational trends analysis or error
        """
        # Safety check - ensure no source code is being sent
        if not self._validate_no_source_code(weekly_aggregated_data):
            return ToolResponse.error_response("Safety check failed: potential source code detected in aggregated data")
        
        try:
            # Handle case when there's no weekly data (empty list)
            if not weekly_aggregated_data:
                prompt = """Analyze the development situation where no pull requests (PRs) were created during the analysis period.

Weekly Aggregated Data: No PR activity during the analysis period

Provide insights on:
1. Development velocity trends (lack of activity)
2. Team productivity patterns (identifying potential blockers)
3. Code quality indicators (impact of low activity)
4. Resource allocation observations (potential causes)
5. Recommendations for improvement (actionable steps)

Focus on organizational-level patterns and provide actionable insights for teams with low or no development activity. Keep the analysis professional and data-driven."""
            else:
                # Prepare the prompt with aggregated data
                prompt = f"""Analyze the following weekly aggregated development data across multiple repositories and provide organizational insights:

Weekly Aggregated Data:
{weekly_aggregated_data}

Provide insights on:
1. Development velocity trends
2. Team productivity patterns
3. Code quality indicators
4. Resource allocation observations
5. Recommendations for improvement

Focus on organizational-level patterns and trends. Be specific about what the data shows and provide actionable insights. Keep the analysis professional and data-driven."""

            # Generate analysis
            message = HumanMessage(content=prompt)
            response = self.llm.invoke([message])
            
            analysis = response.content.strip()
            
            return ToolResponse.success_response(analysis)
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to generate organizational trends: {str(e)}")
    
    def generate_user_recommendations(self, user_stats: Dict[str, Any]) -> ToolResponse:
        """Generate personalized recommendations for a specific developer.
        
        Args:
            user_stats: UserStats.to_dict() format with user's coding patterns
            
        Returns:
            ToolResponse with list of personalized recommendations (max 50 words each)
        """
        # Safety check - ensure no source code is being sent
        if not self._validate_no_source_code(user_stats):
            return ToolResponse.error_response("Safety check failed: potential source code detected in user stats")
        
        try:
            # Prepare the prompt with aggregated user statistics only
            work_types = [c['work_type'] for c in user_stats.get('commit_classifications', [])]
            work_type_summary = {}
            for work_type in set(work_types):
                work_type_summary[work_type] = work_types.count(work_type)
            
            prompt = f"""Based on the following developer statistics, provide 1-3 personalized recommendations to help improve their coding practices and career development:

Developer Profile:
- Username: {user_stats.get('username', 'Unknown')}
- Total Commits: {user_stats.get('total_commits', 0)}
- Total Merges: {user_stats.get('total_merges', 0)}
- Total Changes: {user_stats.get('total_changes', 0)} lines
- Work Type Distribution: {work_type_summary}
- Top Files: {[f['filename'] for f in user_stats.get('top_files', [])][:3]}
- Message Patterns: {user_stats.get('commit_message_patterns', [])}

Requirements:
- Provide ONLY the recommendations, no introductory text
- Each recommendation should be maximum 50 words
- Focus on improvement or recognition of good practices
- Base recommendations on the actual data patterns shown
- Be professional and constructive

Format as a simple list of recommendations, one per line, without numbers or bullets."""

            # Generate recommendations
            message = HumanMessage(content=prompt)
            response = self.llm.invoke([message])
            
            recommendations_text = response.content.strip()
            
            # Parse recommendations into list (split by newlines and clean up)
            recommendations = []
            lines = recommendations_text.split('\n')
            
            # Filter out introductory text and keep only actual recommendations
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Skip introductory sentences that contain "based on", "here are", etc.
                    if any(phrase in line.lower() for phrase in [
                        'based on the provided',
                        'based on the following', 
                        'here are',
                        'recommendations to help',
                        'personalized recommendations'
                    ]):
                        continue
                    
                    # Remove list markers like "1.", "-", "*", numbered lists
                    clean_line = line.lstrip('0123456789.-* ')
                    
                    # Skip if it's just a number or empty after cleaning
                    if clean_line and len(clean_line.split()) > 3 and len(clean_line.split()) <= 50:
                        recommendations.append(clean_line)
            
            return ToolResponse.success_response(recommendations[:5])  # Max 5 recommendations
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to generate user recommendations: {str(e)}")
    
    def generate_code_review_insights(self, user_stats: Dict[str, Any], file_contents: Dict[str, str]) -> ToolResponse:
        """Generate senior developer code review insights for user's top modified files.
        
        Args:
            user_stats: UserStats.to_dict() format with user's coding patterns
            file_contents: Dictionary mapping filename to its full code content.
            
        Returns:
            ToolResponse with code review insights from senior developer perspective
        """
        # NOTE: Safety check for source code removed as per user's explicit confirmation.
        # This function now expects to receive and process actual source code.
        
        try:
            top_files = user_stats.get('top_files', [])[:3]  # Top 3 most modified files
            if not top_files:
                return ToolResponse.success_response("No files available for code review analysis.")
            
            username = user_stats.get('username', 'Unknown')
            total_commits = user_stats.get('total_commits', 0)
            work_types = [c['work_type'] for c in user_stats.get('commit_classifications', [])]
            work_type_summary = {}
            for work_type in set(work_types):
                work_type_summary[work_type] = work_types.count(work_type)
            
            # Prepare detailed file analysis including code content
            detailed_file_analysis = []
            for file_info in top_files:
                filename = file_info.get('filename', 'unknown')
                code_content = file_contents.get(filename, "")
                
                # Truncate large files to avoid token limits, if necessary
                # This is a basic truncation; more sophisticated methods might be needed for very large files.
                if len(code_content) > 10000: # Example limit, adjust as needed
                    code_content = code_content[:5000] + "\n... [TRUNCATED] ...\n" + code_content[-5000:]
                
                detailed_file_analysis.append({
                    'filename': filename,
                    'code_content': code_content,
                    'modification_count': file_info.get('modification_count', 0),
                    'total_changes': file_info.get('total_changes', 0),
                })
            
            prompt = f"""As a senior software developer conducting a comprehensive code review, analyze the provided code files for developer {username}. Focus on the following criteria:

# Code Review Criteria:
1.  **Naming Conventions**: Assess clarity, consistency, and adherence to established patterns (e.g., camelCase, snake_case, PascalCase for variables, functions, classes).
2.  **Design Patterns**: Identify adherence to or deviation from common design patterns (e.g., Singleton, Factory, Observer, Strategy) where applicable. Suggest improvements if a pattern could enhance maintainability or scalability.
3.  **Complexity Levels**: Evaluate for overly long methods/functions, deep nesting of `if`/`else` statements or loops, and overall cyclomatic complexity. Suggest refactoring for readability and testability.
4.  **Formatting and Style**: Check for consistency with general coding style guidelines (e.g., indentation, line breaks, spacing, brace placement). Point out any deviations.
5.  **Comments and Documentation**: Assess the presence, clarity, and quality of inline comments, function/method docstrings, and class documentation. Ensure they explain *why* code exists, not just *what* it does.

# Developer Context (for reference, do not directly review these metrics):
- **Username**: {username}
- **Top Modified Files**: {[f['filename'] for f in top_files]}

# Files for Review:
"""
            
            for file_data in detailed_file_analysis:
                prompt += f"""
---
File: {file_data['filename']} ---
```
{file_data['code_content']}
```

"""
            
            prompt += f"""
Based on the above code and the specified criteria, provide your review. If you find problems, give concrete recommendations for improvements. If no significant issues are found, give a brief confirmation that the file is in good condition. Be concise and professional.

Provide your review in a structured format, addressing each file individually. For each file, clearly state any issues found, categorized by the criteria, and provide actionable recommendations. If a file is in good condition, state that explicitly.

Example format for a file with issues:

### File: example.py

**Naming Conventions**: Issue - Variable `x` is too generic. Recommendation - Rename to `user_count` for clarity.
**Complexity**: Issue - `process_data` method has 5 nested if statements. Recommendation - Refactor using Strategy pattern or extract helper methods.
**Comments**: Issue - No docstring for `calculate_total`. Recommendation - Add a docstring explaining its purpose and parameters.

Example format for a file in good condition:

### File: good_code.js

This file appears to be in good condition, adhering to all specified code review criteria.

---

Remember to be specific and actionable in your recommendations. If a file is very large and truncated, focus on the visible parts and general patterns.
"""

            # Generate code review insights
            message = HumanMessage(content=prompt)
            response = self.llm.invoke([message])
            
            insights = response.content.strip()
            
            return ToolResponse.success_response(insights)
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to generate code review insights: {str(e)}")
    
    def analyze_commit_message_quality(self, commits_data: List[Dict[str, Any]]) -> ToolResponse:
        """Analyze how well commit messages correspond to their actual changes.
        
        Args:
            commits_data: List of commits with message, files changed, and diff stats
            
        Returns:
            ToolResponse with commit message quality analysis
        """
        try:
            if not commits_data:
                return ToolResponse.success_response("No commits available for message quality analysis.")
            
            # Sample a subset of commits to analyze (to avoid token limits)
            max_commits = 10
            sample_commits = commits_data[:max_commits] if len(commits_data) > max_commits else commits_data
            
            # Prepare analysis data
            commit_analysis = []
            for commit in sample_commits:
                commit_hash = commit.get('hash', 'unknown')[:8]  # Short hash
                message = commit.get('message', 'No message')
                files_changed = commit.get('files_changed', [])
                diff_stats = commit.get('diff_stats', {})
                
                # Summarize file changes
                files_summary = []
                for file_info in files_changed[:5]:  # Top 5 files to avoid token overflow
                    filename = file_info.get('filename', 'unknown')
                    additions = file_info.get('additions', 0)
                    deletions = file_info.get('deletions', 0)
                    files_summary.append({
                        'file': filename,
                        'changes': f"+{additions}/-{deletions}"
                    })
                
                commit_analysis.append({
                    'hash': commit_hash,
                    'message': message,
                    'files_summary': files_summary,
                    'total_files': diff_stats.get('files_changed', 0),
                    'total_changes': diff_stats.get('total_changes', 0)
                })
            
            prompt = f"""As a senior developer performing code review, analyze how well each commit message describes the actual changes made. Rate the quality of commit messages based on:

**Evaluation Criteria:**
1. **Descriptiveness**: Does the message clearly explain what was changed?
2. **Accuracy**: Does the message match the actual files and scope of changes?
3. **Convention**: Does it follow good commit message practices (imperative mood, proper scope)?
4. **Completeness**: Does it capture the essence of what was modified?

**Commit Analysis Data:**
"""
            
            for i, commit in enumerate(commit_analysis, 1):
                prompt += f"""
**Commit {i}:** {commit['hash']}
**Message:** "{commit['message']}"
**Changes:** {commit['total_files']} files, {commit['total_changes']} lines
**Files Modified:** {', '.join([f"{f['file']} ({f['changes']})" for f in commit['files_summary']])}
{'...' if len(commits_data) > len(commit['files_summary']) else ''}

"""
            
            prompt += f"""
**Analysis Instructions:**
- For each commit, provide a quality score (1-5 scale where 5 is excellent)
- Briefly explain your reasoning for the score
- Identify patterns across commits (good practices or areas for improvement)
- Provide 2-3 actionable recommendations for better commit messages

**Example Analysis Format:**
### Commit 1 (abc123): Score 3/5
**Reasoning:** Message is vague ("fix bug") but changes suggest specific form validation fixes. Should be more specific about what was fixed.

### Summary & Recommendations:
1. Use more descriptive verbs and specific details
2. Include the component or feature being modified
3. Follow conventional commit format when possible

Be concise but specific in your analysis. Focus on how well messages communicate the intent and scope of changes."""

            # Generate analysis
            message = HumanMessage(content=prompt)
            response = self.llm.invoke([message])
            
            analysis = response.content.strip()
            
            return ToolResponse.success_response(analysis)
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to analyze commit message quality: {str(e)}")