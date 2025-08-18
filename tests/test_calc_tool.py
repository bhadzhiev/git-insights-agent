"""Unit tests for CalcTool with comprehensive calculation testing."""

from datetime import datetime, timezone
import pytest

from git_batch_analyzer.tools.calc_tool import CalcTool
from git_batch_analyzer.types import ToolResponse


class TestCalcTool:
    """Test cases for CalcTool class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calc_tool = CalcTool()
    
    def test_lead_time_with_merge_commits(self):
        """Test lead time calculation with valid merge commits."""
        merge_commits = [
            {
                "hash": "abc123",
                "timestamp": "2024-01-01T12:00:00+00:00",
                "parents": ["def456", "ghi789"],
                "message": "Merge pull request #1"
            },
            {
                "hash": "xyz789",
                "timestamp": "2024-01-02T14:30:00+00:00",
                "parents": ["jkl012", "mno345"],
                "message": "Merge branch 'feature'"
            }
        ]
        
        response = self.calc_tool.lead_time(merge_commits)
        
        assert response.success is True
        assert response.data["count"] == 2
        assert "mean" in response.data
        assert "median" in response.data
        assert "p50" in response.data
        assert "p75" in response.data
        # All values should be positive numbers
        assert all(isinstance(response.data[key], (int, float)) and response.data[key] >= 0 
                  for key in ["mean", "median", "p50", "p75"])
    
    def test_lead_time_with_no_merge_commits(self):
        """Test lead time calculation with no merge commits."""
        response = self.calc_tool.lead_time([])
        
        assert response.success is True
        assert response.data["count"] == 0
        assert response.data["mean"] == 0.0
        assert response.data["median"] == 0.0
        assert response.data["p50"] == 0.0
        assert response.data["p75"] == 0.0
    
    def test_lead_time_with_non_merge_commits(self):
        """Test lead time calculation with commits that aren't merges."""
        non_merge_commits = [
            {
                "hash": "abc123",
                "timestamp": "2024-01-01T12:00:00+00:00",
                "parents": ["def456"],  # Only one parent - not a merge
                "message": "Regular commit"
            },
            {
                "hash": "xyz789",
                "timestamp": "2024-01-02T14:30:00+00:00",
                "parents": [],  # No parents
                "message": "Initial commit"
            }
        ]
        
        response = self.calc_tool.lead_time(non_merge_commits)
        
        assert response.success is True
        assert response.data["count"] == 0  # No merge commits processed
    
    def test_lead_time_with_invalid_data(self):
        """Test lead time calculation with invalid data."""
        invalid_commits = [
            {
                "hash": "abc123",
                # Missing timestamp
                "parents": ["def456", "ghi789"],
                "message": "Merge pull request #1"
            }
        ]
        
        response = self.calc_tool.lead_time(invalid_commits)
        
        assert response.success is False
        assert "Error calculating lead time" in response.error
    
    def test_percentile_calculation(self):
        """Test percentile calculation with various values."""
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        
        # Test 50th percentile (median)
        response = self.calc_tool.percentile(values, 50)
        assert response.success is True
        assert response.data == 5.5  # Median of 1-10
        
        # Test 75th percentile
        response = self.calc_tool.percentile(values, 75)
        assert response.success is True
        assert response.data == 7.75
        
        # Test 25th percentile
        response = self.calc_tool.percentile(values, 25)
        assert response.success is True
        assert response.data == 3.25
        
        # Test 0th percentile (minimum)
        response = self.calc_tool.percentile(values, 0)
        assert response.success is True
        assert response.data == 1.0
        
        # Test 100th percentile (maximum)
        response = self.calc_tool.percentile(values, 100)
        assert response.success is True
        assert response.data == 10.0
    
    def test_percentile_with_empty_list(self):
        """Test percentile calculation with empty list."""
        response = self.calc_tool.percentile([], 50)
        
        assert response.success is True
        assert response.data == 0.0
    
    def test_percentile_with_single_value(self):
        """Test percentile calculation with single value."""
        response = self.calc_tool.percentile([42], 75)
        
        assert response.success is True
        assert response.data == 42.0
    
    def test_percentile_with_invalid_percentile(self):
        """Test percentile calculation with invalid percentile values."""
        values = [1, 2, 3, 4, 5]
        
        # Test negative percentile
        response = self.calc_tool.percentile(values, -10)
        assert response.success is False
        assert "Percentile must be between 0 and 100" in response.error
        
        # Test percentile > 100
        response = self.calc_tool.percentile(values, 150)
        assert response.success is False
        assert "Percentile must be between 0 and 100" in response.error
    
    def test_percentile_with_duplicate_values(self):
        """Test percentile calculation with duplicate values."""
        values = [5, 5, 5, 5, 5]
        
        response = self.calc_tool.percentile(values, 50)
        assert response.success is True
        assert response.data == 5.0
        
        response = self.calc_tool.percentile(values, 90)
        assert response.success is True
        assert response.data == 5.0
    
    def test_group_by_iso_week_with_timestamps(self):
        """Test grouping data by ISO week."""
        data = [
            {
                "id": 1,
                "timestamp": "2024-01-01T12:00:00+00:00",  # 2024-W01
                "value": "first"
            },
            {
                "id": 2,
                "timestamp": "2024-01-03T14:30:00+00:00",  # 2024-W01
                "value": "second"
            },
            {
                "id": 3,
                "timestamp": "2024-01-08T09:15:00+00:00",  # 2024-W02
                "value": "third"
            },
            {
                "id": 4,
                "timestamp": "2024-01-15T16:45:00+00:00",  # 2024-W03
                "value": "fourth"
            }
        ]
        
        response = self.calc_tool.group_by_iso_week(data)
        
        assert response.success is True
        assert "2024-W01" in response.data
        assert "2024-W02" in response.data
        assert "2024-W03" in response.data
        
        # Check that items are grouped correctly
        assert len(response.data["2024-W01"]) == 2
        assert len(response.data["2024-W02"]) == 1
        assert len(response.data["2024-W03"]) == 1
        
        # Verify the data is preserved
        week1_ids = [item["id"] for item in response.data["2024-W01"]]
        assert 1 in week1_ids
        assert 2 in week1_ids
    
    def test_group_by_iso_week_with_custom_field(self):
        """Test grouping by ISO week with custom timestamp field."""
        data = [
            {
                "id": 1,
                "created_at": "2024-01-01T12:00:00+00:00",
                "value": "first"
            },
            {
                "id": 2,
                "created_at": "2024-01-08T14:30:00+00:00",
                "value": "second"
            }
        ]
        
        response = self.calc_tool.group_by_iso_week(data, timestamp_field="created_at")
        
        assert response.success is True
        assert "2024-W01" in response.data
        assert "2024-W02" in response.data
        assert len(response.data["2024-W01"]) == 1
        assert len(response.data["2024-W02"]) == 1
    
    def test_group_by_iso_week_with_z_timezone(self):
        """Test grouping by ISO week with Z timezone format."""
        data = [
            {
                "id": 1,
                "timestamp": "2024-01-01T12:00:00Z",  # Z format
                "value": "first"
            }
        ]
        
        response = self.calc_tool.group_by_iso_week(data)
        
        assert response.success is True
        assert "2024-W01" in response.data
        assert len(response.data["2024-W01"]) == 1
    
    def test_group_by_iso_week_with_missing_field(self):
        """Test grouping by ISO week with missing timestamp field."""
        data = [
            {
                "id": 1,
                "value": "first"
                # Missing timestamp field
            },
            {
                "id": 2,
                "timestamp": "2024-01-01T12:00:00+00:00",
                "value": "second"
            }
        ]
        
        response = self.calc_tool.group_by_iso_week(data)
        
        assert response.success is True
        # Should only process items with timestamp field
        assert "2024-W01" in response.data
        assert len(response.data["2024-W01"]) == 1
        assert response.data["2024-W01"][0]["id"] == 2
    
    def test_group_by_iso_week_empty_data(self):
        """Test grouping by ISO week with empty data."""
        response = self.calc_tool.group_by_iso_week([])
        
        assert response.success is True
        assert response.data == {}
    
    def test_group_by_iso_week_with_datetime_objects(self):
        """Test grouping by ISO week with datetime objects instead of strings."""
        data = [
            {
                "id": 1,
                "timestamp": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                "value": "first"
            }
        ]
        
        response = self.calc_tool.group_by_iso_week(data)
        
        assert response.success is True
        assert "2024-W01" in response.data
        assert len(response.data["2024-W01"]) == 1
    
    def test_group_by_iso_week_sorted_output(self):
        """Test that ISO week grouping returns sorted weeks."""
        data = [
            {"timestamp": "2024-01-15T12:00:00+00:00", "id": 3},  # W03
            {"timestamp": "2024-01-01T12:00:00+00:00", "id": 1},  # W01
            {"timestamp": "2024-01-08T12:00:00+00:00", "id": 2},  # W02
        ]
        
        response = self.calc_tool.group_by_iso_week(data)
        
        assert response.success is True
        weeks = list(response.data.keys())
        assert weeks == ["2024-W01", "2024-W02", "2024-W03"]  # Should be sorted
    
    def test_topk_counts_basic(self):
        """Test basic top-k counting functionality."""
        items = ["apple", "banana", "apple", "cherry", "banana", "apple", "date"]
        
        response = self.calc_tool.topk_counts(items, k=3)
        
        assert response.success is True
        assert len(response.data) == 3
        
        # Should be sorted by count (descending)
        assert response.data[0]["item"] == "apple"
        assert response.data[0]["count"] == 3
        assert response.data[1]["item"] == "banana"
        assert response.data[1]["count"] == 2
        assert response.data[2]["item"] in ["cherry", "date"]
        assert response.data[2]["count"] == 1
    
    def test_topk_counts_with_k_larger_than_unique_items(self):
        """Test top-k counting when k is larger than unique items."""
        items = ["apple", "banana", "apple"]
        
        response = self.calc_tool.topk_counts(items, k=10)
        
        assert response.success is True
        assert len(response.data) == 2  # Only 2 unique items
        assert response.data[0]["item"] == "apple"
        assert response.data[0]["count"] == 2
        assert response.data[1]["item"] == "banana"
        assert response.data[1]["count"] == 1
    
    def test_topk_counts_with_empty_list(self):
        """Test top-k counting with empty list."""
        response = self.calc_tool.topk_counts([], k=5)
        
        assert response.success is True
        assert response.data == []
    
    def test_topk_counts_with_single_item(self):
        """Test top-k counting with single item."""
        response = self.calc_tool.topk_counts(["apple"], k=5)
        
        assert response.success is True
        assert len(response.data) == 1
        assert response.data[0]["item"] == "apple"
        assert response.data[0]["count"] == 1
    
    def test_topk_counts_with_k_zero(self):
        """Test top-k counting with k=0."""
        items = ["apple", "banana", "cherry"]
        
        response = self.calc_tool.topk_counts(items, k=0)
        
        assert response.success is False
        assert "k must be greater than 0" in response.error
    
    def test_topk_counts_with_negative_k(self):
        """Test top-k counting with negative k."""
        items = ["apple", "banana", "cherry"]
        
        response = self.calc_tool.topk_counts(items, k=-5)
        
        assert response.success is False
        assert "k must be greater than 0" in response.error
    
    def test_topk_counts_default_k(self):
        """Test top-k counting with default k value."""
        # Create 15 unique items
        items = [f"item_{i}" for i in range(15)] * 2  # Each appears twice
        
        response = self.calc_tool.topk_counts(items)  # Default k=10
        
        assert response.success is True
        assert len(response.data) == 10  # Should return top 10
        # All should have count of 2
        assert all(item["count"] == 2 for item in response.data)
    
    def test_topk_counts_deterministic_ordering(self):
        """Test that top-k counting has deterministic ordering for ties."""
        # Create items with same count to test tie-breaking
        items = ["zebra", "apple", "banana"] * 2  # Each appears twice
        
        response1 = self.calc_tool.topk_counts(items, k=3)
        response2 = self.calc_tool.topk_counts(items, k=3)
        
        assert response1.success is True
        assert response2.success is True
        
        # Results should be identical (deterministic)
        assert response1.data == response2.data
        
        # All items should have count of 2
        assert all(item["count"] == 2 for item in response1.data)
    
    def test_topk_counts_with_numeric_strings(self):
        """Test top-k counting with numeric strings."""
        items = ["1", "2", "1", "3", "2", "1"]
        
        response = self.calc_tool.topk_counts(items, k=3)
        
        assert response.success is True
        assert response.data[0]["item"] == "1"
        assert response.data[0]["count"] == 3
        assert response.data[1]["item"] == "2"
        assert response.data[1]["count"] == 2
        assert response.data[2]["item"] == "3"
        assert response.data[2]["count"] == 1


