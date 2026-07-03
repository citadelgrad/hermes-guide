#!/usr/bin/env python3
"""Fetch URLs and extract markdown content via trafilatura."""
import json
import sys
import time
from pathlib import Path

import trafilatura
from tenacity import retry, stop_after_attempt, wait_exponential_jitter


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=1, max=10))
def fetch_page(url: str) -> str | None:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    return trafilatura.extract(
        downloaded,
        include_tables=True,
        favor_recall=True,
        output_format="markdown",
    )


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
