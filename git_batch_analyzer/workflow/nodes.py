"""LangGraph workflow nodes for Git Batch Analyzer."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List

from ..types import AnalysisState, BranchInfo, PRMetrics
from ..tools.git_tool import GitTool
from ..tools.calc_tool import CalcTool
from ..tools.md_tool import MdTool
from ..tools.llm_tool import LLMTool
from ..tools.user_analysis_tool import UserAnalysisTool


def sync_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for repository cloning and fetching.
    
    This node handles:
    - Cloning the repository if it doesn't exist
    - Fetching latest changes from remote
    - Determining and checking out the default branch
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with sync_completed status and actual_branch used
    """
    try:
        git_tool = GitTool(state["cache_path"])
        config = state["config"]
        
        # Clone repository if it doesn't exist
        if not state["cache_path"].exists():
            clone_response = git_tool.clone(
                state["repository_url"], 
                depth=config.get("fetch_depth", 200)
            )
            if not clone_response.success:
                state["errors"].append(f"Failed to clone repository: {clone_response.error}")
                return {"sync_completed": False, "errors": state["errors"]}
        
        # Fetch all branches from remote
        fetch_response = git_tool.fetch()
        if not fetch_response.success:
            state["errors"].append(f"Failed to fetch updates: {fetch_response.error}")
            return {"sync_completed": False, "errors": state["errors"]}
        
        # Use the specified branch (since we're now analyzing specific branches)
        specified_branch = state["branch"]
        
        # Checkout the specified branch
        checkout_fetch_response = git_tool.fetch(specified_branch)
        if not checkout_fetch_response.success:
            state["errors"].append(f"Failed to checkout branch '{specified_branch}': {checkout_fetch_response.error}")
            return {"sync_completed": False, "errors": state["errors"]}
        
        return {
            "sync_completed": True,
            "actual_branch": specified_branch  # Track which branch was actually analyzed
        }
        
    except Exception as e:
        state["errors"].append(f"Sync node error: {str(e)}")
        return {"sync_completed": False, "errors": state["errors"]}


