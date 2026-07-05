#!/usr/bin/env python3
"""Discover all Hermes docs URLs.

The public docs site can return Vercel Security Checkpoint HTML to non-browser
fetchers, so prefer the source-of-truth markdown files in the Hermes Agent repo
and map them back to public docs URLs for source attribution.
"""
import json
import sys
from pathlib import Path

import requests

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
        resp = requests.get(
            "https://api.github.com/repos/NousResearch/hermes-agent/git/trees/main?recursive=1",
            timeout=60,
        )
        resp.raise_for_status()
        github_urls = []
        for item in resp.json().get("tree", []):
            path = item.get("path", "")
            if not path.startswith("website/docs/") or not path.endswith((".md", ".mdx")):
                continue

            slug = path.removeprefix("website/docs/").rsplit(".", 1)[0]
            if slug == "index":
                public_url = "https://hermes-agent.nousresearch.com/docs/"
            elif slug.endswith("/index"):
                public_url = f"https://hermes-agent.nousresearch.com/docs/{slug.removesuffix('/index')}"
            else:
                public_url = f"https://hermes-agent.nousresearch.com/docs/{slug}"
            github_urls.append(public_url)

        if github_urls:
            urls = list(set(urls + github_urls))
    except Exception as e:
        print(f"Warning: GitHub docs discovery failed ({e}), trying sitemap", file=sys.stderr)

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
