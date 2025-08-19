#!/usr/bin/env python3

import subprocess
import os
from pathlib import Path

def check_git_repo():
    """Check what's in the git repository after our operations"""
    repo_path = Path("/Users/bozhidar/.cache/git-analyzer/sap-integrations")
    
    if not repo_path.exists():
        print("Repository does not exist")
        return
    
    print(f"=== Checking repository at {repo_path} ===")
    
    # Check current branch
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"Current branch: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to get current branch: {e.stderr}")
    
    # Check all branches (local and remote)
    try:
        result = subprocess.run(
            ["git", "branch", "-a"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        print("All branches:")
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                print(f"  {line}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to list branches: {e.stderr}")
    
    # Check remote branches specifically
    try:
        result = subprocess.run(
            ["git", "branch", "-r"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        print("Remote branches:")
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                print(f"  {line}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to list remote branches: {e.stderr}")
    
    # Check git log for current branch
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-n", "5"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        print("Recent commits (current branch):")
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                print(f"  {line}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to get log: {e.stderr}")

if __name__ == "__main__":
    check_git_repo()