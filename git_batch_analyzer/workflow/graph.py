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
    6. tables_node: Generate markdown tables including user statistics
    7. exec_summary_node: Generate LLM executive summary (if enabled)
    8. org_trend_node: Generate LLM organizational trends (if enabled)
    9. assembler_node: Combine all sections into final report
    
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
    """Process multiple repositories using the workflow.
    
    This function handles:
    - Creating workflow instances for each repository
    - Running workflows with proper error handling
    - Continuing processing even if individual repositories fail
    - Collecting results and errors from all repositories
    
    Args:
        repositories: List of repository configurations
        config: Global configuration dictionary
        
    Returns:
        Dictionary containing results and errors from all repositories
    """
    from pathlib import Path
    from ..types import create_initial_state
    
    workflow = create_workflow()
    results = {
        "successful_repositories": [],
        "failed_repositories": [],
        "errors": []
    }
    
    for repo_config in repositories:
        try:
            # Extract repository information
            repository_url = repo_config["url"]
            repository_name = repo_config.get("name") or _extract_repo_name(repository_url)
            branch = repo_config.get("branch", "main")
            
            # Create cache path
            cache_dir = Path(config.get("cache_dir", "~/.cache/git-analyzer")).expanduser()
            cache_path = cache_dir / repository_name
            
            # Create initial state for this repository
            initial_state = create_initial_state(
                config=config,
                repository_url=repository_url,
                repository_name=repository_name,
                branch=branch,
                cache_path=cache_path
            )
            
            # Run the workflow for this repository
            final_state = workflow.invoke(initial_state)
            
            # Check if workflow completed successfully
            if final_state.get("assembler_completed", False):
                results["successful_repositories"].append({
                    "name": repository_name,
                    "url": repository_url,
                    "final_state": final_state
                })
            else:
                # Workflow failed but we continue with other repositories
                repo_errors = final_state.get("errors", [])
                results["failed_repositories"].append({
                    "name": repository_name,
                    "url": repository_url,
                    "errors": repo_errors
                })
                results["errors"].extend([f"{repository_name}: {error}" for error in repo_errors])
                
        except Exception as e:
            # Handle unexpected errors during repository processing
            error_msg = f"Unexpected error processing {repository_url}: {str(e)}"
            results["failed_repositories"].append({
                "name": repository_name if 'repository_name' in locals() else "unknown",
                "url": repository_url,
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