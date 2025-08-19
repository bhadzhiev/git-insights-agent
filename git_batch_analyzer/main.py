"""Main CLI interface for Git Batch Analyzer."""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta

import click

from .config.loader import load_config_from_yaml, ConfigurationError
from .config.models import AnalysisConfig, EmailConfig
from .workflow.graph import process_repositories
from .tools.email_tool import EmailTool
from .tools.git_tool import GitTool


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@click.command()
@click.argument('config_file', type=click.Path(exists=True, path_type=Path))
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    help='Override output file path from config'
)
@click.option(
    '--cache-dir',
    type=click.Path(path_type=Path),
    help='Override cache directory from config'
)
@click.option(
    '--period-days',
    type=int,
    help='Override analysis period in days from config'
)
@click.option(
    '--max-workers',
    type=int,
    help='Number of parallel workers for repository processing (default: 4)'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Validate configuration and show what would be processed without running analysis'
)
@click.option(
    '--send-email',
    is_flag=True,
    help='Send the report to committers via email.'
)
def cli(
    config_file: Path,
    verbose: bool,
    output: Path,
    cache_dir: Path,
    period_days: int,
    max_workers: int,
    dry_run: bool,
    send_email: bool
) -> None:
    """
    Git Batch Analyzer - Analyze multiple git repositories and generate development metrics reports.
    
    CONFIG_FILE: Path to YAML configuration file specifying repositories and analysis parameters.
    
    Example usage:
    
        git-batch-analyzer config.yaml
        
        git-batch-analyzer config.yaml --verbose --output custom-report.md
        
        git-batch-analyzer config.yaml --max-workers 8  # Use 8 parallel workers
        
        git-batch-analyzer config.yaml --dry-run
    """
    # Configure logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        click.echo("Verbose logging enabled")
        logger.debug("Verbose logging enabled")
    
    try:
      
        # Load and validate configuration
        logger.info(f"Loading configuration from {config_file}")
        config = load_config_from_yaml(config_file)
        
        # Apply CLI overrides
        config = _apply_cli_overrides(config, output, cache_dir, period_days, max_workers)
        
        # Log configuration summary
        _log_config_summary(config)
        
        if dry_run:
            logger.info("Dry run mode - configuration validation complete")
            _show_dry_run_summary(config)
            return
        
        # Process repositories
        logger.info(f"Starting analysis of {len(config.repositories)} repositories")
        results = _process_all_repositories(config)
        
        # Generate summary report
        _generate_summary_report(config, results)
        
        # Log summary
        _log_final_summary(results, config.output_file)

        if send_email:
            if not config.email:
                click.echo("Email configuration is missing in the config file.", err=True)
                logger.error("Email configuration is missing.")
                sys.exit(1)

            if not config.output_file.exists():
                click.echo(f"Report file not found: {config.output_file}", err=True)
                logger.error(f"Report file not found: {config.output_file}")
                sys.exit(1)

            # Send individual reports to each repository's committers
            _send_individual_repo_emails(config, results)
        
    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("Analysis interrupted by user", err=True)
        logger.info("Analysis interrupted by user")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        logger.error(f"Unexpected error: {e}")
        if verbose:
            click.echo("Full traceback:", err=True)
            logger.exception("Full traceback:")
        sys.exit(1)


def _apply_cli_overrides(
    config: AnalysisConfig,
    output: Path,
    cache_dir: Path,
    period_days: int,
    max_workers: int
) -> AnalysisConfig:
    """Apply CLI option overrides to configuration."""
    if output:
        config.output_file = output.expanduser()
        logger.debug(f"Output file overridden to: {config.output_file}")
    
    if cache_dir:
        config.cache_dir = cache_dir.expanduser()
        config.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Cache directory overridden to: {config.cache_dir}")
    
    if period_days:
        config.period_days = period_days
        # Update stale_days if it was using the default
        if config.stale_days == config.period_days:
            config.stale_days = period_days
        logger.debug(f"Analysis period overridden to: {config.period_days} days")
    
    if max_workers:
        config.max_workers = max_workers
        logger.debug(f"Max workers overridden to: {config.max_workers}")
    
    return config


