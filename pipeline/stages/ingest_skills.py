#!/usr/bin/env python3
"""Ingest skills catalog batches into LightRAG via the hermes-guide backend."""
import json, os, sys
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

BACKEND_URL = os.environ.get("HERMES_GUIDE_URL", "http://127.0.0.1:7842")
ADMIN_TOKEN = os.environ["HERMES_GUIDE_ADMIN_TOKEN"]

@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=2, max=30))
def ingest_batch(text: str, source_url: str):
    resp = requests.post(
        f"{BACKEND_URL}/ingest",
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        json={"text": text, "source_url": source_url},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()

def main():
    batches_path = Path("pipeline/output/skills-batches.jsonl")
    dlq_path = Path("pipeline/output/dlq-skills.jsonl")

    batches = [json.loads(l) for l in batches_path.read_text().splitlines() if l.strip()]
    failed = []

    for i, batch in enumerate(batches, 1):
        try:
            ingest_batch(batch["text"], batch["source_url"])
            print(f"[{i}/{len(batches)}] ok {batch['category']} ({batch['count']} skills)")
        except Exception as e:
            print(f"[{i}/{len(batches)}] FAIL {batch['category']}: {e}", file=sys.stderr)
            failed.append({"category": batch["category"], "error": str(e)})

    if failed:
        dlq_path.write_text("\n".join(json.dumps(f) for f in failed))
        print(f"\nFailed: {len(failed)} batches -> {dlq_path}", file=sys.stderr)

    print(f"\nIngested {len(batches) - len(failed)}/{len(batches)} skill batches")
    if failed:
        sys.exit(1)

if __name__ == "__main__":
    main()
