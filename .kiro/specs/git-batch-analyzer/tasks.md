# Implementation Plan

- [x] 1. Set up project structure and core configuration
  - Create pyproject.toml with uv configuration and dependencies
  - Set up basic package structure with __init__.py files
  - Implement configuration dataclasses and YAML loading
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Implement state management and core types
  - Create AnalysisState TypedDict with all required fields
  - Define core data structures (MergeCommit, BranchInfo, DiffStats, PRMetrics)
  - Implement ToolResponse dataclass for consistent error handling
  - _Requirements: 2.1, 2.2, 7.3_

- [x] 3. Create git operations tool
  - Implement GitTool class with clone, fetch, log_merges, diff_stats, and remote_branches methods
  - Add shallow clone support with configurable depth
  - Implement structured JSON responses for all git operations
  - Write unit tests for git tool with mocked git operations
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 8.1_

- [x] 4. Create calculation utilities tool
  - Implement CalcTool class with lead_time, percentile, group_by_iso_week, and topk_counts methods
  - Add support for configurable k value in topk_counts
  - Ensure all calculations return deterministic results
  - Write unit tests for all calculation functions
  - _Requirements: 3.2, 3.3, 3.4, 3.5, 2.1, 8.1_

- [x] 5. Implement caching and markdown tools
  - Create CacheTool class for JSON read/write operations
  - Implement MdTool class for deterministic table rendering
  - Add cache directory management and repository path handling
  - Write unit tests for caching and markdown generation
  - _Requirements: 2.3, 6.2, 8.1_

- [x] 6. Create LLM integration tool
  - Implement LLMTool class with OpenAI integration
  - Add executive summary generation (120 words max)
  - Add organizational trend analysis functionality
  - Implement safety checks to never send source code
  - Write unit tests with mocked LLM responses
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 8.1_

- [x] 7. Implement LangGraph workflow nodes
  - Create sync_node for repository cloning and fetching
  - Create collect_node for gathering merge commits and branch data
  - Create metrics_node for calculating PR metrics and aggregations
  - Create stale_node for identifying stale branches
  - Write unit tests for each node with mock tools
  - _Requirements: 2.1, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 8.1_

- [x] 8. Implement report generation nodes
  - Create tables_node for generating deterministic markdown tables
  - Create exec_summary_node for LLM-generated executive summaries
  - Create org_trend_node for LLM-generated organizational insights
  - Create assembler_node for combining all sections into final report
  - Write unit tests for report generation with fixed section ordering
  - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 8.1_

- [ ] 9. Create LangGraph workflow definition
  - Implement create_workflow function with all nodes and edges
  - Set up proper entry and finish points
  - Add error handling for node failures
  - Ensure workflow continues processing other repositories on individual failures
  - Write integration tests for complete workflow execution
  - _Requirements: 2.2, 8.2_

- [x] 10. Implement CLI interface and main entry point
  - Create main.py with Click-based CLI interface
  - Add config file validation and loading
  - Implement multi-repository processing loop
  - Add logging for repository failures and progress tracking
  - Write end-to-end tests with sample configurations
  - _Requirements: 1.1, 2.2, 6.4, 8.2_

- [ ] 11. Add comprehensive error handling and logging
  - Implement graceful handling of repository access failures
  - Add structured logging for debugging and monitoring
  - Ensure deterministic behavior with identical inputs
  - Add validation for configuration parameters
  - Write tests for various failure scenarios
  - _Requirements: 2.2, 7.3, 8.3, 8.4_

- [ ] 12. Create golden file testing framework
  - Set up fixture repository with known commit history
  - Create golden report.md file for comparison testing
  - Implement test that runs full workflow and compares output
  - Add test for LLM-disabled mode producing complete reports
  - Verify deterministic output with identical configurations
  - _Requirements: 8.2, 8.3, 8.5_

- [x] 13. Add configuration validation and defaults
  - Implement validation for repository URLs and configuration parameters
  - Add support for configurable stale_days threshold
  - Set up proper default values for all optional configuration fields
  - Add configuration schema validation with helpful error messages
  - Write tests for configuration edge cases and validation
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 4.2_

- [ ] 14. Optimize performance and add concurrent processing
  - Implement concurrent repository processing where safe
  - Add progress indicators for long-running operations
  - Optimize git operations for large repositories
  - Add memory usage monitoring and optimization
  - Write performance tests with multiple repositories
  - _Requirements: 2.3, 7.1, 7.5_

- [ ] 15. Final integration and documentation
  - Create comprehensive README with usage examples
  - Add example configuration files
  - Ensure all requirements are covered by implementation
  - Run full test suite and verify all tests pass
  - Validate deterministic behavior across different environments
  - _Requirements: 8.2, 8.3_