#!/usr/bin/env python3
"""Discover all Hermes docs URLs via sitemap + priority hardcoded list."""
import json
import sys
from pathlib import Path

# Priority pages always included even if missing from sitemap
PRIORITY_URLS = [
    "https://hermes-agent.nousresearch.com/docs/guides/tips/",
    "https://hermes-agent.nousresearch.com/docs/getting-started/learning-path",
    "https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills",
    "https://hermes-agent.nousresearch.com/docs/user-guide/features/skills",
    "https://hermes-agent.nousresearch.com/docs/getting-started/quickstart",
    "https://hermes-agent.nousresearch.com/docs/",
]


def discover_urls() -> list[str]:
    urls = list(PRIORITY_URLS)

    try:
        from usp.tree import sitemap_tree_for_homepage
        tree = sitemap_tree_for_homepage("https://hermes-agent.nousresearch.com")
        sitemap_urls = [page.url for page in tree.all_pages()
                        if "/docs" in page.url]
        urls = list(set(urls + sitemap_urls))
    except Exception as e:
        print(f"Warning: sitemap crawl failed ({e}), using priority URLs only", file=sys.stderr)

    return [u for u in urls if u.startswith("https://")]


if __name__ == "__main__":
    output_path = Path("pipeline/output/urls.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    urls = discover_urls()
    output_path.write_text(json.dumps(urls, indent=2))
    print(f"Discovered {len(urls)} URLs -> {output_path}")
