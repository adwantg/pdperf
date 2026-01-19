#!/usr/bin/env python3
"""Fetch Codacy issues for a repository.

Author: gadwant

Usage:
    1. Copy .env.example to .env and fill in your API token
    2. Run: python scripts/fetch_codacy_issues.py
    
    Or set environment variables manually:
        export CODACY_API_TOKEN=your_token_here
        python scripts/fetch_codacy_issues.py
"""

import os
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def load_env_file():
    """Load environment variables from .env file if it exists."""
    # Look for .env in script directory or parent
    script_dir = Path(__file__).parent
    env_paths = [
        script_dir / ".env",
        script_dir.parent / ".env",
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            print(f"Loading config from: {env_path}")
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())
            return True
    return False


def get_env(name: str) -> str:
    """Get required environment variable."""
    value = os.environ.get(name)
    if not value:
        print(f"Error: Environment variable {name} is not set")
        sys.exit(1)
    return value


def fetch_issues(
    api_token: str,
    provider: str,
    username: str,
    project: str,
    limit: int = 100,
    cursor: str | None = None
) -> dict:
    """Fetch issues from Codacy API.
    
    API: POST /api/v3/analysis/organizations/{provider}/{username}/repositories/{repository}/issues/search
    """
    # Correct endpoint with /repositories/ in path
    url = f"https://app.codacy.com/api/v3/analysis/organizations/{provider}/{username}/repositories/{project}/issues/search"
    
    # Request body for filtering (empty = all issues)
    body = {}
    
    # Add pagination
    params = f"?limit={limit}"
    if cursor:
        params += f"&cursor={cursor}"
    
    full_url = url + params
    
    headers = {
        "api-token": api_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    request = Request(full_url, data=json.dumps(body).encode(), headers=headers, method="POST")
    
    try:
        # nosec B310 - URL is constructed from trusted config, always HTTPS
        with urlopen(request) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        error_body = e.read().decode() if e.fp else "No details"
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"Details: {error_body}")
        sys.exit(1)


def format_issue(issue: dict) -> str:
    """Format a single issue for display."""
    file_path = issue.get("filePath", "unknown")
    line = issue.get("lineNumber", "?")
    level = issue.get("level", "unknown")
    title = issue.get("patternInfo", {}).get("title", "No title")
    message = issue.get("message", "No message")
    
    level_icons = {
        "Error": "❌",
        "Warning": "⚠️",
        "Info": "ℹ️",
    }
    icon = level_icons.get(level, "•")
    
    return f"{icon} [{level}] {file_path}:{line}\n   {title}\n   {message}\n"


def main():
    # Load .env file if it exists
    load_env_file()
    
    # Load configuration from environment
    api_token = get_env("CODACY_API_TOKEN")
    provider = get_env("CODACY_ORGANIZATION_PROVIDER")
    username = get_env("CODACY_USERNAME")
    project = get_env("CODACY_PROJECT_NAME")
    
    print(f"Fetching issues for {provider}/{username}/{project}...")
    print("=" * 60)
    
    all_issues = []
    cursor = None
    page = 1
    
    while True:
        print(f"Fetching page {page}...")
        result = fetch_issues(api_token, provider, username, project, limit=100, cursor=cursor)
        
        issues = result.get("data", [])
        all_issues.extend(issues)
        
        # Check for more pages
        pagination = result.get("pagination", {})
        cursor = pagination.get("cursor")
        
        if not cursor or not issues:
            break
        
        page += 1
    
    print(f"\nTotal issues found: {len(all_issues)}")
    print("=" * 60)
    
    if not all_issues:
        print("🎉 No issues found! Your code is clean.")
        return
    
    # Group by level
    errors = [i for i in all_issues if i.get("level") == "Error"]
    warnings = [i for i in all_issues if i.get("level") == "Warning"]
    infos = [i for i in all_issues if i.get("level") == "Info"]
    
    print(f"\n❌ Errors: {len(errors)}")
    print(f"⚠️  Warnings: {len(warnings)}")
    print(f"ℹ️  Info: {len(infos)}")
    print()
    
    # Print all issues
    for issue in all_issues:
        print(format_issue(issue))
    
    # Save to JSON for further processing
    output_file = "codacy_issues.json"
    with open(output_file, "w") as f:
        json.dump({"total": len(all_issues), "issues": all_issues}, f, indent=2)
    print(f"\nSaved all issues to: {output_file}")


if __name__ == "__main__":
    main()
