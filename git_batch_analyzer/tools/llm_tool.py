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
            # Prepare the prompt with only aggregated data
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
            
            prompt = f"""Based on the following developer statistics, provide 3-5 personalized recommendations to help improve their coding practices and career development:

Developer Profile:
- Username: {user_stats.get('username', 'Unknown')}
- Total Commits: {user_stats.get('total_commits', 0)}
- Total Merges: {user_stats.get('total_merges', 0)}
- Total Changes: {user_stats.get('total_changes', 0)} lines
- Work Type Distribution: {work_type_summary}
- Top Files: {[f['filename'] for f in user_stats.get('top_files', [])][:3]}
- Message Patterns: {user_stats.get('commit_message_patterns', [])}

Provide specific, actionable recommendations tailored to this developer's patterns. Each recommendation should be:
- Maximum 50 words
- Focused on improvement or recognition of good practices
- Based on the actual data patterns shown
- Professional and constructive

Format as a simple list of recommendations."""

            # Generate recommendations
            message = HumanMessage(content=prompt)
            response = self.llm.invoke([message])
            
            recommendations_text = response.content.strip()
            
            # Parse recommendations into list (split by newlines and clean up)
            recommendations = []
            for line in recommendations_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Remove list markers like "1.", "-", "*"
                    clean_line = line.lstrip('0123456789.-* ')
                    if clean_line and len(clean_line.split()) <= 50:  # Max 50 words
                        recommendations.append(clean_line)
            
            return ToolResponse.success_response(recommendations[:5])  # Max 5 recommendations
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to generate user recommendations: {str(e)}")
    
    def generate_code_review_insights(self, user_stats: Dict[str, Any]) -> ToolResponse:
        """Generate senior developer code review insights for user's top modified files.
        
        Args:
            user_stats: UserStats.to_dict() format with user's coding patterns
            
        Returns:
            ToolResponse with code review insights from senior developer perspective
        """
        # Safety check - ensure no source code is being sent
        if not self._validate_no_source_code(user_stats):
            return ToolResponse.error_response("Safety check failed: potential source code detected in user stats")
        
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
            
            # Create file analysis summary without exposing code content
            file_analysis = []
            for file_info in top_files:
                filename = file_info.get('filename', 'unknown')
                mod_count = file_info.get('modification_count', 0)
                changes = file_info.get('total_changes', 0)
                
                file_analysis.append({
                    'filename': filename,
                    'modifications': mod_count,
                    'total_changes': changes,
                    'avg_changes_per_mod': round(changes / max(mod_count, 1), 1)
                })
            
            prompt = f"""As a senior software developer conducting a code review, analyze the file modification patterns for developer {username} and provide structured insights using proven code review practices.

# Developer Context
- **Total Commits**: {total_commits}
- **Work Distribution**: {work_type_summary}

# Top Modified Files Analysis
{file_analysis}

Using this comprehensive code review framework, provide analysis for each of the top 3 files:

## Per-File Analysis Template

For each file, provide:

**Role & Purpose**: What this file likely does based on its name and modification patterns

**Strengths Observed**:
- Positive patterns from modification frequency/size
- Architectural benefits suggested by the file's role

**Potential Issues** (use severity rubric):
- **Major**: Reliability/performance/design risks (high change frequency may indicate complexity)
- **Minor**: Quality/maintainability opportunities  
- **Nit**: Style/organization suggestions

**Recommendations**:
- **Design & Maintainability**: Single responsibility, DRY principles, clear boundaries
- **Performance**: If high-change file, consider hot path optimization
- **Reliability**: Error handling patterns for frequently changed code
- **Observability**: Logging/monitoring for critical files
- **Tests**: Coverage needs based on change frequency

## Key Focus Areas:
- Files with high `avg_changes_per_mod` may indicate complexity or technical debt
- Frequently modified files (high modification count) are candidates for:
  - Enhanced test coverage
  - Better error handling  
  - Performance optimization
  - Documentation updates
- File naming patterns suggest architectural organization

## Severity Rubric:
- **Major**: Design/reliability risks that affect system stability
- **Minor**: Quality improvements that enhance maintainability  
- **Nit**: Style/organization suggestions

Provide actionable, specific recommendations based on file patterns. Keep total response under 400 words."""

            # Generate code review insights
            message = HumanMessage(content=prompt)
            response = self.llm.invoke([message])
            
            insights = response.content.strip()
            
            return ToolResponse.success_response(insights)
            
        except Exception as e:
            return ToolResponse.error_response(f"Failed to generate code review insights: {str(e)}")