def _log_config_summary(config: AnalysisConfig) -> None:
    """Log a summary of the loaded configuration."""
    logger.info(f"Configuration loaded successfully:")
    logger.info(f"  - Repositories: {len(config.repositories)}")
    logger.info(f"  - Analysis period: {config.period_days} days")
    logger.info(f"  - Stale branch threshold: {config.stale_days} days")
    logger.info(f"  - Max parallel workers: {config.max_workers}")
    logger.info(f"  - Cache directory: {config.cache_dir}")
    logger.info(f"  - Output file: {config.output_file}")
    logger.info(f"  - LLM enabled: {'Yes' if config.llm else 'No'}")
    
    if config.llm:
        logger.info(f"  - LLM provider: {config.llm.provider}")
        logger.info(f"  - LLM model: {config.llm.model}")


def _show_dry_run_summary(config: AnalysisConfig) -> None:
    """Show what would be processed in a dry run."""
    click.echo("\n" + "="*60)
    click.echo("DRY RUN SUMMARY")
    click.echo("="*60)
    
    click.echo(f"\nRepositories to analyze ({len(config.repositories)}):")
    for i, repo in enumerate(config.repositories, 1):
        branch_info = f" (branch: {repo.branch})" if repo.branch else " (default branch)"
        click.echo(f"  {i}. {repo.url}{branch_info}")
    
    click.echo(f"\nAnalysis configuration:")
    click.echo(f"  - Period: {config.period_days} days")
    click.echo(f"  - Stale threshold: {config.stale_days} days")
    click.echo(f"  - Fetch depth: {config.fetch_depth} commits")
    click.echo(f"  - Top files to show: {config.top_k_files}")
    click.echo(f"  - Parallel workers: {config.max_workers}")
    
    click.echo(f"\nOutput configuration:")
    click.echo(f"  - Cache directory: {config.cache_dir}")
    click.echo(f"  - Output file: {config.output_file}")
    
    if config.llm:
        click.echo(f"\nLLM configuration:")
        click.echo(f"  - Provider: {config.llm.provider}")
        click.echo(f"  - Model: {config.llm.model}")
        click.echo(f"  - Temperature: {config.llm.temperature}")
    else:
        click.echo(f"\nLLM: Disabled (tables and stale branches only)")
    
    click.echo("\n" + "="*60)


def _process_all_repositories(config: AnalysisConfig) -> Dict[str, Any]:
    """Process all repositories using the workflow."""
    # Convert config to dictionary format expected by workflow
    config_dict = {
        "period_days": config.period_days,
        "stale_days": config.stale_days,
        "fetch_depth": config.fetch_depth,
        "top_k_files": config.top_k_files,
        "cache_dir": str(config.cache_dir),
        "output_file": str(config.output_file),
        "max_workers": config.max_workers,
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
            "temperature": config.llm.temperature,
            "api_key": config.llm.api_key
        } if config.llm else None
    }
    
    # Convert repositories to list of dictionaries
    repositories = []
    for repo in config.repositories:
        repo_dict = {"url": repo.url}
        if repo.branch:
            repo_dict["branch"] = repo.branch
        repositories.append(repo_dict)
    
    # Process repositories with progress tracking
    results = process_repositories(repositories, config_dict)
    
    # Initialize inactive_repositories list if not present
    if "inactive_repositories" not in results:
        results["inactive_repositories"] = []
    
    # Log progress for each repository-branch combination
    for repo_result in results["successful_repositories"]:
        branch_info = f" ({repo_result.get('branch', 'unknown')})" if repo_result.get('branch') else ""
        click.echo(f"✓ Successfully processed: {repo_result['name']}{branch_info}")
        logger.info(f"✓ Successfully processed: {repo_result['name']}{branch_info}")
    
    for repo_result in results["failed_repositories"]:
        branch_info = f" ({repo_result.get('branch', 'unknown')})" if repo_result.get('branch') else ""
        click.echo(f"✗ Failed to process: {repo_result['name']}{branch_info}", err=True)
        logger.warning(f"✗ Failed to process: {repo_result['name']}{branch_info}")
        for error in repo_result["errors"]:
            click.echo(f"  - {error}", err=True)
            logger.warning(f"  - {error}")
    
    return results


