#!/usr/bin/env python3
"""Ingest fetched docs into LightRAG via the hermes-guide backend API."""
import json
import os
import sys
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

BACKEND_URL = os.environ.get("HERMES_GUIDE_URL", "http://127.0.0.1:7842")
ADMIN_TOKEN = os.environ["HERMES_GUIDE_ADMIN_TOKEN"]
INGEST_DELAY_SECONDS = float(os.environ.get("HERMES_GUIDE_INGEST_DELAY_SECONDS", "2.2"))


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=2, max=30))
def ingest_doc(text: str, source_url: str) -> dict:
    resp = requests.post(
        f"{BACKEND_URL}/ingest",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={"text": text, "source_url": source_url},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    input_path = Path("pipeline/output/docs.jsonl")
    dlq_path = Path("pipeline/output/dlq-docs.jsonl")

    if not input_path.exists():
        print(f"FAIL input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    docs = [json.loads(line) for line in input_path.read_text().splitlines() if line.strip()]
    failed = []

    for i, doc in enumerate(docs, 1):
        try:
            result = ingest_doc(doc["content"], doc["url"])
            print(f"[{i}/{len(docs)}] OK  {doc['url']} -> {result.get('status', 'unknown')}")
            time.sleep(INGEST_DELAY_SECONDS)
        except Exception as e:
            print(f"[{i}/{len(docs)}] FAIL {doc['url']}: {e}", file=sys.stderr)
            failed.append({"url": doc["url"], "error": str(e)})

    if failed:
        dlq_path.parent.mkdir(parents=True, exist_ok=True)
        dlq_path.write_text("\n".join(json.dumps(f) for f in failed))
        print(f"\nFailed: {len(failed)} docs -> {dlq_path}", file=sys.stderr)

    ingested = len(docs) - len(failed)
    print(f"\nIngested {ingested}/{len(docs)} docs")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
