"""Unit tests for MdTool with comprehensive markdown generation testing."""

import pytest
from datetime import datetime, timezone

from git_batch_analyzer.tools.md_tool import MdTool
from git_batch_analyzer.types import ToolResponse


class TestMdTool:
    """Test cases for MdTool class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.md_tool = MdTool()
    
    def test_render_table_basic(self):
        """Test basic table rendering functionality."""
        headers = ["Name", "Age", "City"]
        rows = [
            ["Alice", "25", "New York"],
            ["Bob", "30", "San Francisco"],
            ["Charlie", "35", "Chicago"]
        ]
        
        response = self.md_tool.render_table(headers, rows)
        
        assert response.success is True
        
        lines = response.data.split('\n')
        assert len(lines) == 5  # Header + separator + 3 data rows
        
        # Check header row
        assert "| Name    | Age | City          |" == lines[0]
        
        # Check separator row
        assert "| ------- | --- | ------------- |" == lines[1]
        
        # Check data rows
        assert "| Alice   | 25  | New York      |" == lines[2]
        assert "| Bob     | 30  | San Francisco |" == lines[3]
        assert "| Charlie | 35  | Chicago       |" == lines[4]
    
    def test_render_table_with_alignment(self):
        """Test table rendering with column alignment."""
        headers = ["Item", "Price", "Quantity"]
        rows = [
            ["Apple", "$1.50", "10"],
            ["Banana", "$0.75", "25"]
        ]
        alignment = ["left", "right", "center"]
        
        response = self.md_tool.render_table(headers, rows, alignment)
        
        assert response.success is True
        
        lines = response.data.split('\n')
        
        # Check separator row has correct alignment markers
        assert "| ------ | ----: | :------: |" == lines[1]
    
    def test_render_table_empty_rows(self):
        """Test table rendering with empty rows."""
        headers = ["Column1", "Column2"]
        rows = []
        
        response = self.md_tool.render_table(headers, rows)
        
        assert response.success is True
        
        lines = response.data.split('\n')
        assert len(lines) == 2  # Only header + separator
        assert "| Column1 | Column2 |" == lines[0]
        assert "| ------- | ------- |" == lines[1]
    
    def test_render_table_empty_headers(self):
        """Test table rendering with empty headers."""
        headers = []
        rows = [["data1", "data2"]]
        
        response = self.md_tool.render_table(headers, rows)
        
        assert response.success is False
        assert "Headers cannot be empty" in response.error
    
    def test_render_table_mismatched_columns(self):
        """Test table rendering with mismatched column counts."""
        headers = ["Col1", "Col2", "Col3"]
        rows = [
            ["A", "B", "C"],  # Correct
            ["D", "E"],       # Too few columns
            ["F", "G", "H", "I"]  # Too many columns
        ]
        
        # Should fail on first mismatched row
        response = self.md_tool.render_table(headers, rows)
        
        assert response.success is False
        assert "Row 1 has 2 columns, expected 3" in response.error
    
    def test_render_table_with_special_characters(self):
        """Test table rendering with special characters and unicode."""
        headers = ["Name", "Symbol", "Unicode"]
        rows = [
            ["Rocket", "🚀", "U+1F680"],
            ["Heart", "❤️", "U+2764"],
            ["Pi", "π", "U+03C0"],
            ["Quote", '"Hello"', "Quotes"]
        ]
        
        response = self.md_tool.render_table(headers, rows)
        
        assert response.success is True
        assert "🚀" in response.data
        assert "❤️" in response.data
        assert "π" in response.data
        assert '"Hello"' in response.data
    
    def test_render_table_with_numeric_data(self):
        """Test table rendering with numeric data types."""
        headers = ["Integer", "Float", "Boolean"]
        rows = [
            [42, 3.14159, True],
            [0, -2.5, False],
            [-100, 0.0, None]
        ]
        
        response = self.md_tool.render_table(headers, rows)
        
        assert response.success is True
        
        # All values should be converted to strings
        assert "42" in response.data
        assert "3.14159" in response.data
        assert "True" in response.data
        assert "False" in response.data
        assert "None" in response.data
    
    def test_render_table_column_width_calculation(self):
        """Test that column widths are calculated correctly."""
        headers = ["Short", "Very Long Header Name"]
        rows = [
            ["A", "B"],
            ["Very Long Data Value", "C"]
        ]
        
        response = self.md_tool.render_table(headers, rows)
        
        assert response.success is True
        
        lines = response.data.split('\n')
        
        # First column should be wide enough for "Very Long Data Value"
        # Second column should be wide enough for "Very Long Header Name"
        assert "| A                    | B                     |" == lines[2]
        assert "| Very Long Data Value | C                     |" == lines[3]
    
    def test_render_metrics_table(self):
        """Test rendering standardized metrics table."""
        pr_metrics = {
            "total_prs": 42,
            "lead_time_p50": 24.5,
            "lead_time_p75": 48.2,
            "change_size_p50": 15,
            "change_size_p75": 32
        }
        
        response = self.md_tool.render_metrics_table(pr_metrics)
        
        assert response.success is True
        
        # Check that all expected metrics are present
        assert "Total PRs" in response.data
        assert "42" in response.data
        assert "Lead Time P50 (hours)" in response.data
        assert "24.5" in response.data
        assert "Lead Time P75 (hours)" in response.data
        assert "48.2" in response.data
        assert "Change Size P50" in response.data
        assert "15" in response.data
        assert "Change Size P75" in response.data
        assert "32" in response.data
        
        # Check table structure
        lines = response.data.split('\n')
        assert len(lines) == 7  # Header + separator + 5 metric rows
    
    def test_render_metrics_table_missing_data(self):
        """Test rendering metrics table with missing data."""
        pr_metrics = {
            "total_prs": 10
            # Missing other metrics
        }
        
        response = self.md_tool.render_metrics_table(pr_metrics)
        
        assert response.success is True
        
        # Should use default values for missing metrics
        assert "10" in response.data  # total_prs
        assert "0.0" in response.data  # Default for missing lead times
        assert "0" in response.data   # Default for missing change sizes
    
    def test_render_weekly_counts_table(self):
        """Test rendering weekly PR counts table."""
        weekly_counts = {
            "2024-W03": 5,
            "2024-W01": 8,
            "2024-W02": 3,
            "2024-W04": 12
        }
        
        response = self.md_tool.render_weekly_counts_table(weekly_counts)
        
        assert response.success is True
        
        lines = response.data.split('\n')
        
        # Should be sorted chronologically
        assert "2024-W01" in lines[2]  # First data row
        assert "2024-W02" in lines[3]  # Second data row
        assert "2024-W03" in lines[4]  # Third data row
        assert "2024-W04" in lines[5]  # Fourth data row
        
        # Check counts are present
        assert "8" in response.data
        assert "3" in response.data
        assert "5" in response.data
        assert "12" in response.data
    
    def test_render_weekly_counts_table_empty(self):
        """Test rendering weekly counts table with no data."""
        response = self.md_tool.render_weekly_counts_table({})
        
        assert response.success is True
        assert response.data == "No weekly data available."
    
    def test_render_top_files_table(self):
        """Test rendering top files table."""
        top_files = [
            {"item": "src/main.py", "count": 15},
            {"item": "README.md", "count": 8},
            {"item": "tests/test_main.py", "count": 5},
            {"item": "config/settings.yaml", "count": 3}
        ]
        
        response = self.md_tool.render_top_files_table(top_files)
        
        assert response.success is True
        
        # Check that files and counts are present
        assert "src/main.py" in response.data
        assert "15" in response.data
        assert "README.md" in response.data
        assert "8" in response.data
        assert "tests/test_main.py" in response.data
        assert "5" in response.data
        
        lines = response.data.split('\n')
        assert len(lines) == 6  # Header + separator + 4 data rows
    
    def test_render_top_files_table_empty(self):
        """Test rendering top files table with no data."""
        response = self.md_tool.render_top_files_table([])
        
        assert response.success is True
        assert response.data == "No file change data available."
    
    def test_render_top_files_table_missing_fields(self):
        """Test rendering top files table with missing fields."""
        top_files = [
            {"item": "file1.py"},  # Missing count
            {"count": 5},          # Missing item
            {"item": "file2.py", "count": 3}  # Complete
        ]
        
        response = self.md_tool.render_top_files_table(top_files)
        
        assert response.success is True
        
        # Should handle missing fields gracefully
        assert "file1.py" in response.data
        assert "0" in response.data  # Default count
        assert "" in response.data   # Default item (empty string)
        assert "file2.py" in response.data
        assert "3" in response.data
    
    def test_render_stale_branches_table(self):
        """Test rendering stale branches table."""
        now = datetime.now(timezone.utc)
        old_timestamp = "2023-12-01T10:00:00+00:00"
        recent_timestamp = "2024-01-10T15:30:00+00:00"
        
        stale_branches = [
            {
                "name": "feature-old",
                "last_commit_hash": "abc123def456",
                "last_commit_timestamp": old_timestamp
            },
            {
                "name": "bugfix-ancient",
                "last_commit_hash": "xyz789uvw012",
                "last_commit_timestamp": recent_timestamp
            }
        ]
        
        response = self.md_tool.render_stale_branches_table(stale_branches)
        
        assert response.success is True
        
        # Check branch names are present
        assert "feature-old" in response.data
        assert "bugfix-ancient" in response.data
        
        # Check short hashes are present (first 8 characters)
        assert "abc123de" in response.data
        assert "xyz789uv" in response.data
        
        # Should be sorted by branch name
        lines = response.data.split('\n')
        # bugfix-ancient should come before feature-old alphabetically
        bugfix_line = next(i for i, line in enumerate(lines) if "bugfix-ancient" in line)
        feature_line = next(i for i, line in enumerate(lines) if "feature-old" in line)
        assert bugfix_line < feature_line
    
    def test_render_stale_branches_table_empty(self):
        """Test rendering stale branches table with no data."""
        response = self.md_tool.render_stale_branches_table([])
        
        assert response.success is True
        assert response.data == "No stale branches found."
    
    def test_render_stale_branches_table_invalid_timestamp(self):
        """Test rendering stale branches table with invalid timestamps."""
        stale_branches = [
            {
                "name": "branch1",
                "last_commit_hash": "abc123",
                "last_commit_timestamp": "invalid-timestamp"
            },
            {
                "name": "branch2",
                "last_commit_hash": "def456",
                "last_commit_timestamp": ""  # Empty timestamp
            },
            {
                "name": "branch3",
                "last_commit_hash": "ghi789"
                # Missing timestamp
            }
        ]
        
        response = self.md_tool.render_stale_branches_table(stale_branches)
        
        assert response.success is True
        
        # Should handle invalid timestamps gracefully
        assert "branch1" in response.data
        assert "branch2" in response.data
        assert "branch3" in response.data
        assert "Unknown" in response.data  # Should appear for invalid timestamps
    
    def test_render_section(self):
        """Test rendering markdown sections."""
        title = "Analysis Results"
        content = "This section contains the analysis results.\n\nHere are the findings."
        
        response = self.md_tool.render_section(title, content, level=2)
        
        assert response.success is True
        
        expected = "## Analysis Results\n\nThis section contains the analysis results.\n\nHere are the findings."
        assert response.data == expected
    
    def test_render_section_different_levels(self):
        """Test rendering sections with different header levels."""
        title = "Test Section"
        content = "Content here"
        
        # Test different header levels
        for level in range(1, 7):
            response = self.md_tool.render_section(title, content, level=level)
            assert response.success is True
            
            expected_prefix = "#" * level
            assert response.data.startswith(f"{expected_prefix} {title}")
    
    def test_render_section_invalid_level(self):
        """Test rendering section with invalid header level."""
        response = self.md_tool.render_section("Title", "Content", level=0)
        assert response.success is False
        assert "Header level must be between 1 and 6" in response.error
        
        response = self.md_tool.render_section("Title", "Content", level=7)
        assert response.success is False
        assert "Header level must be between 1 and 6" in response.error
    
    def test_combine_sections(self):
        """Test combining multiple markdown sections."""
        sections = [
            "# Main Title\n\nIntroduction text.",
            "## Section 1\n\nFirst section content.",
            "## Section 2\n\nSecond section content.",
            "### Subsection\n\nSubsection content."
        ]
        
        response = self.md_tool.combine_sections(sections)
        
        assert response.success is True
        
        # Sections should be joined with double newlines
        expected = "\n\n".join(sections)
        assert response.data == expected
    
    def test_combine_sections_with_empty_sections(self):
        """Test combining sections with empty and whitespace-only sections."""
        sections = [
            "# Title",
            "",  # Empty
            "   ",  # Whitespace only
            "## Section 1\n\nContent here.",
            None,  # None value
            "## Section 2\n\nMore content."
        ]
        
        response = self.md_tool.combine_sections(sections)
        
        assert response.success is True
        
        # Should filter out empty/None sections
        lines = response.data.split('\n')
        assert "# Title" in response.data
        assert "## Section 1" in response.data
        assert "## Section 2" in response.data
        
        # Should not have excessive empty lines from filtered sections
        assert "\n\n\n" not in response.data
    
    def test_combine_sections_empty_list(self):
        """Test combining empty list of sections."""
        response = self.md_tool.combine_sections([])
        
        assert response.success is True
        assert response.data == ""
    
    def test_combine_sections_all_empty(self):
        """Test combining list of all empty sections."""
        sections = ["", "   ", None, "\n\n"]
        
        response = self.md_tool.combine_sections(sections)
        
        assert response.success is True
        assert response.data == ""


class TestMdToolIntegration:
    """Integration tests for MdTool with realistic scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.md_tool = MdTool()
    
    def test_complete_report_generation(self):
        """Test generating a complete markdown report."""
        # Generate executive summary section
        exec_summary = "This analysis covers 3 repositories with 45 total PRs. Lead times show improvement with P50 at 18.5 hours."
        summary_response = self.md_tool.render_section("Executive Summary", exec_summary, level=1)
        assert summary_response.success is True
        
        # Generate metrics table
        pr_metrics = {
            "total_prs": 45,
            "lead_time_p50": 18.5,
            "lead_time_p75": 36.2,
            "change_size_p50": 22,
            "change_size_p75": 58
        }
        metrics_response = self.md_tool.render_metrics_table(pr_metrics)
        assert metrics_response.success is True
        
        metrics_section_response = self.md_tool.render_section("Repository Metrics", metrics_response.data, level=2)
        assert metrics_section_response.success is True
        
        # Generate weekly counts table
        weekly_counts = {
            "2024-W01": 12,
            "2024-W02": 15,
            "2024-W03": 18
        }
        weekly_response = self.md_tool.render_weekly_counts_table(weekly_counts)
        assert weekly_response.success is True
        
        weekly_section_response = self.md_tool.render_section("Weekly Activity", weekly_response.data, level=2)
        assert weekly_section_response.success is True
        
        # Generate top files table
        top_files = [
            {"item": "src/main.py", "count": 25},
            {"item": "src/utils.py", "count": 18},
            {"item": "README.md", "count": 12}
        ]
        files_response = self.md_tool.render_top_files_table(top_files)
        assert files_response.success is True
        
        files_section_response = self.md_tool.render_section("Top Changed Files", files_response.data, level=2)
        assert files_section_response.success is True
        
        # Generate stale branches table
        stale_branches = [
            {
                "name": "feature-abandoned",
                "last_commit_hash": "abc123def456",
                "last_commit_timestamp": "2023-11-15T10:00:00+00:00"
            }
        ]
        stale_response = self.md_tool.render_stale_branches_table(stale_branches)
        assert stale_response.success is True
        
        stale_section_response = self.md_tool.render_section("Stale Branches", stale_response.data, level=2)
        assert stale_section_response.success is True
        
        # Combine all sections
        all_sections = [
            summary_response.data,
            metrics_section_response.data,
            weekly_section_response.data,
            files_section_response.data,
            stale_section_response.data
        ]
        
        final_response = self.md_tool.combine_sections(all_sections)
        assert final_response.success is True
        
        # Verify complete report structure
        report = final_response.data
        assert "# Executive Summary" in report
        assert "## Repository Metrics" in report
        assert "## Weekly Activity" in report
        assert "## Top Changed Files" in report
        assert "## Stale Branches" in report
        
        # Verify data is present
        assert "45 total PRs" in report
        assert "18.5" in report  # P50 lead time
        assert "src/main.py" in report
        assert "feature-abandoned" in report
    
    def test_multi_repository_report(self):
        """Test generating report sections for multiple repositories."""
        repositories = [
            {
                "name": "frontend-app",
                "metrics": {
                    "total_prs": 25,
                    "lead_time_p50": 16.5,
                    "lead_time_p75": 32.1,
                    "change_size_p50": 18,
                    "change_size_p75": 45
                }
            },
            {
                "name": "backend-api",
                "metrics": {
                    "total_prs": 35,
                    "lead_time_p50": 22.3,
                    "lead_time_p75": 41.7,
                    "change_size_p50": 28,
                    "change_size_p75": 67
                }
            }
        ]
        
        repo_sections = []
        
        for repo in repositories:
            # Generate metrics table for each repository
            metrics_response = self.md_tool.render_metrics_table(repo["metrics"])
            assert metrics_response.success is True
            
            # Create section for this repository
            section_response = self.md_tool.render_section(
                f"Repository: {repo['name']}", 
                metrics_response.data, 
                level=2
            )
            assert section_response.success is True
            repo_sections.append(section_response.data)
        
        # Combine repository sections
        combined_response = self.md_tool.combine_sections(repo_sections)
        assert combined_response.success is True
        
        # Verify both repositories are present
        report = combined_response.data
        assert "Repository: frontend-app" in report
        assert "Repository: backend-api" in report
        assert "25" in report  # frontend PRs
        assert "35" in report  # backend PRs
        assert "16.5" in report  # frontend P50
        assert "22.3" in report  # backend P50
    
    def test_deterministic_table_rendering(self):
        """Test that table rendering is deterministic."""
        headers = ["File", "Changes", "Authors"]
        rows = [
            ["file1.py", "10", "3"],
            ["file2.py", "5", "2"],
            ["file3.py", "15", "4"]
        ]
        
        # Render the same table multiple times
        results = []
        for _ in range(5):
            response = self.md_tool.render_table(headers, rows)
            assert response.success is True
            results.append(response.data)
        
        # All results should be identical
        assert all(result == results[0] for result in results)
        
        # Test with different data order (should produce different but consistent results)
        shuffled_rows = [
            ["file3.py", "15", "4"],
            ["file1.py", "10", "3"],
            ["file2.py", "5", "2"]
        ]
        
        shuffled_results = []
        for _ in range(3):
            response = self.md_tool.render_table(headers, shuffled_rows)
            assert response.success is True
            shuffled_results.append(response.data)
        
        # Shuffled results should be consistent with each other
        assert all(result == shuffled_results[0] for result in shuffled_results)
        
        # But different from original order
        assert shuffled_results[0] != results[0]
    
    def test_large_table_rendering(self):
        """Test rendering large tables efficiently."""
        headers = ["ID", "Name", "Value", "Category", "Status"]
        
        # Generate large dataset
        rows = []
        for i in range(100):
            rows.append([
                str(i),
                f"Item_{i:03d}",
                str(i * 10.5),
                f"Category_{i % 5}",
                "Active" if i % 2 == 0 else "Inactive"
            ])
        
        response = self.md_tool.render_table(headers, rows)
        
        assert response.success is True
        
        lines = response.data.split('\n')
        assert len(lines) == 102  # Header + separator + 100 data rows
        
        # Verify first and last rows
        assert "Item_000" in lines[2]  # First data row
        assert "Item_099" in lines[101]  # Last data row
        
        # Verify table structure is maintained
        assert all(line.startswith('|') and line.endswith('|') for line in lines)
    
    def test_error_handling_and_recovery(self):
        """Test error handling in various edge cases."""
        # Test with None values in data
        headers = ["Col1", "Col2"]
        rows_with_none = [
            ["Value1", None],
            [None, "Value2"]
        ]
        
        response = self.md_tool.render_table(headers, rows_with_none)
        assert response.success is True
        assert "None" in response.data
        
        # Test with very long strings
        long_string = "A" * 1000
        long_rows = [["Short", long_string]]
        
        response = self.md_tool.render_table(["Col1", "Col2"], long_rows)
        assert response.success is True
        assert long_string in response.data
        
        # Test with empty strings
        empty_rows = [["", ""], ["Value", ""]]
        
        response = self.md_tool.render_table(["Col1", "Col2"], empty_rows)
        assert response.success is True
        
        # Should handle empty cells gracefully
        lines = response.data.split('\n')
        assert "|       |      |" == lines[2]  # Empty cells should have proper spacing
    
    def test_complex_data_types_conversion(self):
        """Test handling of complex data types in tables."""
        headers = ["Type", "Value", "Converted"]
        
        # Test various data types
        complex_data = [
            [list, [1, 2, 3], str([1, 2, 3])],
            [dict, {"key": "value"}, str({"key": "value"})],
            [tuple, (1, 2), str((1, 2))],
            [set, {1, 2, 3}, str({1, 2, 3})]
        ]
        
        response = self.md_tool.render_table(headers, complex_data)
        
        assert response.success is True
        
        # All complex types should be converted to strings
        assert "[1, 2, 3]" in response.data
        assert "{'key': 'value'}" in response.data or "{'key': 'value'}" in response.data
        assert "(1, 2)" in response.data
    
    def test_unicode_and_special_character_handling(self):
        """Test handling of unicode and special characters in tables."""
        headers = ["Language", "Greeting", "Symbol"]
        rows = [
            ["English", "Hello", "🇺🇸"],
            ["Chinese", "你好", "🇨🇳"],
            ["Japanese", "こんにちは", "🇯🇵"],
            ["Arabic", "مرحبا", "🇸🇦"],
            ["Russian", "Привет", "🇷🇺"],
            ["Special", "Chars: @#$%^&*()", "💻"]
        ]
        
        response = self.md_tool.render_table(headers, rows)
        
        assert response.success is True
        
        # All unicode characters should be preserved
        assert "你好" in response.data
        assert "こんにちは" in response.data
        assert "مرحبا" in response.data
        assert "Привет" in response.data
        assert "🇺🇸" in response.data
        assert "💻" in response.data
        assert "@#$%^&*()" in response.data
        
        # Table structure should be maintained despite varying character widths
        lines = response.data.split('\n')
        assert all(line.count('|') >= 4 for line in lines)  # At least 4 pipes per line (3 columns)
    
    def test_generate_report_filename(self):
        """Test generating report filenames with proper format."""
        repo_name = "my-awesome-repo"
        period_days = 7
        
        filename = self.md_tool.generate_report_filename(repo_name, period_days)
        
        # Should follow pattern: [repoName]report[fromDate]-[toDate].md
        assert filename.startswith("my-awesome-repo")
        assert "report" in filename
        assert filename.endswith(".md")
        
        # Should contain date range
        assert "-" in filename  # Date separator
        assert filename.count("-") >= 4  # At least YYYY-MM-DD-YYYY-MM-DD format
    
    def test_generate_report_filename_special_chars(self):
        """Test generating report filenames with special characters in repo name."""
        repo_names_and_expected = [
            ("repo/with/slashes", "repo_with_slashes"),
            ("repo with spaces", "repo_with_spaces"),
            ("repo@domain.com", "repo_domain.com"),
            ("repo:port", "repo_port"),
            ("normal-repo", "normal-repo")
        ]
        
        for repo_name, expected_clean in repo_names_and_expected:
            filename = self.md_tool.generate_report_filename(repo_name, 7)
            assert filename.startswith(expected_clean)
            assert "report" in filename
            assert filename.endswith(".md")
    
    def test_generate_report_filename_different_periods(self):
        """Test generating report filenames with different time periods."""
        repo_name = "test-repo"
        
        filename_7 = self.md_tool.generate_report_filename(repo_name, 7)
        filename_30 = self.md_tool.generate_report_filename(repo_name, 30)
        
        # Both should be valid but different (due to different start dates)
        assert filename_7.startswith("test-repo")
        assert filename_30.startswith("test-repo")
        assert filename_7 != filename_30  # Different periods should produce different filenames