def _generate_summary_report(config: AnalysisConfig, results: Dict[str, Any]) -> None:
    """Generate and write a summary report listing all individual repository reports."""
    if not results["successful_repositories"]:
        click.echo("No repositories were successfully processed - cannot generate report", err=True)
        logger.error("No repositories were successfully processed - cannot generate report")
        return
    
    logger.info("Generating summary report...")
    
    # Collect all repository information
    successful_repos = []
    inactive_repos = []
    
    for repo_result in results["successful_repositories"]:
        final_state = repo_result["final_state"]
        # Check if repository has actual PRs/changes in the period
        pr_metrics = final_state.get("pr_metrics", {})
        total_prs = pr_metrics.get("total_prs", 0)
        
        # Also check for any commits (not just PRs)
        all_commits = final_state.get("all_commits", [])
        total_commits = len(all_commits)

        repo_info = {
            "name": repo_result["name"],
            "url": repo_result["url"],
            "branch": final_state.get("actual_branch", "unknown"),
            "total_prs": total_prs,
            "total_commits": total_commits
        }

        # Repository is active if it has PRs OR commits
        if total_prs > 0 or total_commits > 0:
            successful_repos.append(repo_info)
        else:
            inactive_repos.append(repo_info)
    
    # Update results to track inactive repositories separately (for summary statistics)
    results["inactive_repositories"] = inactive_repos
    
    # Generate summary report content
    summary_report = _create_summary_report_content(successful_repos, inactive_repos, results["failed_repositories"], config)
    
    # Write the summary report
    try:
        config.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config.output_file, 'w', encoding='utf-8') as f:
            f.write(summary_report)
        logger.info(f"Summary report written to: {config.output_file}")
    except Exception as e:
        logger.error(f"Failed to write summary report: {e}")
        raise


def _create_summary_report_content(
    successful_repos: List[Dict[str, Any]], 
    inactive_repos: List[Dict[str, Any]],
    failed_repos: List[Dict[str, Any]],
    config: AnalysisConfig
) -> str:
    """Create summary report content listing all individual repository reports."""
    from datetime import datetime, timedelta
    from git_batch_analyzer.tools.md_tool import MdTool
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=config.period_days)
    from_date = start_date.strftime("%Y-%m-%d")
    to_date = end_date.strftime("%Y-%m-%d")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_repos = len(successful_repos) + len(inactive_repos) + len(failed_repos)
    
    header = f"""# Git Batch Analysis Summary Report

**Generated:** {timestamp}  
**Analysis Period:** {config.period_days} days ({from_date} to {to_date})  
**Total Repositories:** {total_repos}  
**Successful:** {len(successful_repos) + len(inactive_repos)}  
**Failed:** {len(failed_repos)}

## Individual Repository Reports

All individual repository reports have been generated in the `reports/` folder with the naming pattern: `[repoName]report[fromDate]-[toDate].md`

"""
    
    sections = [header]
    
    # Active repositories section
    if successful_repos:
        md_tool = MdTool()
        active_section = "### Active Repositories (with PRs/commits)\n\n"
        
        headers = ["Repository", "Report File", "PRs", "Commits", "Branch"]
        rows = []
        for repo in successful_repos:
            filename = md_tool.generate_report_filename(repo["name"], config.period_days)
            rows.append([
                repo["name"],
                f"`reports/{filename}`",
                str(repo["total_prs"]),
                str(repo["total_commits"]),
                repo["branch"]
            ])
        
        table_response = md_tool.render_table(headers, rows, alignment=["left", "left", "right", "right", "left"])
        if table_response.success:
            active_section += table_response.data
        
        sections.append(active_section)
    
    # Inactive repositories section - show summary only, no report files
    if inactive_repos:
        inactive_section = "### Inactive Repositories (no PRs/commits)\n\n"
        inactive_section += f"**{len(inactive_repos)} repositories** had no development activity during the analysis period:\n\n"
        
        for repo in inactive_repos:
            inactive_section += f"- **{repo['name']}** (branch: {repo['branch']})\n"
        
        sections.append(inactive_section)
    
    # Failed repositories section
    if failed_repos:
        failed_section = "### Failed Repositories\n\n"
        for repo in failed_repos:
            failed_section += f"- **{repo['name']}**: {repo['error']}\n"
        sections.append(failed_section)
    
    return "\n\n".join(sections)