def collect_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for gathering merge commits and branch data.
    
    This node handles:
    - Collecting merge commits from the specified time period
    - Gathering diff statistics for each merge commit
    - Collecting information about all remote branches
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with collected git data
    """
    try:
        if not state["sync_completed"]:
            state["errors"].append("Cannot collect data: sync not completed")
            return {"collect_completed": False, "errors": state["errors"]}
        
        git_tool = GitTool(state["cache_path"])
        config = state["config"]
        period_days = config.get("period_days", 7)
        
        # Use actual_branch from sync_node instead of configured branch
        branch_to_analyze = state.get("actual_branch", state["branch"])
        
        # Collect merge commits
        merges_response = git_tool.log_merges(branch_to_analyze, period_days)
        if not merges_response.success:
            state["errors"].append(f"Failed to collect merge commits: {merges_response.error}")
            return {"collect_completed": False, "errors": state["errors"]}
        
        merge_commits = merges_response.data or []
        
        # Also collect ALL commits (not just merges) to check for direct pushes
        all_commits_response = git_tool.log_all_commits(branch_to_analyze, period_days)
        if not all_commits_response.success:
            state["errors"].append(f"Failed to collect all commits: {all_commits_response.error}")
            return {"collect_completed": False, "errors": state["errors"]}
        
        all_commits = all_commits_response.data or []
        
        # Collect diff statistics for each merge commit
        diff_stats = []
        for commit in merge_commits:
            diff_response = git_tool.diff_stats(commit["hash"])
            if diff_response.success:
                diff_stats.append(diff_response.data)
            else:
                # Log error but continue processing other commits
                state["errors"].append(f"Failed to get diff stats for {commit['hash']}: {diff_response.error}")
        
        # Collect branch information
        branches_response = git_tool.remote_branches()
        if not branches_response.success:
            state["errors"].append(f"Failed to collect branch info: {branches_response.error}")
            return {"collect_completed": False, "errors": state["errors"]}
        
        branches = branches_response.data or []
        
        return {
            "merge_commits": merge_commits,
            "all_commits": all_commits,
            "diff_stats": diff_stats,
            "branches": branches,
            "collect_completed": True
        }
        
    except Exception as e:
        state["errors"].append(f"Collect node error: {str(e)}")
        return {"collect_completed": False, "errors": state["errors"]}


def metrics_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for calculating PR metrics and aggregations.
    
    This node handles:
    - Calculating lead time percentiles (50th and 75th)
    - Calculating change size percentiles (50th and 75th)
    - Grouping commits by ISO week for trend analysis
    - Identifying top-k file churn hotspots
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with calculated PR metrics
    """
    try:
        if not state["collect_completed"]:
            state["errors"].append("Cannot calculate metrics: data collection not completed")
            return {"metrics_completed": False, "errors": state["errors"]}
        
        calc_tool = CalcTool()
        config = state["config"]
        merge_commits = state["merge_commits"]
        diff_stats = state["diff_stats"]
        
        # Calculate lead time statistics
        lead_time_response = calc_tool.lead_time(merge_commits)
        if not lead_time_response.success:
            state["errors"].append(f"Failed to calculate lead time: {lead_time_response.error}")
            return {"metrics_completed": False, "errors": state["errors"]}
        
        lead_time_stats = lead_time_response.data
        
        # Calculate change size percentiles
        change_sizes = [stats["total_changes"] for stats in diff_stats]
        
        p50_response = calc_tool.percentile(change_sizes, 50)
        p75_response = calc_tool.percentile(change_sizes, 75)
        
        if not p50_response.success or not p75_response.success:
            state["errors"].append("Failed to calculate change size percentiles")
            return {"metrics_completed": False, "errors": state["errors"]}
        
        # Group commits by ISO week
        weekly_response = calc_tool.group_by_iso_week(merge_commits)
        if not weekly_response.success:
            state["errors"].append(f"Failed to group by week: {weekly_response.error}")
            return {"metrics_completed": False, "errors": state["errors"]}
        
        weekly_groups = weekly_response.data
        weekly_pr_counts = {week: len(commits) for week, commits in weekly_groups.items()}
        
        # Calculate top-k files (placeholder - would need file-level diff data)
        # For now, create empty list as we don't have file-level data in current implementation
        top_k = config.get("top_k_files", 10)
        top_files = []  # Would be populated with actual file churn data
        
        # Create PR metrics object (user stats will be added later by user_analysis_node)
        pr_metrics = PRMetrics(
            total_prs=len(merge_commits),
            lead_time_p50=lead_time_stats["p50"],
            lead_time_p75=lead_time_stats["p75"],
            change_size_p50=int(p50_response.data),
            change_size_p75=int(p75_response.data),
            weekly_pr_counts=weekly_pr_counts,
            top_files=top_files,
            user_stats=None  # Will be populated by user_analysis_node
        )
        
        return {
            "pr_metrics": pr_metrics.to_dict(),
            "metrics_completed": True
        }
        
    except Exception as e:
        state["errors"].append(f"Metrics node error: {str(e)}")
        return {"metrics_completed": False, "errors": state["errors"]}


