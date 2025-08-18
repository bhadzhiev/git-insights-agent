"""Caching tool for JSON read/write operations and cache management."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..types import ToolResponse


class CacheTool:
    """Tool for managing JSON cache files and repository cache directories."""
    
    def __init__(self, cache_dir: Path):
        """Initialize CacheTool with cache directory.
        
        Args:
            cache_dir: Base directory for cache storage
        """
        self.cache_dir = Path(cache_dir)
    
    def read_json(self, cache_key: str) -> ToolResponse:
        """Read JSON data from cache file.
        
        Args:
            cache_key: Key identifying the cache file (will be used as filename)
            
        Returns:
            ToolResponse with cached data or error if file doesn't exist
        """
        try:
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            if not cache_file.exists():
                return ToolResponse.error_response(f"Cache file not found: {cache_key}")
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return ToolResponse.success_response(data)
            
        except json.JSONDecodeError as e:
            return ToolResponse.error_response(f"Invalid JSON in cache file {cache_key}: {str(e)}")
        except Exception as e:
            return ToolResponse.error_response(f"Error reading cache file {cache_key}: {str(e)}")
    
    def write_json(self, cache_key: str, data: Any) -> ToolResponse:
        """Write JSON data to cache file.
        
        Args:
            cache_key: Key identifying the cache file (will be used as filename)
            data: Data to cache (must be JSON serializable)
            
        Returns:
            ToolResponse indicating success or failure
        """
        try:
            # Ensure cache directory exists
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            cache_file = self.cache_dir / f"{cache_key}.json"
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
            
            return ToolResponse.success_response({
                "message": f"Successfully cached data to {cache_key}",
                "file_path": str(cache_file),
                "size_bytes": cache_file.stat().st_size
            })
            
        except TypeError as e:
            return ToolResponse.error_response(f"Data not JSON serializable for {cache_key}: {str(e)}")
        except Exception as e:
            return ToolResponse.error_response(f"Error writing cache file {cache_key}: {str(e)}")
    
    def get_repo_cache_path(self, repository_url: str) -> ToolResponse:
        """Get the cache directory path for a specific repository.
        
        Args:
            repository_url: URL of the repository
            
        Returns:
            ToolResponse with the repository cache path
        """
        try:
            # Extract repository name from URL
            repo_name = self._extract_repo_name(repository_url)
            repo_cache_path = self.cache_dir / repo_name
            
            return ToolResponse.success_response({
                "repository_url": repository_url,
                "repository_name": repo_name,
                "cache_path": str(repo_cache_path),
                "exists": repo_cache_path.exists()
            })
            
        except Exception as e:
            return ToolResponse.error_response(f"Error determining cache path for {repository_url}: {str(e)}")
    
    def ensure_cache_dir(self) -> ToolResponse:
        """Ensure the cache directory exists.
        
        Returns:
            ToolResponse indicating success or failure
        """
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            
            return ToolResponse.success_response({
                "message": "Cache directory ready",
                "cache_dir": str(self.cache_dir),
                "exists": self.cache_dir.exists(),
                "is_dir": self.cache_dir.is_dir()
            })
            
        except Exception as e:
            return ToolResponse.error_response(f"Error creating cache directory: {str(e)}")
    
    def list_cached_files(self, pattern: str = "*.json") -> ToolResponse:
        """List cached files matching a pattern.
        
        Args:
            pattern: Glob pattern to match files (default: "*.json")
            
        Returns:
            ToolResponse with list of cached files
        """
        try:
            if not self.cache_dir.exists():
                return ToolResponse.success_response([])
            
            cached_files = []
            for file_path in self.cache_dir.glob(pattern):
                if file_path.is_file():
                    cached_files.append({
                        "name": file_path.name,
                        "path": str(file_path),
                        "size_bytes": file_path.stat().st_size,
                        "modified": file_path.stat().st_mtime
                    })
            
            # Sort by modification time (newest first)
            cached_files.sort(key=lambda x: x["modified"], reverse=True)
            
            return ToolResponse.success_response(cached_files)
            
        except Exception as e:
            return ToolResponse.error_response(f"Error listing cached files: {str(e)}")
    
    def clear_cache(self, cache_key: Optional[str] = None) -> ToolResponse:
        """Clear cache files.
        
        Args:
            cache_key: Specific cache key to clear, or None to clear all JSON files
            
        Returns:
            ToolResponse indicating success or failure
        """
        try:
            if not self.cache_dir.exists():
                return ToolResponse.success_response({
                    "message": "Cache directory does not exist",
                    "files_removed": 0,
                    "cache_key": cache_key
                })
            
            files_removed = 0
            
            if cache_key:
                # Clear specific cache file
                cache_file = self.cache_dir / f"{cache_key}.json"
                if cache_file.exists():
                    cache_file.unlink()
                    files_removed = 1
            else:
                # Clear all JSON cache files
                for cache_file in self.cache_dir.glob("*.json"):
                    if cache_file.is_file():
                        cache_file.unlink()
                        files_removed += 1
            
            return ToolResponse.success_response({
                "message": f"Cleared {files_removed} cache file(s)",
                "files_removed": files_removed,
                "cache_key": cache_key
            })
            
        except Exception as e:
            return ToolResponse.error_response(f"Error clearing cache: {str(e)}")
    
    def _extract_repo_name(self, repository_url: str) -> str:
        """Extract repository name from URL for use as cache directory name.
        
        Args:
            repository_url: Repository URL
            
        Returns:
            Sanitized repository name suitable for use as directory name
        """
        # Handle various URL formats
        url = repository_url.strip()
        
        # Remove protocol
        if url.startswith(('http://', 'https://')):
            url = url.split('://', 1)[1]
        elif url.startswith('git@'):
            url = url.replace('git@', '').replace(':', '/')
        
        # Remove .git suffix
        if url.endswith('.git'):
            url = url[:-4]
        
        # Extract the last two parts (org/repo)
        parts = url.split('/')
        if len(parts) >= 2 and parts[-1] and parts[-2]:
            repo_name = f"{parts[-2]}_{parts[-1]}"
        elif len(parts) >= 1 and parts[-1]:
            repo_name = parts[-1]
        else:
            repo_name = "unknown_repo"
        
        # Sanitize for filesystem
        repo_name = repo_name.replace('/', '_').replace('\\', '_')
        repo_name = ''.join(c for c in repo_name if c.isalnum() or c in '-_.')
        
        return repo_name or "unknown_repo"