"""Main CLI interface for Git Batch Analyzer."""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

import click

from .config.loader import load_config_from_yaml, ConfigurationError
from .config.models import AnalysisConfig
from .workflow.graph import process_repositories


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
    '--dry-run',
    is_flag=True,
    help='Validate configuration and show what would be processed without running analysis'
)
def cli(
    config_file: Path,
    verbose: bool,
    output: Path,
    cache_dir: Path,
    period_days: int,
    dry_run: bool
) -> None:
    """
    Git Batch Analyzer - Analyze multiple git repositories and generate development metrics reports.
    
    CONFIG_FILE: Path to YAML configuration file specifying repositories and analysis parameters.
    
    Example usage:
    
        git-batch-analyzer config.yaml
        
        git-batch-analyzer config.yaml --verbose --output custom-report.md
        
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
        config = _apply_cli_overrides(config, output, cache_dir, period_days)
        
        # Log configuration summary
        _log_config_summary(config)
        
        if dry_run:
            logger.info("Dry run mode - configuration validation complete")
            _show_dry_run_summary(config)
            return
        
        # Process repositories
        logger.info(f"Starting analysis of {len(config.repositories)} repositories")
        results = _process_all_repositories(config)
        
        # Generate final report
        _generate_final_report(config, results)
        
        # Log summary
        _log_final_summary(results, config.output_file)
        
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
    period_days: int
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
    
    return config


def _log_config_summary(config: AnalysisConfig) -> None:
    """Log a summary of the loaded configuration."""
    logger.info(f"Configuration loaded successfully:")
    logger.info(f"  - Repositories: {len(config.repositories)}")
    logger.info(f"  - Analysis period: {config.period_days} days")
    logger.info(f"  - Stale branch threshold: {config.stale_days} days")
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
    
    # Log progress for each repository
    for repo_result in results["successful_repositories"]:
        click.echo(f"✓ Successfully processed: {repo_result['name']}")
        logger.info(f"✓ Successfully processed: {repo_result['name']}")
    
    for repo_result in results["failed_repositories"]:
        click.echo(f"✗ Failed to process: {repo_result['name']}", err=True)
        logger.warning(f"✗ Failed to process: {repo_result['name']}")
        for error in repo_result["errors"]:
            click.echo(f"  - {error}", err=True)
            logger.warning(f"  - {error}")
    
    return results


def _generate_final_report(config: AnalysisConfig, results: Dict[str, Any]) -> None:
    """Generate the final combined report from all successful repositories."""
    if not results["successful_repositories"]:
        click.echo("No repositories were successfully processed - cannot generate report", err=True)
        logger.error("No repositories were successfully processed - cannot generate report")
        return
    
    logger.info("Generating final combined report...")
    
    # Collect all final reports from successful repositories
    all_reports = []
    for repo_result in results["successful_repositories"]:
        final_state = repo_result["final_state"]
        if final_state.get("final_report"):
            all_reports.append({
                "name": repo_result["name"],
                "url": repo_result["url"],
                "report": final_state["final_report"]
            })
    
    if not all_reports:
        logger.error("No reports were generated from successful repositories")
        return
    
    # Combine reports into a single document
    combined_report = _combine_repository_reports(all_reports, config)
    
    # Write the final report
    try:
        config.output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config.output_file, 'w', encoding='utf-8') as f:
            f.write(combined_report)
        logger.info(f"Final report written to: {config.output_file}")
    except Exception as e:
        logger.error(f"Failed to write final report: {e}")
        raise


def _combine_repository_reports(
    reports: List[Dict[str, Any]], 
    config: AnalysisConfig
) -> str:
    """Combine individual repository reports into a single document."""
    from datetime import datetime
    
    # Generate report header
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"""# Git Batch Analysis Report

Generated: {timestamp}
Analysis Period: {config.period_days} days
Repositories Analyzed: {len(reports)}

---

"""
    
    # Add each repository's report
    combined_sections = [header]
    
    for i, repo_report in enumerate(reports, 1):
        repo_section = f"""## Repository {i}: {repo_report['name']}

**URL:** {repo_report['url']}

{repo_report['report']}

---

"""
        combined_sections.append(repo_section)
    
    return "\n".join(combined_sections)


def _log_final_summary(results: Dict[str, Any], output_file: Path) -> None:
    """Log a final summary of the analysis results."""
    successful_count = len(results["successful_repositories"])
    failed_count = len(results["failed_repositories"])
    total_count = successful_count + failed_count
    
    # Echo to user
    click.echo("\n" + "="*60)
    click.echo("ANALYSIS COMPLETE")
    click.echo("="*60)
    click.echo(f"Total repositories: {total_count}")
    click.echo(f"Successfully processed: {successful_count}")
    click.echo(f"Failed: {failed_count}")
    
    if successful_count > 0:
        click.echo(f"Report generated: {output_file}")
    
    if failed_count > 0:
        click.echo(f"\nFailed repositories:")
        for repo_result in results["failed_repositories"]:
            click.echo(f"  - {repo_result['name']}: {repo_result['url']}")
    
    click.echo("="*60)
    
    # Also log for debugging
    logger.info("\n" + "="*60)
    logger.info("ANALYSIS COMPLETE")
    logger.info("="*60)
    logger.info(f"Total repositories: {total_count}")
    logger.info(f"Successfully processed: {successful_count}")
    logger.info(f"Failed: {failed_count}")
    
    if successful_count > 0:
        logger.info(f"Report generated: {output_file}")
    
    if failed_count > 0:
        logger.warning(f"\nFailed repositories:")
        for repo_result in results["failed_repositories"]:
            logger.warning(f"  - {repo_result['name']}: {repo_result['url']}")
    
    logger.info("="*60)


if __name__ == "__main__":
    cli()