def stale_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for identifying stale branches.
    
    This node handles:
    - Filtering branches based on configurable stale_days threshold
    - Marking branches as stale if they haven't been updated recently
    - Creating a list of stale branches for reporting
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with stale branch information
    """
    try:
        if not state["collect_completed"]:
            state["errors"].append("Cannot identify stale branches: data collection not completed")
            return {"stale_completed": False, "errors": state["errors"]}
        
        config = state["config"]
        branches = state["branches"]
        stale_days = config.get("stale_days", config.get("period_days", 7))
        
        # Calculate cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=stale_days)
        
        stale_branches = []
        for branch_dict in branches:
            # Parse timestamp
            timestamp_str = branch_dict["last_commit_timestamp"]
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str.replace('Z', '+00:00')
            last_commit_time = datetime.fromisoformat(timestamp_str)
            
            # Check if branch is stale
            if last_commit_time < cutoff_date:
                # Create updated branch info with stale flag
                stale_branch = branch_dict.copy()
                stale_branch["is_stale"] = True
                stale_branches.append(stale_branch)
        
        return {
            "stale_branches": stale_branches,
            "stale_completed": True
        }
        
    except Exception as e:
        state["errors"].append(f"Stale node error: {str(e)}")
        return {"stale_completed": False, "errors": state["errors"]}


def tables_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for generating deterministic markdown tables.
    
    This node handles:
    - Creating metrics tables for PR analysis
    - Generating weekly PR counts tables
    - Creating top files tables
    - Rendering stale branches tables
    - Combining all tables into a single markdown section
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with tables_markdown content
    """
    try:
        if not (state["metrics_completed"] and state["stale_completed"] and state["user_analysis_completed"]):
            state["errors"].append("Cannot generate tables: metrics, stale analysis, or user analysis not completed")
            return {"tables_completed": False, "errors": state["errors"]}
        
        md_tool = MdTool()
        pr_metrics = state["pr_metrics"]
        stale_branches = state["stale_branches"]
        user_stats = state.get("user_stats", [])
        
        # Generate individual tables
        tables_sections = []
        
        # 1. PR Metrics table
        metrics_response = md_tool.render_metrics_table(pr_metrics)
        if not metrics_response.success:
            state["errors"].append(f"Failed to render metrics table: {metrics_response.error}")
            return {"tables_completed": False, "errors": state["errors"]}
        
        metrics_section_response = md_tool.render_section(
            f"{state['repository_name']} - PR Metrics", 
            metrics_response.data, 
            level=5
        )
        if metrics_section_response.success:
            tables_sections.append(metrics_section_response.data)
        
        # 2. Weekly PR counts table
        weekly_counts = pr_metrics.get("weekly_pr_counts", {})
        if weekly_counts:
            weekly_response = md_tool.render_weekly_counts_table(weekly_counts)
            if weekly_response.success:
                weekly_section_response = md_tool.render_section(
                    f"{state['repository_name']} - Weekly PR Counts", 
                    weekly_response.data, 
                    level=5
                )
                if weekly_section_response.success:
                    tables_sections.append(weekly_section_response.data)
        
        # 3. Top files table
        top_files = pr_metrics.get("top_files", [])
        if top_files:
            files_response = md_tool.render_top_files_table(top_files)
            if files_response.success:
                files_section_response = md_tool.render_section(
                    f"{state['repository_name']} - Top Changed Files", 
                    files_response.data, 
                    level=5
                )
                if files_section_response.success:
                    tables_sections.append(files_section_response.data)
        
        # 4. Stale branches table
        if stale_branches:
            stale_response = md_tool.render_stale_branches_table(stale_branches)
            if stale_response.success:
                stale_section_response = md_tool.render_section(
                    f"{state['repository_name']} - Stale Branches", 
                    stale_response.data, 
                    level=5
                )
                if stale_section_response.success:
                    tables_sections.append(stale_section_response.data)
        
        # 5. User statistics tables
        if user_stats:
            # Overview table
            user_overview_response = md_tool.render_user_stats_table(user_stats)
            if user_overview_response.success:
                user_overview_section_response = md_tool.render_section(
                    f"{state['repository_name']} - Developer Statistics", 
                    user_overview_response.data, 
                    level=5
                )
                if user_overview_section_response.success:
                    tables_sections.append(user_overview_section_response.data)
            
            # Individual user detail sections (limit to top 5 most active users)
            sorted_users = sorted(user_stats, key=lambda u: u.get('total_commits', 0), reverse=True)
            for user_stat in sorted_users[:5]:  # Top 5 most active users
                username = user_stat.get('username', 'Unknown')
                user_detail_response = md_tool.render_user_detail_section(user_stat)
                if user_detail_response.success:
                    user_detail_section_response = md_tool.render_section(
                        f"Developer Profile: {username}", 
                        user_detail_response.data, 
                        level=6
                    )
                    if user_detail_section_response.success:
                        tables_sections.append(user_detail_section_response.data)
        
        # Combine all table sections
        combined_response = md_tool.combine_sections(tables_sections)
        if not combined_response.success:
            state["errors"].append(f"Failed to combine table sections: {combined_response.error}")
            return {"tables_completed": False, "errors": state["errors"]}
        
        return {
            "tables_markdown": combined_response.data,
            "tables_completed": True
        }
        
    except Exception as e:
        state["errors"].append(f"Tables node error: {str(e)}")
        return {"tables_completed": False, "errors": state["errors"]}


