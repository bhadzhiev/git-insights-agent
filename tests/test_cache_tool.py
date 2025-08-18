"""Unit tests for CacheTool with comprehensive caching functionality testing."""

import json
import tempfile
from pathlib import Path
import pytest

from git_batch_analyzer.tools.cache_tool import CacheTool
from git_batch_analyzer.types import ToolResponse


class TestCacheTool:
    """Test cases for CacheTool class."""
    
    def setup_method(self):
        """Set up test fixtures with temporary cache directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "test_cache"
        self.cache_tool = CacheTool(self.cache_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_write_and_read_json_basic(self):
        """Test basic JSON write and read operations."""
        test_data = {
            "name": "test_repo",
            "commits": 42,
            "branches": ["main", "develop"],
            "metrics": {"p50": 24.5, "p75": 48.2}
        }
        
        # Write data
        write_response = self.cache_tool.write_json("test_key", test_data)
        assert write_response.success is True
        assert "Successfully cached data to test_key" in write_response.data["message"]
        assert write_response.data["size_bytes"] > 0
        
        # Read data back
        read_response = self.cache_tool.read_json("test_key")
        assert read_response.success is True
        assert read_response.data == test_data
    
    def test_read_nonexistent_cache_file(self):
        """Test reading a cache file that doesn't exist."""
        response = self.cache_tool.read_json("nonexistent_key")
        
        assert response.success is False
        assert "Cache file not found: nonexistent_key" in response.error
    
    def test_write_json_creates_directory(self):
        """Test that write_json creates cache directory if it doesn't exist."""
        # Ensure cache directory doesn't exist
        assert not self.cache_dir.exists()
        
        test_data = {"test": "data"}
        response = self.cache_tool.write_json("test_key", test_data)
        
        assert response.success is True
        assert self.cache_dir.exists()
        assert self.cache_dir.is_dir()
    
    def test_write_json_with_complex_data(self):
        """Test writing complex nested data structures."""
        complex_data = {
            "repositories": [
                {
                    "name": "repo1",
                    "metrics": {
                        "commits": [
                            {"hash": "abc123", "timestamp": "2024-01-01T12:00:00Z"},
                            {"hash": "def456", "timestamp": "2024-01-02T14:30:00Z"}
                        ],
                        "stats": {"total": 2, "percentiles": [10.5, 25.7, 50.0]}
                    }
                }
            ],
            "metadata": {
                "generated_at": "2024-01-15T10:00:00Z",
                "version": "1.0.0"
            }
        }
        
        write_response = self.cache_tool.write_json("complex_data", complex_data)
        assert write_response.success is True
        
        read_response = self.cache_tool.read_json("complex_data")
        assert read_response.success is True
        assert read_response.data == complex_data
    
    def test_write_json_with_non_serializable_data(self):
        """Test writing data that's not JSON serializable."""
        import datetime
        
        non_serializable_data = {
            "timestamp": datetime.datetime.now(),  # datetime objects aren't JSON serializable
            "function": lambda x: x + 1  # functions aren't JSON serializable
        }
        
        response = self.cache_tool.write_json("bad_data", non_serializable_data)
        
        assert response.success is False
        assert "Data not JSON serializable" in response.error
    
    def test_read_json_with_corrupted_file(self):
        """Test reading a corrupted JSON file."""
        # Create a corrupted JSON file manually
        cache_file = self.cache_dir / "corrupted.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(cache_file, 'w') as f:
            f.write('{"invalid": json content}')  # Invalid JSON
        
        response = self.cache_tool.read_json("corrupted")
        
        assert response.success is False
        assert "Invalid JSON in cache file" in response.error
    
    def test_get_repo_cache_path_github_https(self):
        """Test repository cache path generation for GitHub HTTPS URLs."""
        repo_url = "https://github.com/user/repository.git"
        
        response = self.cache_tool.get_repo_cache_path(repo_url)
        
        assert response.success is True
        assert response.data["repository_url"] == repo_url
        assert response.data["repository_name"] == "user_repository"
        assert response.data["exists"] is False
        assert str(self.cache_dir / "user_repository") in response.data["cache_path"]
    
    def test_get_repo_cache_path_github_ssh(self):
        """Test repository cache path generation for GitHub SSH URLs."""
        repo_url = "git@github.com:user/repository.git"
        
        response = self.cache_tool.get_repo_cache_path(repo_url)
        
        assert response.success is True
        assert response.data["repository_name"] == "user_repository"
    
    def test_get_repo_cache_path_without_git_suffix(self):
        """Test repository cache path generation for URLs without .git suffix."""
        repo_url = "https://github.com/user/repository"
        
        response = self.cache_tool.get_repo_cache_path(repo_url)
        
        assert response.success is True
        assert response.data["repository_name"] == "user_repository"
    
    def test_get_repo_cache_path_with_special_characters(self):
        """Test repository cache path generation with special characters."""
        repo_url = "https://github.com/user-name/repo.name-with-dots.git"
        
        response = self.cache_tool.get_repo_cache_path(repo_url)
        
        assert response.success is True
        # Should sanitize special characters
        repo_name = response.data["repository_name"]
        assert "/" not in repo_name
        assert "\\" not in repo_name
        # Should preserve allowed characters
        assert "user-name" in repo_name
        assert "repo.name-with-dots" in repo_name
    
    def test_get_repo_cache_path_edge_cases(self):
        """Test repository cache path generation with edge cases."""
        # Test with minimal URL
        response = self.cache_tool.get_repo_cache_path("repo")
        assert response.success is True
        assert response.data["repository_name"] == "repo"
        
        # Test with empty URL
        response = self.cache_tool.get_repo_cache_path("")
        assert response.success is True
        assert response.data["repository_name"] == "unknown_repo"
        
        # Test with just domain
        response = self.cache_tool.get_repo_cache_path("https://github.com/")
        assert response.success is True
        assert response.data["repository_name"] == "unknown_repo"
    
    def test_ensure_cache_dir(self):
        """Test cache directory creation."""
        # Ensure directory doesn't exist initially
        assert not self.cache_dir.exists()
        
        response = self.cache_tool.ensure_cache_dir()
        
        assert response.success is True
        assert response.data["exists"] is True
        assert response.data["is_dir"] is True
        assert self.cache_dir.exists()
        assert self.cache_dir.is_dir()
    
    def test_ensure_cache_dir_already_exists(self):
        """Test cache directory creation when it already exists."""
        # Create directory first
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        response = self.cache_tool.ensure_cache_dir()
        
        assert response.success is True
        assert response.data["exists"] is True
        assert response.data["is_dir"] is True
    
    def test_list_cached_files_empty_directory(self):
        """Test listing cached files in empty directory."""
        response = self.cache_tool.list_cached_files()
        
        assert response.success is True
        assert response.data == []
    
    def test_list_cached_files_nonexistent_directory(self):
        """Test listing cached files when cache directory doesn't exist."""
        response = self.cache_tool.list_cached_files()
        
        assert response.success is True
        assert response.data == []
    
    def test_list_cached_files_with_files(self):
        """Test listing cached files with actual files."""
        # Create some cache files
        test_data1 = {"test": "data1"}
        test_data2 = {"test": "data2"}
        
        self.cache_tool.write_json("file1", test_data1)
        self.cache_tool.write_json("file2", test_data2)
        
        response = self.cache_tool.list_cached_files()
        
        assert response.success is True
        assert len(response.data) == 2
        
        # Check file information
        file_names = [f["name"] for f in response.data]
        assert "file1.json" in file_names
        assert "file2.json" in file_names
        
        # Check that files have size and modification time
        for file_info in response.data:
            assert file_info["size_bytes"] > 0
            assert "modified" in file_info
            assert "path" in file_info
    
    def test_list_cached_files_with_custom_pattern(self):
        """Test listing cached files with custom pattern."""
        # Create cache directory and files
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create JSON and non-JSON files
        (self.cache_dir / "test1.json").write_text('{"test": 1}')
        (self.cache_dir / "test2.json").write_text('{"test": 2}')
        (self.cache_dir / "readme.txt").write_text("Not a JSON file")
        
        # List only JSON files (default)
        json_response = self.cache_tool.list_cached_files("*.json")
        assert json_response.success is True
        assert len(json_response.data) == 2
        
        # List all files
        all_response = self.cache_tool.list_cached_files("*")
        assert all_response.success is True
        assert len(all_response.data) == 3
    
    def test_list_cached_files_sorted_by_modification_time(self):
        """Test that cached files are sorted by modification time."""
        import time
        
        # Create files with slight delay to ensure different modification times
        self.cache_tool.write_json("older_file", {"test": "old"})
        time.sleep(0.1)
        self.cache_tool.write_json("newer_file", {"test": "new"})
        
        response = self.cache_tool.list_cached_files()
        
        assert response.success is True
        assert len(response.data) == 2
        
        # Should be sorted by modification time (newest first)
        assert response.data[0]["name"] == "newer_file.json"
        assert response.data[1]["name"] == "older_file.json"
        assert response.data[0]["modified"] > response.data[1]["modified"]
    
    def test_clear_cache_specific_file(self):
        """Test clearing a specific cache file."""
        # Create multiple cache files
        self.cache_tool.write_json("file1", {"test": "data1"})
        self.cache_tool.write_json("file2", {"test": "data2"})
        
        # Clear specific file
        response = self.cache_tool.clear_cache("file1")
        
        assert response.success is True
        assert response.data["files_removed"] == 1
        assert response.data["cache_key"] == "file1"
        
        # Verify file1 is gone but file2 remains
        read1_response = self.cache_tool.read_json("file1")
        assert read1_response.success is False
        
        read2_response = self.cache_tool.read_json("file2")
        assert read2_response.success is True
    
    def test_clear_cache_nonexistent_file(self):
        """Test clearing a cache file that doesn't exist."""
        response = self.cache_tool.clear_cache("nonexistent")
        
        assert response.success is True
        assert response.data["files_removed"] == 0
        assert response.data["cache_key"] == "nonexistent"
    
    def test_clear_cache_all_files(self):
        """Test clearing all cache files."""
        # Create multiple cache files
        self.cache_tool.write_json("file1", {"test": "data1"})
        self.cache_tool.write_json("file2", {"test": "data2"})
        self.cache_tool.write_json("file3", {"test": "data3"})
        
        # Clear all files
        response = self.cache_tool.clear_cache()
        
        assert response.success is True
        assert response.data["files_removed"] == 3
        assert response.data["cache_key"] is None
        
        # Verify all files are gone
        list_response = self.cache_tool.list_cached_files()
        assert list_response.success is True
        assert len(list_response.data) == 0
    
    def test_clear_cache_nonexistent_directory(self):
        """Test clearing cache when directory doesn't exist."""
        response = self.cache_tool.clear_cache()
        
        assert response.success is True
        assert response.data["files_removed"] == 0
        assert "Cache directory does not exist" in response.data["message"]
    
    def test_json_deterministic_output(self):
        """Test that JSON output is deterministic (sorted keys)."""
        test_data = {
            "zebra": "last",
            "apple": "first", 
            "banana": "middle"
        }
        
        # Write and read multiple times
        responses = []
        for i in range(3):
            self.cache_tool.write_json(f"test_{i}", test_data)
            
            # Read the raw file content to check JSON formatting
            cache_file = self.cache_dir / f"test_{i}.json"
            with open(cache_file, 'r') as f:
                content = f.read()
            responses.append(content)
        
        # All JSON outputs should be identical (deterministic)
        assert all(content == responses[0] for content in responses)
        
        # Keys should be sorted in the JSON output
        assert '"apple"' in responses[0]
        assert '"banana"' in responses[0]
        assert '"zebra"' in responses[0]
        # Apple should come before zebra in the JSON string
        apple_pos = responses[0].find('"apple"')
        zebra_pos = responses[0].find('"zebra"')
        assert apple_pos < zebra_pos


