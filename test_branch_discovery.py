#!/usr/bin/env python3

import subprocess
import sys

def test_ls_remote():
    """Test git ls-remote to see what branches are available"""
    repos = [
        "https://bhadzhiev@git.eu-west-1.codecatalyst.aws/v1/linkin/SAP/sap-integrations",
        "https://bhadzhiev@git.eu-west-1.codecatalyst.aws/v1/linkin/SAP/sap-cdk",
        "https://bhadzhiev@git.eu-west-1.codecatalyst.aws/v1/linkin/SAP/sap-admin",
        "https://bhadzhiev@git.eu-west-1.codecatalyst.aws/v1/linkin/DATA/sap-odata-collector",
        "https://bhadzhiev@git.eu-west-1.codecatalyst.aws/v1/linkin/DATA/airflow-dags",
        "https://bhadzhiev@git.eu-west-1.codecatalyst.aws/v1/linkin/DATA/ray-jobs"
    ]
    
    for repo_url in repos:
        print(f"\n=== Testing {repo_url} ===")
        
        # Test ls-remote
        try:
            result = subprocess.run(
                ["git", "ls-remote", "--heads", repo_url],
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            branches = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split('\t')
                    if len(parts) == 2 and parts[1].startswith('refs/heads/'):
                        branch_name = parts[1].replace('refs/heads/', '')
                        branches.append(branch_name)
            
            print(f"Found {len(branches)} branches:")
            for branch in sorted(branches):
                print(f"  - {branch}")
                
        except subprocess.CalledProcessError as e:
            print(f"Error: {e.stderr}")
        except subprocess.TimeoutExpired:
            print("Error: Command timed out")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_ls_remote()