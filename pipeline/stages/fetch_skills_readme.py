#!/usr/bin/env python3
"""Fetch the awesome-hermes-skills README and save locally.

Pin to a specific commit SHA for reproducibility.
"""
import json, requests, sys
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

# Pin to a known commit (update this periodically, not on every run)
REPO = "ZeroPointRepo/awesome-hermes-skills"
# Use HEAD of main for now; pin after first successful run
COMMIT_SHA = None  # Will use default branch if None

@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10))
def fetch_readme(repo: str, commit_sha: str | None = None) -> str:
    if commit_sha:
        url = f"https://raw.githubusercontent.com/{repo}/{commit_sha}/README.md"
    else:
        url = f"https://raw.githubusercontent.com/{repo}/main/README.md"

    resp = requests.get(url, timeout=30)
    if resp.status_code == 404:
        # Try 'master' branch
        url = f"https://raw.githubusercontent.com/{repo}/master/README.md"
        resp = requests.get(url, timeout=30)

    resp.raise_for_status()
    return resp.text

def main():
    output_path = Path("pipeline/output/awesome-hermes-skills-readme.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Also try to get the latest commit SHA for pinning
    try:
        api_resp = requests.get(
            f"https://api.github.com/repos/{REPO}/commits/main",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )
        if api_resp.ok:
            sha = api_resp.json()["sha"][:12]
            meta_path = Path("pipeline/output/skills-readme-commit.txt")
            meta_path.write_text(sha)
            print(f"Pinned to commit: {sha}")
    except Exception:
        pass

    content = fetch_readme(REPO, COMMIT_SHA)
    output_path.write_text(content)
    print(f"Fetched README ({len(content)} chars) -> {output_path}")

if __name__ == "__main__":
    main()