def exec_summary_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for LLM-generated executive summaries.
    
    This node handles:
    - Generating executive summaries using LLM
    - Ensuring summaries are 120 words or less
    - Using only aggregated metrics (no source code)
    - Handling LLM configuration from state config
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with executive_summary content
    """
    try:
        if not state["metrics_completed"]:
            state["errors"].append("Cannot generate executive summary: metrics not completed")
            return {"exec_summary_completed": False, "errors": state["errors"]}
        
        config = state["config"]
        pr_metrics = state["pr_metrics"]
        
        # Check if LLM is enabled in config
        llm_config = config.get("llm")
        if not llm_config or not llm_config.get("enabled", True):
            # Skip LLM generation if disabled
            return {
                "executive_summary": None,
                "exec_summary_completed": True
            }
        
        # Initialize LLM tool with config
        try:
            llm_tool = LLMTool(
                provider=llm_config.get("provider", "openai"),
                model=llm_config.get("model", "gpt-3.5-turbo"),
                temperature=llm_config.get("temperature", 0.7),
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                max_tokens=llm_config.get("max_tokens")
            )
        except Exception as e:
            state["errors"].append(f"Failed to initialize LLM tool: {str(e)}")
            return {"exec_summary_completed": False, "errors": state["errors"]}
        
        # Generate executive summary
        weekly_data = pr_metrics.get("weekly_pr_counts", {})
        summary_response = llm_tool.generate_executive_summary(pr_metrics, weekly_data)
        
        if not summary_response.success:
            state["errors"].append(f"Failed to generate executive summary: {summary_response.error}")
            return {"exec_summary_completed": False, "errors": state["errors"]}
        
        return {
            "executive_summary": summary_response.data,
            "exec_summary_completed": True
        }
        
    except Exception as e:
        state["errors"].append(f"Executive summary node error: {str(e)}")
        return {"exec_summary_completed": False, "errors": state["errors"]}


def org_trend_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for LLM-generated organizational insights.
    
    This node handles:
    - Generating organizational trend analysis using LLM
    - Using weekly aggregated data across repositories
    - Providing org-level insights and recommendations
    - Handling LLM configuration from state config
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with org_trends content
    """
    try:
        if not state["metrics_completed"]:
            state["errors"].append("Cannot generate organizational trends: metrics not completed")
            return {"org_trend_completed": False, "errors": state["errors"]}
        
        config = state["config"]
        pr_metrics = state["pr_metrics"]
        
        # Check if LLM is enabled in config
        llm_config = config.get("llm")
        if not llm_config or not llm_config.get("enabled", True):
            # Skip LLM generation if disabled
            return {
                "org_trends": None,
                "org_trend_completed": True
            }
        
        # Initialize LLM tool with config
        try:
            llm_tool = LLMTool(
                provider=llm_config.get("provider", "openai"),
                model=llm_config.get("model", "gpt-3.5-turbo"),
                temperature=llm_config.get("temperature", 0.7),
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                max_tokens=llm_config.get("max_tokens")
            )
        except Exception as e:
            state["errors"].append(f"Failed to initialize LLM tool: {str(e)}")
            return {"org_trend_completed": False, "errors": state["errors"]}
        
        # Prepare weekly aggregated data for organizational analysis
        weekly_data = pr_metrics.get("weekly_pr_counts", {})
        total_prs = pr_metrics.get("total_prs", 0)
        
        # Skip organizational trends if no data available
        if total_prs == 0 or not weekly_data:
            return {
                "org_trends": None,  # No trends section
                "org_trend_completed": True
            }
        
        # Create aggregated data structure for org-level analysis
        weekly_aggregated_data = []
        for week, pr_count in weekly_data.items():
            weekly_aggregated_data.append({
                "week": week,
                "repository": state["repository_name"],
                "pr_count": pr_count,
                "lead_time_p50": pr_metrics.get("lead_time_p50", 0),
                "lead_time_p75": pr_metrics.get("lead_time_p75", 0),
                "change_size_p50": pr_metrics.get("change_size_p50", 0),
                "change_size_p75": pr_metrics.get("change_size_p75", 0)
            })
        
        # Generate organizational trends analysis
        trends_response = llm_tool.generate_organizational_trends(weekly_aggregated_data)
        
        if not trends_response.success:
            state["errors"].append(f"Failed to generate organizational trends: {trends_response.error}")
            return {"org_trend_completed": False, "errors": state["errors"]}
        
        return {
            "org_trends": trends_response.data,
            "org_trend_completed": True
        }
        
    except Exception as e:
        state["errors"].append(f"Organizational trends node error: {str(e)}")
        return {"org_trend_completed": False, "errors": state["errors"]}


