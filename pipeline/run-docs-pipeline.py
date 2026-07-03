#!/usr/bin/env python3
"""Standalone runner for the hermes-docs ingestion pipeline.

Usage:
    python pipeline/run-docs-pipeline.py

Environment variables required for ingest stage:
    HERMES_GUIDE_ADMIN_TOKEN  - admin bearer token for /ingest endpoint
    HERMES_GUIDE_URL          - base URL (default: http://127.0.0.1:7842)

Run from the repo root so stage scripts resolve pipeline/output/ correctly.
"""
import subprocess
import sys

stages = [
    ("discover-urls", ["python", "pipeline/stages/discover_urls.py"]),
    ("fetch-docs",    ["python", "pipeline/stages/fetch_docs.py"]),
    ("validate-docs", ["python", "pipeline/stages/validate_docs.py"]),
    ("ingest-docs",   ["python", "pipeline/stages/ingest_docs.py"]),
]

for name, cmd in stages:
    print(f"\n{'=' * 50}")
    print(f"Stage: {name}")
    print(f"{'=' * 50}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nFAIL Stage '{name}' failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"OK  Stage '{name}' complete")

print("\nOK  Pipeline complete")
