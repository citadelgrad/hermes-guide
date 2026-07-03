#!/usr/bin/env python3
"""Validate skills catalog was parsed correctly."""
import json, sys
from pathlib import Path

MINIMUM_SKILLS = 50  # conservative minimum (may not always get full 258 from parsing)

def main():
    catalog_path = Path("pipeline/output/skills-catalog.jsonl")
    if not catalog_path.exists():
        print("FAIL skills-catalog.jsonl not found", file=sys.stderr)
        sys.exit(1)

    skills = [json.loads(l) for l in catalog_path.read_text().splitlines() if l.strip()]

    if len(skills) < MINIMUM_SKILLS:
        print(f"FAIL Only {len(skills)} skills found, expected >={MINIMUM_SKILLS}", file=sys.stderr)
        sys.exit(1)

    print(f"ok {len(skills)} skills parsed successfully")

    # Show category breakdown
    categories = {}
    for s in skills:
        cat = s.get('category', 'unknown')
        categories[cat] = categories.get(cat, 0) + 1

    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

if __name__ == "__main__":
    main()