def assembler_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for combining all sections into final report.
    
    This node handles:
    - Combining executive summary, tables, and org trends
    - Ensuring fixed section ordering for deterministic output
    - Creating the final markdown report
    - Writing the report to the configured output file
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with final report assembled
    """
    try:
        if not (state["tables_completed"] and 
                state["exec_summary_completed"] and 
                state["org_trend_completed"] and
                state["user_analysis_completed"] and
                state["commit_quality_completed"]):
            state["errors"].append("Cannot assemble report: not all sections completed")
            return {"assembler_completed": False, "errors": state["errors"]}
        
        md_tool = MdTool()
        sections = []
        
        # 1. Executive Summary (if available)
        if state["executive_summary"]:
            exec_section_response = md_tool.render_section(
                "Executive Summary", 
                state["executive_summary"], 
                level=4
            )
            if exec_section_response.success:
                sections.append(exec_section_response.data)
        
        # 2. Repository Tables
        if state["tables_markdown"]:
            tables_section_response = md_tool.render_section(
                "Repository Metrics", 
                state["tables_markdown"], 
                level=4
            )
            if tables_section_response.success:
                sections.append(tables_section_response.data)
        
        # 3. Organizational Trends (if available)
        if state["org_trends"]:
            trends_section_response = md_tool.render_section(
                "Organizational Trends", 
                state["org_trends"], 
                level=4
            )
            if trends_section_response.success:
                sections.append(trends_section_response.data)
        
        # 4. Commit Message Quality Analysis (if available)
        if state["commit_quality_analysis"]:
            quality_section_response = md_tool.render_section(
                "Commit Message Quality Analysis", 
                state["commit_quality_analysis"], 
                level=4
            )
            if quality_section_response.success:
                sections.append(quality_section_response.data)
        
        # 4. Add report header
        report_title = f"### Git Analysis Report - {state['repository_name']}"
        from datetime import datetime, timedelta
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        actual_branch = state.get("actual_branch", state["branch"])
        
        # Add analyzed period information
        config = state["config"]
        period_days = config.get("period_days", 7)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)
        period_text = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({period_days} days)"
        
        report_header = f"{report_title}\n\n**Generated on:** {timestamp}  \n**Analyzed Branch:** {actual_branch}  \n**Analyzed Period:** {period_text}"
        
        # Combine all sections with header
        all_sections = [report_header] + sections
        final_report_response = md_tool.combine_sections(all_sections)
        
        if not final_report_response.success:
            state["errors"].append(f"Failed to assemble final report: {final_report_response.error}")
            return {"assembler_completed": False, "errors": state["errors"]}
        
        # Check if there are any PRs/changes in the analysis period
        pr_metrics = state.get("pr_metrics", {})
        total_prs = pr_metrics.get("total_prs", 0)
        
        # Also check for any commits (not just PRs)
        all_commits = state.get("all_commits", [])
        total_commits = len(all_commits)
        
        # Skip file generation if no changes during the period (no PRs AND no commits)
        if total_prs == 0 and total_commits == 0:
            return {
                "final_report": final_report_response.data,
                "report_filename": None,  # No file created
                "assembler_completed": True,
                "skipped_no_changes": True
            }
        
        # Generate individual report file for this repository
        config = state["config"]
        period_days = config.get("period_days", 7)
        
        # Create reports directory if it doesn't exist
        import os
        from pathlib import Path
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        # Generate filename using the new pattern
        repo_name = state["repository_name"]
        filename = md_tool.generate_report_filename(repo_name, period_days)
        output_file = reports_dir / filename
        
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(final_report_response.data)
        except Exception as e:
            state["errors"].append(f"Failed to write report to {output_file}: {str(e)}")
            return {"assembler_completed": False, "errors": state["errors"]}
        
        return {
            "final_report": final_report_response.data,
            "report_filename": str(output_file),
            "assembler_completed": True
        }
        
    except Exception as e:
        state["errors"].append(f"Assembler node error: {str(e)}")
        return {"assembler_completed": False, "errors": state["errors"]}


def user_analysis_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for analyzing individual user commit patterns and generating recommendations.
    
    This node handles:
    - Analyzing all users who have committed to the repository
    - Generating file hotspots per user
    - Classifying work types for each user's commits
    - Creating personalized recommendations using LLM (if enabled)
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with user analysis results
    """
    try:
        if not state["collect_completed"]:
            state["errors"].append("Cannot analyze users: data collection not completed")
            return {"user_analysis_completed": False, "errors": state["errors"]}
        
        user_analysis_tool = UserAnalysisTool(state["cache_path"])
        config = state["config"]
        period_days = config.get("period_days", 7)
        
        # Use actual_branch from sync_node instead of configured branch
        branch_to_analyze = state.get("actual_branch", state["branch"])
        
        # Analyze all users
        user_analysis_response = user_analysis_tool.analyze_all_users(branch_to_analyze, period_days)
        if not user_analysis_response.success:
            state["errors"].append(f"Failed to analyze users: {user_analysis_response.error}")
            return {"user_analysis_completed": False, "errors": state["errors"]}
        
        user_stats_list = user_analysis_response.data or []
        
        # Generate LLM recommendations if LLM is enabled
        llm_config = config.get("llm")
        if llm_config and llm_config.get("enabled", True):
            try:
                llm_tool = LLMTool(
                    provider=llm_config.get("provider", "openai"),
                    model=llm_config.get("model", "gpt-3.5-turbo"),
                    temperature=llm_config.get("temperature", 0.7),
                    api_key=llm_config.get("api_key"),
                    base_url=llm_config.get("base_url"),
                    max_tokens=llm_config.get("max_tokens")
                )
                
                # Generate recommendations and code review insights for each user
                for user_stats in user_stats_list:
                    # Generate personalized recommendations
                    recommendations_response = llm_tool.generate_user_recommendations(user_stats)
                    if recommendations_response.success:
                        user_stats['recommendations'] = recommendations_response.data
                    else:
                        # Fall back to rule-based recommendations
                        user_stats['recommendations'] = [
                            "Consider reviewing commit patterns for potential improvements",
                            "Focus on maintaining consistent development practices"
                        ]
                    
                    # Generate code review insights for top files
                    try:
                        # Read file contents for top modified files
                        file_contents = {}
                        repo_path = state["cache_path"] # This is the path to the cloned repository
                        for file_info in user_stats.get('top_files', [])[:3]:
                            filename = file_info.get('filename')
                            if filename:
                                full_file_path = repo_path / filename
                                if full_file_path.exists() and full_file_path.is_file():
                                    try:
                                        with open(full_file_path, 'r', encoding='utf-8') as f:
                                            file_contents[filename] = f.read()
                                    except Exception as file_read_e:
                                        print(f"Error reading file {full_file_path}: {file_read_e}")
                                        file_contents[filename] = "" # Add empty content if read fails
                                else:
                                    print(f"File not found or not a file: {full_file_path}")
                                    file_contents[filename] = "" # Add empty content if file not found

                        code_review_response = llm_tool.generate_code_review_insights(user_stats, file_contents)
                        if code_review_response.success:
                            user_stats['code_review_insights'] = code_review_response.data
                        else:
                            print(f"Code review insights failed for {user_stats.get('username', 'unknown')}: {code_review_response.error}")
                            user_stats['code_review_insights'] = ""
                    except Exception as e:
                        print(f"Code review insights exception for {user_stats.get('username', 'unknown')}: {str(e)}")
                        user_stats['code_review_insights'] = ""
                            
            except Exception as e:
                # If LLM fails, fall back to rule-based recommendations for all users
                for user_stats in user_stats_list:
                    user_stats['recommendations'] = [
                        "Consider reviewing commit patterns for potential improvements",
                        "Focus on maintaining consistent development practices"
                    ]
                    user_stats['code_review_insights'] = ""
        else:
            # Generate rule-based recommendations if LLM is disabled
            for user_stats in user_stats_list:
                user_stats['recommendations'] = [
                    "Consider reviewing commit patterns for potential improvements",
                    "Focus on maintaining consistent development practices"
                ]
                user_stats['code_review_insights'] = ""
        
        return {
            "user_stats": user_stats_list,
            "user_analysis_completed": True
        }
        
    except Exception as e:
        state["errors"].append(f"User analysis node error: {str(e)}")
        return {"user_analysis_completed": False, "errors": state["errors"]}


