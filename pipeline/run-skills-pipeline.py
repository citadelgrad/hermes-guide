#!/usr/bin/env python3
"""Standalone runner for the skills catalog ingestion pipeline."""
import subprocess, sys

stages = [
    ("fetch-readme",   ["python", "pipeline/stages/fetch_skills_readme.py"]),
    ("parse-skills",   ["python", "pipeline/stages/parse_skills.py"]),
    ("validate-skills",["python", "pipeline/stages/validate_skills.py"]),
    ("ingest-skills",  ["python", "pipeline/stages/ingest_skills.py"]),
]

for name, cmd in stages:
    print(f"\n{'='*50}")
    print(f"Stage: {name}")
    print(f"{'='*50}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"FAIL Stage '{name}' failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"ok Stage '{name}' complete")

print("\nok Skills pipeline complete")