def _log_final_summary(results: Dict[str, Any], output_file: Path) -> None:
    """Log a final summary of the analysis results."""
    successful_count = len(results["successful_repositories"])
    failed_count = len(results["failed_repositories"])
    inactive_count = len(results.get("inactive_repositories", []))
    total_count = successful_count + failed_count
    
    # Count branches with actual activity (for report generation)
    active_count = successful_count - inactive_count
    
    # Echo to user
    click.echo("\n" + "="*60)
    click.echo("ANALYSIS COMPLETE")
    click.echo("="*60)
    click.echo(f"Total branches analyzed: {total_count}")
    click.echo(f"Successfully processed: {successful_count}")
    click.echo(f"  - With activity (included in report): {active_count}")
    click.echo(f"  - Without activity (inactive): {inactive_count}")
    click.echo(f"Failed to process: {failed_count}")
    
    click.echo(f"Summary report generated: {output_file}")
    click.echo(f"Individual reports saved in: reports/ folder")
    
    if active_count > 0:
        click.echo(f"\nRepositories with activity:")
        for repo_result in results["successful_repositories"]:
            final_state = repo_result["final_state"]
            pr_metrics = final_state.get("pr_metrics", {})
            total_prs = pr_metrics.get("total_prs", 0)
            if total_prs > 0:
                report_filename = final_state.get("report_filename", "unknown")
                click.echo(f"  - {repo_result['name']}: {total_prs} PRs -> {report_filename}")
    
    if inactive_count > 0:
        click.echo(f"\nInactive repositories (no PRs in analysis period):")
        for repo_result in results.get("inactive_repositories", []):
            click.echo(f"  - {repo_result['name']}")
    
    if failed_count > 0:
        click.echo(f"\nFailed repositories:")
        for repo_result in results["failed_repositories"]:
            click.echo(f"  - {repo_result['name']}: {repo_result['url']}")
    
    click.echo("="*60)
    
    # Also log for debugging
    logger.info("\n" + "="*60)
    logger.info("ANALYSIS COMPLETE")
    logger.info("="*60)
    logger.info(f"Total branches analyzed: {total_count}")
    logger.info(f"Successfully processed: {successful_count}")
    logger.info(f"  - With activity (included in report): {active_count}")
    logger.info(f"  - Without activity (inactive): {inactive_count}")
    logger.info(f"Failed to process: {failed_count}")
    
    if active_count > 0:
        logger.info(f"Report generated: {output_file}")
    
    if inactive_count > 0:
        logger.info(f"\nInactive repositories (no PRs in analysis period):")
        for repo_result in results.get("inactive_repositories", []):
            logger.info(f"  - {repo_result['name']}")
    
    if failed_count > 0:
        logger.warning(f"\nFailed repositories:")
        for repo_result in results["failed_repositories"]:
            logger.warning(f"  - {repo_result['name']}: {repo_result['url']}")
    
    logger.info("="*60)


