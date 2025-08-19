"""LangGraph workflow definition for Git Batch Analyzer."""

from typing import Dict, Any, List
from langgraph.graph import StateGraph, END

from ..types import AnalysisState
from .nodes import (
    sync_node,
    collect_node,
    metrics_node,
    stale_node,
    user_analysis_node,
    commit_quality_node,
    tables_node,
    exec_summary_node,
    org_trend_node,
    assembler_node
)


def create_workflow():
    """Create and compile the LangGraph workflow for git analysis.
    
    The workflow follows this sequence:
    1. sync_node: Clone/fetch repository
    2. collect_node: Gather merge commits and branch data
    3. metrics_node: Calculate PR metrics and aggregations
    4. stale_node: Identify stale branches
    5. user_analysis_node: Analyze user commit patterns and generate recommendations
    6. commit_quality_node: Analyze commit message quality vs actual changes
    7. tables_node: Generate markdown tables including user statistics
    8. exec_summary_node: Generate LLM executive summary (if enabled)
    9. org_trend_node: Generate LLM organizational trends (if enabled)
    10. assembler_node: Combine all sections into final report
    
    Returns:
        Compiled LangGraph workflow ready for execution
    """
    # Create the state graph
    workflow = StateGraph(AnalysisState)
    
    # Add all nodes to the workflow
    workflow.add_node("sync", sync_node)
    workflow.add_node("collect", collect_node)
    workflow.add_node("metrics", metrics_node)
    workflow.add_node("stale", stale_node)
    workflow.add_node("user_analysis", user_analysis_node)
    workflow.add_node("commit_quality", commit_quality_node)
    workflow.add_node("tables", tables_node)
    workflow.add_node("exec_summary", exec_summary_node)
    workflow.add_node("org_trend", org_trend_node)
    workflow.add_node("assembler", assembler_node)
    
    # Set entry point
    workflow.set_entry_point("sync")
    
    # Define the workflow edges with conditional logic
    workflow.add_conditional_edges(
        "sync",
        _should_continue_after_sync,
        {
            "continue": "collect",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "collect",
        _should_continue_after_collect,
        {
            "continue": "metrics",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "metrics",
        _should_continue_after_metrics,
        {
            "continue": "stale",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "stale",
        _should_continue_after_stale,
        {
            "continue": "user_analysis",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "user_analysis",
        _should_continue_after_user_analysis,
        {
            "continue": "commit_quality",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "commit_quality",
        _should_continue_after_commit_quality,
        {
            "continue": "tables",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "tables",
        _should_continue_after_tables,
        {
            "continue": "exec_summary",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "exec_summary",
        _should_continue_after_exec_summary,
        {
            "continue": "org_trend",
            "end": END
        }
    )
    
    workflow.add_conditional_edges(
        "org_trend",
        _should_continue_after_org_trend,
        {
            "continue": "assembler",
            "end": END
        }
    )
    
    # Assembler always ends the workflow
    workflow.add_edge("assembler", END)
    
    # Compile and return the workflow
    return workflow.compile()


def _should_continue_after_sync(state: AnalysisState) -> str:
    """Determine if workflow should continue after sync node.
    
    Args:
        state: Current analysis state
        
    Returns:
        "continue" if sync was successful, "end" if it failed
    """
    if state.get("sync_completed", False):
        return "continue"
    else:
        return "end"


def _should_continue_after_collect(state: AnalysisState) -> str:
    """Determine if workflow should continue after collect node.
    
    Args:
        state: Current analysis state
        
    Returns:
        "continue" if collect was successful, "end" if it failed
    """
    if state.get("collect_completed", False):
        return "continue"
    else:
        return "end"


def _should_continue_after_metrics(state: AnalysisState) -> str:
    """Determine if workflow should continue after metrics node.
    
    Args:
        state: Current analysis state
        
    Returns:
        "continue" if metrics was successful, "end" if it failed
    """
    if state.get("metrics_completed", False):
        return "continue"
    else:
        return "end"


def _should_continue_after_stale(state: AnalysisState) -> str:
    """Determine if workflow should continue after stale node.
    
    Args:
        state: Current analysis state
        
    Returns:
        "continue" if stale analysis was successful, "end" if it failed
    """
    if state.get("stale_completed", False):
        return "continue"
    else:
        return "end"


def _should_continue_after_tables(state: AnalysisState) -> str:
    """Determine if workflow should continue after tables node.
    
    Args:
        state: Current analysis state
        
    Returns:
        "continue" if tables generation was successful, "end" if it failed
    """
    if state.get("tables_completed", False):
        return "continue"
    else:
        return "end"


def _should_continue_after_exec_summary(state: AnalysisState) -> str:
    """Determine if workflow should continue after exec_summary node.
    
    Args:
        state: Current analysis state
        
    Returns:
        "continue" if exec summary was successful, "end" if it failed
    """
    if state.get("exec_summary_completed", False):
        return "continue"
    else:
        return "end"


def _should_continue_after_user_analysis(state: AnalysisState) -> str:
    """Determine if workflow should continue after user_analysis node.
    
    Args:
        state: Current analysis state
        
    Returns:
        "continue" if user analysis was successful, "end" if it failed
    """
    if state.get("user_analysis_completed", False):
        return "continue"
    else:
        return "end"


def _should_continue_after_commit_quality(state: AnalysisState) -> str:
    """Determine if workflow should continue after commit_quality node.
    
    Args:
        state: Current analysis state
        
    Returns:
        "continue" if commit quality analysis was successful, "end" if it failed
    """
    if state.get("commit_quality_completed", False):
        return "continue"
    else:
        return "end"


def _should_continue_after_org_trend(state: AnalysisState) -> str:
    """Determine if workflow should continue after org_trend node.
    
    Args:
        state: Current analysis state
        
    Returns:
        "continue" if org trend analysis was successful, "end" if it failed
    """
    if state.get("org_trend_completed", False):
        return "continue"
    else:
        return "end"


def process_repositories(
    repositories: List[Dict[str, Any]], 
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Process multiple repositories using the workflow, analyzing all branches in each repository.
    
    This function handles:
    - Creating workflow instances for each branch in each repository
    - Getting all branches from each repository first
    - Running workflows with proper error handling
    - Continuing processing even if individual repositories/branches fail
    - Collecting results and errors from all repository branches
    - Parallel processing for improved performance
    
    Args:
        repositories: List of repository configurations
        config: Global configuration dictionary
        
    Returns:
        Dictionary containing results and errors from all repository branches
    """
    from pathlib import Path
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ..types import create_initial_state
    from ..tools.git_tool import GitTool # Import GitTool here
    
    workflow = create_workflow()
    results = {
        "successful_repositories": [],
        "failed_repositories": [],
        "errors": []
    }
    
    # Get parallelism config - default to 4 workers
    max_workers = config.get("max_workers", 4)
    
    # Process repositories in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all repository processing tasks
        future_to_repo = {
            executor.submit(_process_single_repository, repo_config, config, workflow): repo_config
            for repo_config in repositories
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_repo):
            repo_config = future_to_repo[future]
            try:
                repo_results = future.result()
                # Merge results from this repository
                results["successful_repositories"].extend(repo_results["successful_repositories"])
                results["failed_repositories"].extend(repo_results["failed_repositories"])
                results["errors"].extend(repo_results["errors"])
            except Exception as e:
                # Handle unexpected errors from the entire repository processing
                repository_url = repo_config["url"]
                repository_name = repo_config.get("name") or _extract_repo_name(repository_url)
                error_msg = f"Unexpected error processing {repository_url}: {str(e)}"
                results["failed_repositories"].append({
                    "name": repository_name,
                    "url": repository_url,
                    "branch": "all",
                    "errors": [str(e)]
                })
                results["errors"].append(error_msg)
    
    return results


def _process_single_repository(
    repo_config: Dict[str, Any], 
    config: Dict[str, Any], 
    workflow
) -> Dict[str, Any]:
    """Process a single repository and all its branches.
    
    Args:
        repo_config: Repository configuration
        config: Global configuration dictionary
        workflow: Compiled LangGraph workflow
        
    Returns:
        Dictionary containing results and errors from this repository's branches
    """
    from pathlib import Path
    from ..types import create_initial_state
    from ..tools.git_tool import GitTool
    
    results = {
        "successful_repositories": [],
        "failed_repositories": [],
        "errors": []
    }
    
    try:
        # Extract repository information
        repository_url = repo_config["url"]
        repository_name = repo_config.get("name") or _extract_repo_name(repository_url)
        
        # Create cache path
        cache_dir = Path(config.get("cache_dir", "~/.cache/git-analyzer")).expanduser()
        cache_path = cache_dir / repository_name
        
        # First, clone and get all branches from the repository
        git_tool = GitTool(cache_path)
        
        # Get all remote branches directly using ls-remote (more efficient)
        ls_remote_response = git_tool._run_git_command(["ls-remote", "--heads", repository_url], cwd=Path.cwd())
        if not ls_remote_response.success:
            results["failed_repositories"].append({
                "name": repository_name,
                "url": repository_url,
                "branch": "all",
                "errors": [f"Failed to list remote branches: {ls_remote_response.error}"]
            })
            return results
        
        # Parse ls-remote output to get branch names
        remote_branches = []
        for line in ls_remote_response.data.split('\n'):
            line = line.strip()
            if line:
                parts = line.split('\t')
                if len(parts) == 2 and parts[1].startswith('refs/heads/'):
                    branch_name = parts[1].replace('refs/heads/', '')
                    remote_branches.append(branch_name)
        
        # Remove duplicates and sort
        real_branches = sorted(list(set(remote_branches)))
        
        # If no branches found, try default branches
        if not real_branches:
            real_branches = ["main", "master", "develop"]
        
        # Clone repository if it doesn't exist
        if not cache_path.exists():
            # If we have multiple branches to analyze, do a full clone
            # Otherwise, use shallow clone for efficiency
            clone_depth = 0 if len(real_branches) > 1 else 1
            
            clone_response = git_tool.clone(repository_url, depth=clone_depth)
            if not clone_response.success:
                results["failed_repositories"].append({
                    "name": repository_name,
                    "url": repository_url,
                    "branch": "all",
                    "errors": [f"Failed to clone repository: {clone_response.error}"]
                })
                return results
        
        # First, fetch all remote branches to make them available locally
        fetch_all_response = git_tool._run_git_command(["fetch", "origin", "--prune"])
        if not fetch_all_response.success:
            # Try fetching each branch individually as fallback
            for branch in real_branches:
                fetch_response = git_tool._run_git_command(["fetch", "origin", branch])
                if not fetch_response.success:
                    pass  # Silently continue, checkout will handle missing branches
        
        # Analyze each branch separately
        for branch in real_branches:
            try:
                # Create unique name for this branch analysis
                branch_analysis_name = f"{repository_name}-{branch}"
                
                # Checkout the specific branch for analysis
                checkout_response = git_tool.checkout(branch)
                if not checkout_response.success:
                    results["failed_repositories"].append({
                        "name": branch_analysis_name,
                        "url": repository_url,
                        "branch": branch,
                        "errors": [f"Failed to checkout branch '{branch}': {checkout_response.error}"]
                    })
                    continue
                
                # Create initial state for this repository-branch combination
                initial_state = create_initial_state(
                    config=config,
                    repository_url=repository_url,
                    repository_name=branch_analysis_name,  # Include branch in name
                    branch=branch,
                    cache_path=cache_path
                )
                
                # Run the workflow for this repository-branch combination
                final_state = workflow.invoke(initial_state)
                
                # Check if workflow completed successfully
                if final_state.get("assembler_completed", False):
                    results["successful_repositories"].append({
                        "name": branch_analysis_name,
                        "url": repository_url,
                        "branch": branch,
                        "final_state": final_state
                    })
                else:
                    # Workflow failed but we continue with other branches
                    repo_errors = final_state.get("errors", [])
                    results["failed_repositories"].append({
                        "name": branch_analysis_name,
                        "url": repository_url,
                        "branch": branch,
                        "errors": repo_errors
                    })
                    results["errors"].extend([f"{branch_analysis_name}: {error}" for error in repo_errors])
                    
            except Exception as e:
                # Handle unexpected errors during branch processing
                error_msg = f"Unexpected error processing {repository_name}-{branch}: {str(e)}"
                results["failed_repositories"].append({
                    "name": f"{repository_name}-{branch}",
                    "url": repository_url,
                    "branch": branch,
                    "errors": [str(e)]
                })
                results["errors"].append(error_msg)
                
    except Exception as e:
        # Handle unexpected errors during repository processing
        error_msg = f"Unexpected error processing {repository_url}: {str(e)}"
        results["failed_repositories"].append({
            "name": repository_name if 'repository_name' in locals() else "unknown",
            "url": repository_url,
            "branch": "all",
            "errors": [str(e)]
        })
        results["errors"].append(error_msg)
    
    return results


def _extract_repo_name(repository_url: str) -> str:
    """Extract repository name from URL.
    
    Args:
        repository_url: Git repository URL
        
    Returns:
        Repository name extracted from URL
    """
    # Handle both SSH and HTTPS URLs
    if repository_url.endswith('.git'):
        repository_url = repository_url[:-4]
    
    # Extract the last part of the path as repository name
    return repository_url.split('/')[-1]