# Requirements Document

## Introduction

The Git Batch Analyzer is a LangGraph-based system that analyzes multiple git repositories to generate comprehensive development metrics reports. The system takes a YAML configuration file specifying repositories to analyze and produces a deterministic markdown report containing executive summaries, per-repository metrics, organizational trends, and stale branch analysis.

## Requirements

### Requirement 1

**User Story:** As a development manager, I want to analyze multiple git repositories with a single configuration file, so that I can get consistent metrics across all my team's projects.

#### Acceptance Criteria

1. WHEN a user provides a YAML config file with repository URLs THEN the system SHALL process all specified repositories
2. WHEN the config specifies a branch THEN the system SHALL analyze that branch, OTHERWISE the system SHALL use the remote HEAD
3. WHEN the config specifies a period_days THEN the system SHALL analyze commits from that time period, OTHERWISE the system SHALL default to 7 days
4. WHEN the config specifies cache_dir THEN the system SHALL use that directory for caching, OTHERWISE the system SHALL use ~/.cache/git-analyzer
5. WHEN the config specifies an output file THEN the system SHALL write the report to that location, OTHERWISE the system SHALL use report.md

### Requirement 2

**User Story:** As a development manager, I want deterministic report generation, so that identical inputs always produce identical outputs for consistent analysis.

#### Acceptance Criteria

1. WHEN the same YAML configuration is used with identical repository states THEN the system SHALL produce identical report.md files
2. WHEN repository cloning or fetching fails for one repository THEN the system SHALL log the failure and continue processing other repositories
3. WHEN caching is enabled THEN the system SHALL reuse existing cloned repositories unless forced to refresh
4. WHEN generating reports THEN the system SHALL use only deterministic tools for data processing sections

### Requirement 3

**User Story:** As a development manager, I want comprehensive git metrics analysis, so that I can understand development patterns and performance across repositories.

#### Acceptance Criteria

1. WHEN analyzing repositories THEN the system SHALL extract merge commits with timestamps, parents, and messages
2. WHEN calculating metrics THEN the system SHALL compute lead time percentiles (50th and 75th)
3. WHEN calculating metrics THEN the system SHALL compute change size percentiles (50th and 75th)
4. WHEN analyzing code changes THEN the system SHALL identify top-k file churn hotspots with configurable k value (default k=10)
5. WHEN processing commits THEN the system SHALL group data by ISO week for trend analysis

### Requirement 4

**User Story:** As a development manager, I want to identify stale branches, so that I can maintain repository hygiene and reduce technical debt.

#### Acceptance Criteria

1. WHEN analyzing remote branches THEN the system SHALL list all branches with their last commit timestamps
2. WHEN identifying stale branches THEN the system SHALL use a configurable stale_days threshold (default = period_days) to determine branches with no commits in that timeframe
3. WHEN generating the report THEN the system SHALL include a dedicated section listing all stale branches

### Requirement 5

**User Story:** As a development manager, I want AI-generated insights in my reports, so that I can quickly understand trends and patterns without manual analysis.

#### Acceptance Criteria

1. WHEN generating reports THEN the system SHALL create an executive summary of 120 words or less using LLM
2. WHEN creating the executive summary THEN the system SHALL base it on weekly aggregations and lead time percentiles
3. WHEN generating organizational trends THEN the system SHALL use LLM to analyze weekly aggregated data for org-level insights
4. WHEN using LLM services THEN the system SHALL never send source code, only aggregated metrics
5. WHEN calling LLM services THEN the system SHALL use the configured provider, model, and temperature settings

### Requirement 6

**User Story:** As a development manager, I want structured report output, so that I can easily consume and share the analysis results.

#### Acceptance Criteria

1. WHEN generating reports THEN the system SHALL produce a markdown file with sections in this order: executive summary, per-repo tables, org-level trends, and stale branch list
2. WHEN creating tables THEN the system SHALL use deterministic markdown rendering
3. WHEN assembling the final report THEN the system SHALL combine all sections into a single report.md file
4. WHEN writing output THEN the system SHALL use the filename specified in the configuration

### Requirement 7

**User Story:** As a developer, I want reliable git operations, so that the system can handle various repository states and network conditions.

#### Acceptance Criteria

1. WHEN cloning repositories THEN the system SHALL perform shallow clones with configurable fetch depth (default = 200 commits)
2. WHEN fetching updates THEN the system SHALL fetch the latest changes from remote
3. WHEN git operations fail THEN the system SHALL return structured JSON responses with error information
4. WHEN accessing git data THEN the system SHALL use consistent JSON-only tool interfaces
5. WHEN caching repositories THEN the system SHALL store them under cache_dir/<repo-name> structure

### Requirement 8

**User Story:** As a developer, I want comprehensive testing capabilities, so that I can ensure the system works correctly across different scenarios.

#### Acceptance Criteria

1. WHEN running unit tests THEN each tool SHALL return responses matching the defined JSON schema
2. WHEN running integration tests THEN the system SHALL process fixture repositories and compare output against golden files
3. WHEN testing determinism THEN identical inputs SHALL produce identical outputs that can be verified through file comparison
4. WHEN testing failure scenarios THEN the system SHALL handle and log repository access failures gracefully
5. WHEN running tests with LLM disabled THEN the system SHALL still produce a complete report with tables and stale branches (excluding AI-generated summaries)