def _prepare_email_content(config: AnalysisConfig, results: Dict[str, Any]) -> str:
    """Prepare HTML email content by combining all individual reports."""
    import markdown
    from git_batch_analyzer.tools.md_tool import MdTool
    
    # Start with email header
    from_date = (datetime.now() - timedelta(days=config.period_days)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")
    
    email_content = f"""# Git Development Activity Report

**Period:** {config.period_days} days ({from_date} to {to_date})  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

"""
    
    # Add individual repository reports
    md_tool = MdTool()
    active_repos = 0
    
    for repo_result in results["successful_repositories"]:
        final_state = repo_result["final_state"]
        
        # Check if repository has activity
        pr_metrics = final_state.get("pr_metrics", {})
        total_prs = pr_metrics.get("total_prs", 0)
        all_commits = final_state.get("all_commits", [])
        total_commits = len(all_commits)
        
        if total_prs > 0 or total_commits > 0:
            active_repos += 1
            # Generate the report filename
            repo_filename = md_tool.generate_report_filename(repo_result["name"], config.period_days)
            report_path = Path("reports") / repo_filename
            
            # Try to read the individual report
            try:
                if report_path.exists():
                    with open(report_path, 'r', encoding='utf-8') as f:
                        report_markdown = f.read()
                    email_content += f"\n\n{report_markdown}\n\n---\n"
                else:
                    # If report file doesn't exist, create a minimal section
                    branch = final_state.get("actual_branch", "unknown")
                    email_content += f"""
## {repo_result['name']} ({branch})

**Activity Summary:**
- PRs: {total_prs}
- Commits: {total_commits}
- Branch: {branch}

*Detailed report not available*

---
"""
            except Exception as e:
                logger.warning(f"Failed to read report for {repo_result['name']}: {e}")
                continue
    
    # Add summary at the end
    inactive_count = len([r for r in results["successful_repositories"] 
                         if not (r["final_state"].get("pr_metrics", {}).get("total_prs", 0) > 0 
                                or len(r["final_state"].get("all_commits", [])) > 0)])
    
    email_content += f"""

## Summary

- **Active repositories:** {active_repos} (with development activity)
- **Inactive repositories:** {inactive_count} (no activity in analysis period)
- **Failed repositories:** {len(results["failed_repositories"])}

This report was automatically generated by Git Batch Analyzer.
"""
    
    # Convert markdown to HTML
    try:
        html_content = markdown.markdown(
            email_content,
            extensions=['tables', 'codehilite', 'toc'],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight'
                }
            }
        )
        
        # Add basic CSS styling
        styled_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        code {{ background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
        pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }}
        .highlight {{ background-color: #f8f8f8; }}
        hr {{ border: none; height: 1px; background-color: #ddd; margin: 20px 0; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
"""
        return styled_html
        
    except Exception as e:
        logger.error(f"Failed to convert markdown to HTML: {e}")
        # Fallback to plain text
        return f"<html><body><pre>{email_content}</pre></body></html>"


def _send_individual_repo_emails(config: AnalysisConfig, results: Dict[str, Any]) -> None:
    """Send individual repository reports to each repository's committers."""
    import markdown
    from git_batch_analyzer.tools.md_tool import MdTool
    
    email_tool = EmailTool(
        sender_email=config.email.sender_email,
        sender_name=config.email.sender_name,
        provider=config.email.provider,
        api_key=config.email.api_key,
        api_secret=config.email.api_secret,
        smtp_server=config.email.smtp_server,
        smtp_port=config.email.smtp_port,
        smtp_password=config.email.smtp_password
    )
    
    md_tool = MdTool()
    emails_sent = 0
    total_recipients = 0
    
    for repo_result in results["successful_repositories"]:
        final_state = repo_result["final_state"]
        
        # Check if repository has activity
        pr_metrics = final_state.get("pr_metrics", {})
        total_prs = pr_metrics.get("total_prs", 0)
        all_commits = final_state.get("all_commits", [])
        total_commits = len(all_commits)
        
        # Only send emails for repositories with activity
        if total_prs == 0 and total_commits == 0:
            continue
            
        # Get committers for this specific repository and branch
        repo_path = config.get_repo_cache_dir(repo_result["url"])
        git_tool = GitTool(repo_path)
        actual_branch = final_state.get("actual_branch", "unknown")
        committers_response = git_tool.get_committers(config.period_days, branch=actual_branch)
        
        if not committers_response.success or not committers_response.data:
            logger.warning(f"No committers found for {repo_result['name']}")
            continue
            
        repo_committers = list(committers_response.data)
        logger.info(f"Found {len(repo_committers)} committers for {repo_result['name']}")
        
        # Prepare individual report content for this repository
        report_content = _prepare_individual_repo_email_content(config, repo_result, final_state, md_tool)
        
        # Send email to this repository's committers
        repo_name = repo_result["name"]
        branch = final_state.get("actual_branch", "unknown")
        subject = f"Git Analysis Report: {repo_name} ({branch}) - {datetime.now().strftime('%Y-%m-%d')}"
        
        email_response = email_tool.send_email(
            recipients=repo_committers,
            subject=subject,
            body=report_content
        )
        
        if email_response.success:
            emails_sent += 1
            total_recipients += len(repo_committers)
            click.echo(f"✓ Sent report for {repo_name} to {len(repo_committers)} committers")
            logger.info(f"Successfully sent email report for {repo_name} to {repo_committers}")
        else:
            click.echo(f"✗ Failed to send report for {repo_name}: {email_response.error}", err=True)
            logger.error(f"Failed to send email report for {repo_name}: {email_response.error}")
    
    # Final summary
    if emails_sent > 0:
        click.echo(f"\n✓ Successfully sent {emails_sent} individual reports to {total_recipients} total recipients")
        logger.info(f"Successfully sent {emails_sent} individual reports to {total_recipients} total recipients")
    else:
        click.echo("No email reports were sent (no repositories with committers found)", err=True)
        logger.warning("No email reports were sent")


def _prepare_individual_repo_email_content(config: AnalysisConfig, repo_result: Dict[str, Any], final_state: Dict[str, Any], md_tool) -> str:
    """Prepare HTML email content for a single repository."""
    import markdown
    
    # Get repository info
    repo_name = repo_result["name"]
    branch = final_state.get("actual_branch", "unknown")
    
    # Start with email header for individual repo
    from_date = (datetime.now() - timedelta(days=config.period_days)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")
    
    # Try to read the individual report file using stored filename
    stored_report_filename = final_state.get("report_filename")
    if stored_report_filename:
        report_path = Path(stored_report_filename)
        logger.debug(f"Using stored report path: {report_path}")
    else:
        # Fallback to generating filename if not stored
        logger.debug("No stored report filename, generating new one")
        repo_filename = md_tool.generate_report_filename(repo_name, config.period_days)
        report_path = Path("reports") / repo_filename
        logger.debug(f"Generated report path: {report_path}")
    
    logger.debug(f"Looking for report file at: {report_path}, exists: {report_path.exists()}")
    
    if report_path.exists():
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report_markdown = f.read()
            
            # Add email header to the report
            email_content = f"""# Git Development Report: {repo_name}

**Repository:** {repo_name}  
**Branch:** {branch}  
**Period:** {config.period_days} days ({from_date} to {to_date})  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

{report_markdown}

---

*This personalized report was automatically generated by Git Batch Analyzer and sent only to committers of this repository.*
"""
        except Exception as e:
            logger.warning(f"Failed to read report file {report_path}: {e}")
            # Fallback content
            pr_metrics = final_state.get("pr_metrics", {})
            total_prs = pr_metrics.get("total_prs", 0)
            all_commits = final_state.get("all_commits", [])
            total_commits = len(all_commits)
            
            email_content = f"""# Git Development Report: {repo_name}

**Repository:** {repo_name}  
**Branch:** {branch}  
**Period:** {config.period_days} days ({from_date} to {to_date})  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Activity Summary

- **PRs:** {total_prs}
- **Commits:** {total_commits}
- **Branch:** {branch}

*Detailed analysis report was not available.*

---

*This report was automatically generated by Git Batch Analyzer.*
"""
    else:
        # Report file doesn't exist - create minimal content
        pr_metrics = final_state.get("pr_metrics", {})
        total_prs = pr_metrics.get("total_prs", 0)
        all_commits = final_state.get("all_commits", [])
        total_commits = len(all_commits)
        
        email_content = f"""# Git Development Report: {repo_name}

**Repository:** {repo_name}  
**Branch:** {branch}  
**Period:** {config.period_days} days ({from_date} to {to_date})  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Activity Summary

- **PRs:** {total_prs}  
- **Commits:** {total_commits}  
- **Branch:** {branch}

*Detailed report file not found: `{report_path}`*

---

*This report was automatically generated by Git Batch Analyzer.*
"""
    
    # Convert markdown to HTML
    try:
        html_content = markdown.markdown(
            email_content,
            extensions=['tables', 'codehilite', 'toc'],
            extension_configs={
                'codehilite': {
                    'css_class': 'highlight'
                }
            }
        )
        
        # Add styling
        styled_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        code {{ background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
        pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }}
        .highlight {{ background-color: #f8f8f8; }}
        hr {{ border: none; height: 1px; background-color: #ddd; margin: 20px 0; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
"""
        return styled_html
        
    except Exception as e:
        logger.error(f"Failed to convert markdown to HTML for {repo_name}: {e}")
        # Fallback to plain text
        return f"<html><body><pre>{email_content}</pre></body></html>"


if __name__ == "__main__":
    cli()