def commit_quality_node(state: AnalysisState) -> Dict[str, Any]:
    """Node for analyzing commit message quality using LLM.
    
    This node handles:
    - Gathering commit data with diff information
    - Analyzing how well commit messages describe actual changes
    - Generating recommendations for better commit practices
    
    Args:
        state: Current analysis state
        
    Returns:
        Updated state with commit message quality analysis
    """
    try:
        if not state["collect_completed"]:
            state["errors"].append("Cannot analyze commit quality: data collection not completed")
            return {"commit_quality_completed": False, "errors": state["errors"]}
        
        config = state["config"]
        llm_config = config.get("llm")
        
        # Skip commit quality analysis if LLM is disabled
        if not llm_config or not llm_config.get("enabled", True):
            return {
                "commit_quality_analysis": None,
                "commit_quality_completed": True
            }
        
        git_tool = GitTool(state["cache_path"])
        all_commits = state.get("all_commits", [])
        
        # Skip if no commits to analyze
        if not all_commits:
            return {
                "commit_quality_analysis": "No commits available for quality analysis.",
                "commit_quality_completed": True
            }
        
        # Gather detailed commit data with diff information
        commits_with_diffs = []
        max_commits_to_analyze = 15  # Limit to avoid overwhelming LLM
        
        for i, commit in enumerate(all_commits[:max_commits_to_analyze]):
            commit_hash = commit.get('hash')
            if not commit_hash:
                continue
                
            # Get diff stats for this commit
            diff_response = git_tool.diff_stats(commit_hash)
            diff_stats = diff_response.data if diff_response.success else {}
            
            # Get files changed in this commit
            files_response = git_tool.get_commit_files(commit_hash)
            files_changed = files_response.data if files_response.success else []
            
            commit_data = {
                'hash': commit_hash,
                'message': commit.get('message', ''),
                'author_name': commit.get('author_name', ''),
                'diff_stats': diff_stats,
                'files_changed': files_changed
            }
            commits_with_diffs.append(commit_data)
        
        # Initialize LLM tool
        try:
            llm_tool = LLMTool(
                provider=llm_config.get("provider", "openai"),
                model=llm_config.get("model", "gpt-3.5-turbo"),
                temperature=llm_config.get("temperature", 0.7),
                api_key=llm_config.get("api_key"),
                base_url=llm_config.get("base_url"),
                max_tokens=llm_config.get("max_tokens")
            )
        except Exception as e:
            state["errors"].append(f"Failed to initialize LLM tool: {str(e)}")
            return {"commit_quality_completed": False, "errors": state["errors"]}
        
        # Analyze commit message quality
        quality_response = llm_tool.analyze_commit_message_quality(commits_with_diffs)
        
        if not quality_response.success:
            state["errors"].append(f"Failed to analyze commit quality: {quality_response.error}")
            return {"commit_quality_completed": False, "errors": state["errors"]}
        
        return {
            "commit_quality_analysis": quality_response.data,
            "commit_quality_completed": True
        }
        
    except Exception as e:
        state["errors"].append(f"Commit quality node error: {str(e)}")
        return {"commit_quality_completed": False, "errors": state["errors"]}