class TestCalcToolIntegration:
    """Integration tests for CalcTool with realistic scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.calc_tool = CalcTool()
    
    def test_complete_metrics_calculation_workflow(self):
        """Test a complete metrics calculation workflow."""
        # Simulate realistic merge commit data
        merge_commits = [
            {
                "hash": "abc123",
                "timestamp": "2024-01-01T10:00:00+00:00",
                "parents": ["def456", "ghi789"],
                "message": "Merge pull request #1: Add user authentication"
            },
            {
                "hash": "xyz789",
                "timestamp": "2024-01-03T14:30:00+00:00",
                "parents": ["jkl012", "mno345"],
                "message": "Merge pull request #2: Fix database connection"
            },
            {
                "hash": "pqr456",
                "timestamp": "2024-01-08T09:15:00+00:00",
                "parents": ["stu901", "vwx234"],
                "message": "Merge pull request #3: Update documentation"
            }
        ]
        
        # Test lead time calculation
        lead_time_response = self.calc_tool.lead_time(merge_commits)
        assert lead_time_response.success is True
        assert lead_time_response.data["count"] == 3
        
        # Test grouping by ISO week
        week_response = self.calc_tool.group_by_iso_week(merge_commits)
        assert week_response.success is True
        assert "2024-W01" in week_response.data
        assert "2024-W02" in week_response.data
        
        # Simulate file change data
        file_changes = [
            "src/auth.py", "src/auth.py", "src/auth.py",  # 3 changes
            "src/db.py", "src/db.py",                     # 2 changes
            "README.md", "tests/test_auth.py"             # 1 change each
        ]
        
        # Test top-k file counting
        topk_response = self.calc_tool.topk_counts(file_changes, k=3)
        assert topk_response.success is True
        assert len(topk_response.data) == 3
        assert topk_response.data[0]["item"] == "src/auth.py"
        assert topk_response.data[0]["count"] == 3
        
        # Test percentile calculations on change sizes
        change_sizes = [10, 25, 15, 30, 5, 40, 20, 35, 12, 28]
        
        p50_response = self.calc_tool.percentile(change_sizes, 50)
        assert p50_response.success is True
        
        p75_response = self.calc_tool.percentile(change_sizes, 75)
        assert p75_response.success is True
        
        # P75 should be greater than P50
        assert p75_response.data > p50_response.data
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery in various scenarios."""
        # Test with malformed data that should be handled gracefully
        malformed_commits = [
            {"hash": "abc123"},  # Missing required fields
            {"timestamp": "invalid-date", "parents": ["def456", "ghi789"]},
            None,  # Null entry
        ]
        
        # Should handle errors gracefully
        response = self.calc_tool.lead_time(malformed_commits)
        assert response.success is False
        
        # Test with mixed valid/invalid data for grouping
        mixed_data = [
            {"timestamp": "2024-01-01T12:00:00+00:00", "id": 1},  # Valid
            {"id": 2},  # Missing timestamp
            {"timestamp": "invalid", "id": 3},  # Invalid timestamp
        ]
        
        # Should process valid entries and skip invalid ones
        response = self.calc_tool.group_by_iso_week(mixed_data)
        assert response.success is True
        # Should have processed the one valid entry
        assert len(response.data) > 0
    
    def test_deterministic_behavior(self):
        """Test that calculations are deterministic with identical inputs."""
        data = [
            {"timestamp": "2024-01-01T12:00:00+00:00", "value": 10},
            {"timestamp": "2024-01-02T12:00:00+00:00", "value": 20},
            {"timestamp": "2024-01-03T12:00:00+00:00", "value": 15},
        ]
        
        # Run the same operations multiple times
        results1 = []
        results2 = []
        
        for _ in range(3):
            response1 = self.calc_tool.group_by_iso_week(data)
            response2 = self.calc_tool.group_by_iso_week(data)
            
            results1.append(response1.data)
            results2.append(response2.data)
        
        # All results should be identical
        assert all(result == results1[0] for result in results1)
        assert all(result == results2[0] for result in results2)
        assert results1 == results2
        
        # Test percentile determinism
        values = [1, 5, 3, 9, 2, 8, 4, 7, 6]
        
        p50_results = []
        for _ in range(5):
            response = self.calc_tool.percentile(values, 50)
            p50_results.append(response.data)
        
        # All percentile calculations should be identical
        assert all(result == p50_results[0] for result in p50_results)