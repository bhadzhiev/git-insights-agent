"""Markdown generation tool for deterministic table rendering."""

from typing import Any, Dict, List, Optional, Union

from ..types import ToolResponse


class MdTool:
    """Tool for generating deterministic markdown tables and content."""
    
    def render_table(
        self,
        headers: List[str],
        rows: List[List[Any]],
        alignment: Optional[List[str]] = None
    ) -> ToolResponse:
        """Render a markdown table with deterministic formatting.
        
        Args:
            headers: List of column headers
            rows: List of rows, where each row is a list of cell values
            alignment: Optional list of alignment specs ('left', 'center', 'right')
            
        Returns:
            ToolResponse with rendered markdown table
        """
        try:
            if not headers:
                return ToolResponse.error_response("Headers cannot be empty")
            
            if not rows:
                return ToolResponse.success_response(self._render_empty_table(headers, alignment))
            
            # Validate row lengths
            expected_cols = len(headers)
            for i, row in enumerate(rows):
                if len(row) != expected_cols:
                    return ToolResponse.error_response(
                        f"Row {i} has {len(row)} columns, expected {expected_cols}"
                    )
            
            # Convert all values to strings and calculate column widths
            str_headers = [str(h) for h in headers]
            str_rows = [[str(cell) for cell in row] for row in rows]
            
            # Calculate minimum column widths
            col_widths = [len(header) for header in str_headers]
            for row in str_rows:
                for i, cell in enumerate(row):
                    col_widths[i] = max(col_widths[i], len(cell))
            
            # Ensure minimum width of 3 for alignment markers
            col_widths = [max(3, width) for width in col_widths]
            
            # Build the table
            table_lines = []
            
            # Header row
            header_cells = [
                str_headers[i].ljust(col_widths[i])
                for i in range(len(str_headers))
            ]
            table_lines.append("| " + " | ".join(header_cells) + " |")
            
            # Separator row
            separator_cells = []
            for i, width in enumerate(col_widths):
                align = alignment[i] if alignment and i < len(alignment) else 'left'
                separator_cells.append(self._create_separator(width, align))
            table_lines.append("| " + " | ".join(separator_cells) + " |")
            
            # Data rows
            for row in str_rows:
                row_cells = [
                    row[i].ljust(col_widths[i])
                    for i in range(len(row))
                ]
                table_lines.append("| " + " | ".join(row_cells) + " |")
            
            markdown_table = "\n".join(table_lines)
            
            return ToolResponse.success_response(markdown_table)
            
        except Exception as e:
            return ToolResponse.error_response(f"Error rendering table: {str(e)}")
    
    def render_metrics_table(self, pr_metrics: Dict[str, Any]) -> ToolResponse:
        """Render a standardized metrics table for PR analysis.
        
        Args:
            pr_metrics: Dictionary containing PR metrics data
            
        Returns:
            ToolResponse with rendered metrics table
        """
        try:
            headers = ["Metric", "Value"]
            rows = [
                ["Total PRs", str(pr_metrics.get("total_prs", 0))],
                ["Lead Time P50 (hours)", f"{pr_metrics.get('lead_time_p50', 0):.1f}"],
                ["Lead Time P75 (hours)", f"{pr_metrics.get('lead_time_p75', 0):.1f}"],
                ["Change Size P50", str(pr_metrics.get("change_size_p50", 0))],
                ["Change Size P75", str(pr_metrics.get("change_size_p75", 0))]
            ]
            
            return self.render_table(headers, rows, alignment=["left", "right"])
            
        except Exception as e:
            return ToolResponse.error_response(f"Error rendering metrics table: {str(e)}")
    
    def render_weekly_counts_table(self, weekly_counts: Dict[str, int]) -> ToolResponse:
        """Render a table of weekly PR counts.
        
        Args:
            weekly_counts: Dictionary mapping ISO weeks to PR counts
            
        Returns:
            ToolResponse with rendered weekly counts table
        """
        try:
            if not weekly_counts:
                return ToolResponse.success_response("No weekly data available.")
            
            headers = ["Week", "PR Count"]
            
            # Sort weeks chronologically
            sorted_weeks = sorted(weekly_counts.keys())
            rows = [[week, str(weekly_counts[week])] for week in sorted_weeks]
            
            return self.render_table(headers, rows, alignment=["left", "right"])
            
        except Exception as e:
            return ToolResponse.error_response(f"Error rendering weekly counts table: {str(e)}")
    
    def render_top_files_table(self, top_files: List[Dict[str, Union[str, int]]]) -> ToolResponse:
        """Render a table of top files by change frequency.
        
        Args:
            top_files: List of dictionaries with 'item' and 'count' keys
            
        Returns:
            ToolResponse with rendered top files table
        """
        try:
            if not top_files:
                return ToolResponse.success_response("No file change data available.")
            
            headers = ["File", "Changes"]
            rows = [[str(file_data.get("item", "")), str(file_data.get("count", 0))] 
                   for file_data in top_files]
            
            return self.render_table(headers, rows, alignment=["left", "right"])
            
        except Exception as e:
            return ToolResponse.error_response(f"Error rendering top files table: {str(e)}")
    
    def render_stale_branches_table(self, stale_branches: List[Dict[str, Any]]) -> ToolResponse:
        """Render a table of stale branches.
        
        Args:
            stale_branches: List of branch info dictionaries
            
        Returns:
            ToolResponse with rendered stale branches table
        """
        try:
            if not stale_branches:
                return ToolResponse.success_response("No stale branches found.")
            
            headers = ["Branch", "Last Commit", "Days Ago"]
            rows = []
            
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            
            for branch in stale_branches:
                branch_name = branch.get("name", "")
                last_commit = branch.get("last_commit_hash", "")[:8]  # Short hash
                
                # Calculate days ago
                timestamp_str = branch.get("last_commit_timestamp", "")
                try:
                    if timestamp_str:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        days_ago = (now - timestamp).days
                    else:
                        days_ago = "Unknown"
                except (ValueError, TypeError):
                    days_ago = "Unknown"
                
                rows.append([branch_name, last_commit, str(days_ago)])
            
            # Sort by branch name for deterministic output
            rows.sort(key=lambda x: x[0])
            
            return self.render_table(headers, rows, alignment=["left", "left", "right"])
            
        except Exception as e:
            return ToolResponse.error_response(f"Error rendering stale branches table: {str(e)}")
    
    def render_section(self, title: str, content: str, level: int = 2) -> ToolResponse:
        """Render a markdown section with title and content.
        
        Args:
            title: Section title
            content: Section content
            level: Header level (1-6)
            
        Returns:
            ToolResponse with rendered section
        """
        try:
            if not 1 <= level <= 6:
                return ToolResponse.error_response("Header level must be between 1 and 6")
            
            header_prefix = "#" * level
            section = f"{header_prefix} {title}\n\n{content}"
            
            return ToolResponse.success_response(section)
            
        except Exception as e:
            return ToolResponse.error_response(f"Error rendering section: {str(e)}")
    
    def combine_sections(self, sections: List[str]) -> ToolResponse:
        """Combine multiple markdown sections with proper spacing.
        
        Args:
            sections: List of markdown section strings
            
        Returns:
            ToolResponse with combined markdown content
        """
        try:
            # Filter out empty sections
            non_empty_sections = [s.strip() for s in sections if s and s.strip()]
            
            if not non_empty_sections:
                return ToolResponse.success_response("")
            
            # Join sections with double newlines for proper spacing
            combined = "\n\n".join(non_empty_sections)
            
            return ToolResponse.success_response(combined)
            
        except Exception as e:
            return ToolResponse.error_response(f"Error combining sections: {str(e)}")
    
    def _create_separator(self, width: int, alignment: str) -> str:
        """Create a table separator cell with proper alignment markers.
        
        Args:
            width: Column width
            alignment: Alignment type ('left', 'center', 'right')
            
        Returns:
            Separator string for the column
        """
        if alignment == 'center':
            return ":" + "-" * (width - 2) + ":"
        elif alignment == 'right':
            return "-" * (width - 1) + ":"
        else:  # left or default
            return "-" * width
    
    def _render_empty_table(self, headers: List[str], alignment: Optional[List[str]] = None) -> str:
        """Render an empty table with just headers.
        
        Args:
            headers: List of column headers
            alignment: Optional list of alignment specs
            
        Returns:
            Empty markdown table string
        """
        col_widths = [max(3, len(str(h))) for h in headers]
        
        # Header row
        header_cells = [str(headers[i]).ljust(col_widths[i]) for i in range(len(headers))]
        header_line = "| " + " | ".join(header_cells) + " |"
        
        # Separator row
        separator_cells = []
        for i, width in enumerate(col_widths):
            align = alignment[i] if alignment and i < len(alignment) else 'left'
            separator_cells.append(self._create_separator(width, align))
        separator_line = "| " + " | ".join(separator_cells) + " |"
        
        return header_line + "\n" + separator_line
    
    def render_user_stats_table(self, user_stats_list: List[Dict[str, Any]]) -> ToolResponse:
        """Render a table summarizing all user statistics.
        
        Args:
            user_stats_list: List of UserStats.to_dict() objects
            
        Returns:
            ToolResponse with rendered user statistics table
        """
        try:
            if not user_stats_list:
                return ToolResponse.success_response("No user statistics available.")
            
            headers = ["Developer", "Commits", "Merges", "Changes", "Top Work Type"]
            rows = []
            
            for user_stats in user_stats_list:
                username = user_stats.get('username', 'Unknown')
                total_commits = user_stats.get('total_commits', 0)
                total_merges = user_stats.get('total_merges', 0)
                total_changes = user_stats.get('total_changes', 0)
                
                # Find most common work type
                classifications = user_stats.get('commit_classifications', [])
                if classifications:
                    work_types = [c.get('work_type', 'unknown') for c in classifications]
                    from collections import Counter
                    most_common = Counter(work_types).most_common(1)[0]
                    top_work_type = f"{most_common[0]} ({most_common[1]})"
                else:
                    top_work_type = "N/A"
                
                rows.append([
                    username,
                    str(total_commits),
                    str(total_merges),
                    str(total_changes),
                    top_work_type
                ])
            
            # Sort by total commits (descending)
            rows.sort(key=lambda x: int(x[1]), reverse=True)
            
            return self.render_table(headers, rows, alignment=["left", "right", "right", "right", "left"])
            
        except Exception as e:
            return ToolResponse.error_response(f"Error rendering user stats table: {str(e)}")
    
    def render_user_detail_section(self, user_stats: Dict[str, Any]) -> ToolResponse:
        """Render a detailed section for a specific user's statistics and recommendations.
        
        Args:
            user_stats: UserStats.to_dict() object for a single user
            
        Returns:
            ToolResponse with rendered user detail section
        """
        try:
            username = user_stats.get('username', 'Unknown')
            sections = []
            
            # Basic stats
            basic_info = f"""**Email:** {user_stats.get('email', 'N/A')}
**Commits:** {user_stats.get('total_commits', 0)} | **Merges:** {user_stats.get('total_merges', 0)} | **Lines Changed:** {user_stats.get('total_changes', 0):,}"""
            sections.append(basic_info)
            
            # Work type breakdown
            classifications = user_stats.get('commit_classifications', [])
            if classifications:
                work_types = [c.get('work_type', 'unknown') for c in classifications]
                from collections import Counter
                work_type_counts = Counter(work_types)
                
                work_breakdown = "**Work Type Distribution:**\n"
                for work_type, count in work_type_counts.most_common():
                    percentage = (count / len(classifications)) * 100
                    work_breakdown += f"- {work_type.title()}: {count} commits ({percentage:.1f}%)\n"
                
                sections.append(work_breakdown.strip())
            
            # Top files
            top_files = user_stats.get('top_files', [])
            if top_files:
                files_section = "**Most Modified Files:**\n"
                for file_info in top_files[:5]:  # Top 5 files
                    filename = file_info.get('filename', 'Unknown')
                    mod_count = file_info.get('modification_count', 0)
                    changes = file_info.get('total_changes', 0)
                    files_section += f"- `{filename}` - {mod_count} modifications ({changes:,} lines)\n"
                
                sections.append(files_section.strip())
            
            # Commit patterns
            patterns = user_stats.get('commit_message_patterns', [])
            if patterns:
                patterns_section = "**Commit Message Patterns:**\n"
                for pattern in patterns:
                    patterns_section += f"- {pattern}\n"
                
                sections.append(patterns_section.strip())
            
            # Recommendations
            recommendations = user_stats.get('recommendations', [])
            if recommendations:
                rec_section = "**Personalized Recommendations:**\n"
                for i, rec in enumerate(recommendations, 1):
                    rec_section += f"{i}. {rec}\n"
                
                sections.append(rec_section.strip())
            
            # Code Review Insights (if available)
            code_review_insights = user_stats.get('code_review_insights', '')
            if code_review_insights and code_review_insights.strip():
                insights_section = "**Senior Developer Code Review Insights:**\n\n"
                insights_section += code_review_insights
                sections.append(insights_section.strip())
            
            # Combine all sections
            content = "\n\n".join(sections)
            
            return ToolResponse.success_response(content)
            
        except Exception as e:
            return ToolResponse.error_response(f"Error rendering user detail section: {str(e)}")
    
    def generate_report_filename(self, repo_name: str, period_days: int) -> str:
        """Generate a filename for the repository report.
        
        Args:
            repo_name: Repository name (format: "repo-branch" or just "repo")
            period_days: Analysis period in days
            
        Returns:
            Formatted filename: repo(branch)dateFrom-dateTo.md
        """
        from datetime import datetime, timedelta
        import re
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Format dates as YYYYMMDD
        from_date = start_date.strftime("%Y%m%d")
        to_date = end_date.strftime("%Y%m%d")
        
        # Parse repo_name to extract repo and branch
        # Expected format: "repo-name-branch" or just "repo-name"
        if '-' in repo_name:
            # Split on last dash to separate repo from branch
            parts = repo_name.rsplit('-', 1)
            if len(parts) == 2:
                repo_part, branch_part = parts
                # Clean parts for filename (remove invalid characters)
                clean_repo = re.sub(r'[^\w\-_.]', '_', repo_part)
                clean_branch = re.sub(r'[^\w\-_.]', '_', branch_part)
                return f"{clean_repo}({clean_branch}){from_date}-{to_date}.md"
        
        # If no branch detected, use whole name as repo
        clean_repo_name = re.sub(r'[^\w\-_.]', '_', repo_name)
        return f"{clean_repo_name}{from_date}-{to_date}.md"