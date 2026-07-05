#!/usr/bin/env python3
"""Fetch docs content.

The public docs site can serve Vercel Security Checkpoint HTML to automated
fetchers. Try the public page first, then fall back to the source markdown in
the Hermes Agent GitHub repo.
"""
import json
import sys
import time
from pathlib import Path

import requests
import trafilatura
from tenacity import retry, stop_after_attempt, wait_exponential_jitter


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10))
def fetch_page(url: str) -> str | None:
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        extracted = trafilatura.extract(
            downloaded,
            include_tables=True,
            favor_recall=True,
            output_format="markdown",
        )
        if extracted and len(extracted.strip()) > 100:
            return extracted

    return fetch_github_markdown(url)


def fetch_github_markdown(public_url: str) -> str | None:
    slug = public_url.removeprefix("https://hermes-agent.nousresearch.com/docs/").strip("/")
    candidates = ["website/docs/index.mdx"] if not slug else [
        f"website/docs/{slug}.md",
        f"website/docs/{slug}.mdx",
        f"website/docs/{slug}/index.md",
        f"website/docs/{slug}/index.mdx",
    ]

    for path in candidates:
        raw_url = f"https://raw.githubusercontent.com/NousResearch/hermes-agent/main/{path}"
        resp = requests.get(raw_url, timeout=30)
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        content = resp.text.strip()
        if len(content) > 100:
            return content
    return None


def main():
    input_path = Path("pipeline/output/urls.json")
    output_path = Path("pipeline/output/docs.jsonl")

    urls = json.loads(input_path.read_text())
    docs = []
    failed = []

    for url in urls:
        try:
            content = fetch_page(url)
            if content and len(content.strip()) > 100:  # skip near-empty pages
                docs.append({"url": url, "content": content})
                print(f"OK  {url} ({len(content)} chars)")
            else:
                print(f"SKIP {url} (empty or too short)", file=sys.stderr)
                failed.append(url)
        except Exception as e:
            print(f"FAIL {url}: {e}", file=sys.stderr)
            failed.append(url)
        time.sleep(0.5)  # polite crawling

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(json.dumps(d) for d in docs))

    if failed:
        Path("pipeline/output/failed-urls.json").write_text(json.dumps(failed, indent=2))

    print(f"\nFetched {len(docs)}/{len(urls)} pages -> {output_path}")
    if failed:
        print(f"Failed URLs logged to pipeline/output/failed-urls.json", file=sys.stderr)


if __name__ == "__main__":
    main()