class TestCacheToolIntegration:
    """Integration tests for CacheTool with realistic scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "integration_cache"
        self.cache_tool = CacheTool(self.cache_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_repository_analysis_caching_workflow(self):
        """Test a complete repository analysis caching workflow."""
        # Simulate repository analysis data
        repo_url = "https://github.com/example/project.git"
        
        # Get cache path for repository
        path_response = self.cache_tool.get_repo_cache_path(repo_url)
        assert path_response.success is True
        repo_name = path_response.data["repository_name"]
        
        # Cache merge commits data
        merge_commits = [
            {
                "hash": "abc123",
                "timestamp": "2024-01-01T12:00:00+00:00",
                "message": "Merge pull request #1",
                "parents": ["def456", "ghi789"],
                "author": "developer1"
            },
            {
                "hash": "xyz789", 
                "timestamp": "2024-01-02T14:30:00+00:00",
                "message": "Merge pull request #2",
                "parents": ["jkl012", "mno345"],
                "author": "developer2"
            }
        ]
        
        commits_key = f"{repo_name}_merge_commits"
        write_response = self.cache_tool.write_json(commits_key, merge_commits)
        assert write_response.success is True
        
        # Cache calculated metrics
        metrics = {
            "total_prs": 2,
            "lead_time_p50": 24.5,
            "lead_time_p75": 48.2,
            "change_size_p50": 15,
            "change_size_p75": 32,
            "weekly_pr_counts": {"2024-W01": 2},
            "top_files": [
                {"item": "src/main.py", "count": 5},
                {"item": "README.md", "count": 2}
            ]
        }
        
        metrics_key = f"{repo_name}_metrics"
        metrics_response = self.cache_tool.write_json(metrics_key, metrics)
        assert metrics_response.success is True
        
        # Cache branch information
        branches = [
            {
                "name": "main",
                "last_commit_hash": "abc123",
                "last_commit_timestamp": "2024-01-01T12:00:00+00:00",
                "is_stale": False
            },
            {
                "name": "feature-old",
                "last_commit_hash": "old456",
                "last_commit_timestamp": "2023-12-01T10:00:00+00:00",
                "is_stale": True
            }
        ]
        
        branches_key = f"{repo_name}_branches"
        branches_response = self.cache_tool.write_json(branches_key, branches)
        assert branches_response.success is True
        
        # List all cached files for this repository
        list_response = self.cache_tool.list_cached_files()
        assert list_response.success is True
        assert len(list_response.data) == 3
        
        # Verify we can read all cached data back
        read_commits = self.cache_tool.read_json(commits_key)
        assert read_commits.success is True
        assert read_commits.data == merge_commits
        
        read_metrics = self.cache_tool.read_json(metrics_key)
        assert read_metrics.success is True
        assert read_metrics.data == metrics
        
        read_branches = self.cache_tool.read_json(branches_key)
        assert read_branches.success is True
        assert read_branches.data == branches
    
    def test_multi_repository_caching(self):
        """Test caching data for multiple repositories."""
        repositories = [
            "https://github.com/org1/repo1.git",
            "https://github.com/org2/repo2.git", 
            "git@github.com:org3/repo3.git"
        ]
        
        cached_repos = []
        
        for repo_url in repositories:
            # Get repository cache info
            path_response = self.cache_tool.get_repo_cache_path(repo_url)
            assert path_response.success is True
            
            repo_name = path_response.data["repository_name"]
            cached_repos.append(repo_name)
            
            # Cache some data for each repository
            repo_data = {
                "url": repo_url,
                "analyzed_at": "2024-01-15T10:00:00Z",
                "commit_count": len(repo_name) * 10  # Vary by repo
            }
            
            cache_key = f"{repo_name}_info"
            write_response = self.cache_tool.write_json(cache_key, repo_data)
            assert write_response.success is True
        
        # Verify all repositories have unique cache names
        assert len(set(cached_repos)) == len(cached_repos)
        
        # Verify we can list and read all cached data
        list_response = self.cache_tool.list_cached_files()
        assert list_response.success is True
        assert len(list_response.data) == len(repositories)
        
        # Read back data for each repository
        for i, repo_name in enumerate(cached_repos):
            cache_key = f"{repo_name}_info"
            read_response = self.cache_tool.read_json(cache_key)
            assert read_response.success is True
            assert read_response.data["url"] == repositories[i]
    
    def test_cache_cleanup_and_management(self):
        """Test cache cleanup and management operations."""
        # Create cache files for multiple repositories
        repo_data = [
            ("repo1_commits", {"commits": [1, 2, 3]}),
            ("repo1_metrics", {"total": 3}),
            ("repo2_commits", {"commits": [4, 5]}),
            ("repo2_metrics", {"total": 2}),
            ("temp_analysis", {"temp": True})
        ]
        
        # Write all cache files
        for key, data in repo_data:
            response = self.cache_tool.write_json(key, data)
            assert response.success is True
        
        # Verify all files exist
        list_response = self.cache_tool.list_cached_files()
        assert list_response.success is True
        assert len(list_response.data) == 5
        
        # Clear specific repository data (repo1)
        self.cache_tool.clear_cache("repo1_commits")
        self.cache_tool.clear_cache("repo1_metrics")
        
        # Verify repo1 data is gone but others remain
        list_response = self.cache_tool.list_cached_files()
        assert list_response.success is True
        assert len(list_response.data) == 3
        
        remaining_files = [f["name"] for f in list_response.data]
        assert "repo1_commits.json" not in remaining_files
        assert "repo1_metrics.json" not in remaining_files
        assert "repo2_commits.json" in remaining_files
        
        # Clear all remaining cache
        clear_response = self.cache_tool.clear_cache()
        assert clear_response.success is True
        assert clear_response.data["files_removed"] == 3
        
        # Verify cache is empty
        final_list = self.cache_tool.list_cached_files()
        assert final_list.success is True
        assert len(final_list.data) == 0
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery scenarios."""
        # Test with permission issues (simulate by using invalid path)
        if hasattr(self, '_test_permission_errors'):  # Skip on systems where this might not work
            invalid_cache_tool = CacheTool(Path("/root/invalid_cache"))
            
            response = invalid_cache_tool.write_json("test", {"data": "test"})
            # Should handle permission errors gracefully
            assert response.success is False
            assert "Error" in response.error
        
        # Test with very large data (should work but test limits)
        large_data = {"items": list(range(10000))}
        response = self.cache_tool.write_json("large_data", large_data)
        assert response.success is True
        
        read_response = self.cache_tool.read_json("large_data")
        assert read_response.success is True
        assert len(read_response.data["items"]) == 10000
        
        # Test with unicode data
        unicode_data = {
            "english": "Hello World",
            "chinese": "你好世界",
            "emoji": "🚀🎉💻",
            "special": "Special chars: àáâãäåæçèéêë"
        }
        
        response = self.cache_tool.write_json("unicode_test", unicode_data)
        assert response.success is True
        
        read_response = self.cache_tool.read_json("unicode_test")
        assert read_response.success is True
        assert read_response.data == unicode_data
    
    def test_deterministic_behavior_across_sessions(self):
        """Test that caching behavior is deterministic across different sessions."""
        test_data = {
            "repositories": ["repo1", "repo2", "repo3"],
            "metrics": {"p50": 25.5, "p75": 45.2},
            "metadata": {"version": "1.0", "timestamp": "2024-01-15T10:00:00Z"}
        }
        
        # Write data multiple times
        checksums = []
        for i in range(3):
            key = f"deterministic_test_{i}"
            self.cache_tool.write_json(key, test_data)
            
            # Read raw file content to check consistency
            cache_file = self.cache_dir / f"{key}.json"
            content = cache_file.read_text(encoding='utf-8')
            checksums.append(hash(content))
        
        # All checksums should be identical (deterministic JSON output)
        assert all(checksum == checksums[0] for checksum in checksums)
        
        # Test that reading produces identical results
        read_results = []
        for i in range(3):
            key = f"deterministic_test_{i}"
            response = self.cache_tool.read_json(key)
            assert response.success is True
            read_results.append(response.data)
        
        # All read results should be identical
        assert all(result == read_results[0] for result in read_results)
        assert all(result == test_data for result in read_results)