# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Installation
```bash
# Install with uv (preferred)
uv pip install -e .

# Install with development dependencies
uv pip install -e ".[dev]"
```

### Running the Application
```bash
# Basic usage
git-batch-analyzer config.yaml

# With verbose output
git-batch-analyzer config.yaml --verbose

# Dry run to validate configuration
git-batch-analyzer config.yaml --dry-run

# Override output file
git-batch-analyzer config.yaml --output custom-report.md

# Run directly with Python module
python -m git_batch_analyzer config.yaml
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=git_batch_analyzer

# Run specific test file
pytest tests/test_git_tool.py

# Run tests with verbose output
pytest -v
```

### Code Quality
```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Type checking with mypy
mypy git_batch_analyzer

# Run pre-commit hooks
pre-commit run --all-files
```

## Architecture Overview

This is a **LangGraph-based system** for analyzing multiple git repositories and generating comprehensive development metrics reports. The architecture follows a workflow pattern:

### Core Components

1. **Main CLI** (`git_batch_analyzer/main.py`): Click-based command-line interface that orchestrates the entire analysis process
2. **Configuration System** (`git_batch_analyzer/config/`): YAML-based configuration loading with Pydantic models
3. **LangGraph Workflow** (`git_batch_analyzer/workflow/`): State-based workflow execution using LangGraph
4. **Analysis Tools** (`git_batch_analyzer/tools/`): Specialized tools for different analysis tasks
5. **Type System** (`git_batch_analyzer/types.py`): Shared type definitions and state management

### Workflow Execution Sequence

The LangGraph workflow (`workflow/graph.py`) executes these nodes in sequence:

1. **sync_node**: Clone/fetch repository from remote
2. **collect_node**: Gather merge commits and branch data  
3. **metrics_node**: Calculate PR metrics and aggregations
4. **stale_node**: Identify stale branches based on age threshold
5. **user_analysis_node**: Analyze individual developer patterns and generate personalized recommendations
6. **tables_node**: Generate markdown tables for metrics and user statistics
7. **exec_summary_node**: Generate LLM executive summary (if LLM enabled)
8. **org_trend_node**: Generate LLM organizational trends (if LLM enabled)
9. **assembler_node**: Combine all sections into final report

Each node has conditional logic to handle failures gracefully - if any step fails, the workflow can terminate early rather than continuing with invalid data.

### Configuration Structure

Configuration uses YAML format with these main sections:
- **repositories**: List of git repositories to analyze (URL + optional branch)
- **analysis parameters**: `period_days`, `stale_days`, `fetch_depth`, `top_k_files`
- **output settings**: `cache_dir`, `output_file`
- **llm configuration**: Optional LLM integration for summaries (OpenAI, Anthropic, Azure, OpenRouter)

### Tool Architecture

Each tool in `tools/` is responsible for a specific domain:
- **git_tool.py**: Repository operations (clone, fetch, log parsing)
- **calc_tool.py**: Metrics calculations and aggregations  
- **llm_tool.py**: LLM integration for summaries and personalized recommendations
- **md_tool.py**: Markdown report generation including user statistics tables
- **user_analysis_tool.py**: Individual developer analysis and commit pattern classification
- **cache_tool.py**: Caching system for repository data
- **user_tool.py**: User interaction and progress feedback

### Personalized Developer Recommendations

The system now includes comprehensive individual developer analysis:

**User Commit Analysis**:
- Tracks all commits per developer (not just merges)
- Analyzes commit frequency and timing patterns
- Calculates total lines changed per developer

**File Hotspot Detection**:
- Identifies files each developer modifies most frequently
- Tracks modification counts and line changes per file
- Helps identify code ownership patterns

**Work Classification**:
- Automatically categorizes commits by type (feature, bugfix, refactor, docs, test, chore, style)
- Uses regex pattern matching on commit messages
- Provides confidence scores for classifications

**Personalized Recommendations**:
- LLM-generated recommendations tailored to each developer's patterns
- Rule-based fallback recommendations when LLM is unavailable
- Focus areas: code quality, testing practices, commit conventions, work balance
- Maximum 50 words per recommendation for actionable insights

### State Management

Uses `AnalysisState` TypedDict to pass data between workflow nodes. State includes repository info, analysis results, generated content, and error tracking.

### Multi-Repository Processing

The system processes multiple repositories sequentially, continuing analysis even if individual repositories fail. Results are aggregated into a single comprehensive report.