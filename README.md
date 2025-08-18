# Git Batch Analyzer

A LangGraph-based system for analyzing multiple git repositories and generating comprehensive development metrics reports.

## Project Structure

```
git_batch_analyzer/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── models.py      # Configuration data classes
│   └── loader.py      # YAML configuration loading
├── tools/             # Analysis tools (git, calculations, etc.)
├── workflow/          # LangGraph workflow definitions
└── main.py           # CLI entry point

tests/                 # Test suite
example-config.yaml    # Example configuration file
```

## Configuration

The system uses YAML configuration files to specify repositories and analysis parameters. See `example-config.yaml` for a complete example.

## Installation

```bash
# Install with uv
uv pip install -e .

# Or install development dependencies
uv pip install -e ".[dev]"
```

## Usage

```bash
git-batch-analyzer config.yaml
```