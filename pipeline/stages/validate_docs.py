#!/usr/bin/env python3
"""Validate that expected docs were processed."""
import json
import sys
from pathlib import Path

MINIMUM_EXPECTED = 6  # at minimum the priority pages


def main():
    docs_path = Path("pipeline/output/docs.jsonl")
    if not docs_path.exists():
        print("FAIL docs.jsonl not found", file=sys.stderr)
        sys.exit(1)

    docs = [json.loads(l) for l in docs_path.read_text().splitlines() if l.strip()]

    if len(docs) < MINIMUM_EXPECTED:
        print(f"FAIL Only {len(docs)} docs found, expected >={MINIMUM_EXPECTED}", file=sys.stderr)
        sys.exit(1)

    print(f"OK  {len(docs)} docs fetched and ready for ingestion")
    for doc in docs[:5]:
        print(f"    - {doc['url']} ({len(doc['content'])} chars)")
    if len(docs) > 5:
        print(f"    ... and {len(docs) - 5} more")


if __name__ == "__main__":
    main()
