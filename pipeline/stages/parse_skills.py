#!/usr/bin/env python3
"""Parse the awesome-hermes-skills README tables into structured JSONL."""
import json, re, sys
from pathlib import Path


def parse_markdown_tables(text: str) -> list[dict]:
    """Extract rows from all markdown tables in text."""
    skills = []

    # Split into sections to capture category context
    sections = re.split(r'^#{1,3}\s+', text, flags=re.MULTILINE)

    current_category = "general"
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue

        # First line is the section heading
        heading = lines[0].strip()
        if heading and not heading.startswith('|'):
            current_category = heading.lower().replace(' ', '-')

        # Find table rows
        table_lines = [l for l in lines if l.strip().startswith('|')]
        if len(table_lines) < 2:
            continue

        # Parse header
        header_line = table_lines[0]
        headers = [h.strip().lower() for h in header_line.strip('|').split('|')]

        # Skip separator row
        data_rows = table_lines[2:]

        for row in data_rows:
            cells = [c.strip() for c in row.strip('|').split('|')]
            if len(cells) != len(headers):
                continue

            entry = dict(zip(headers, cells))
            entry['category'] = current_category

            # Extract skill name from markdown links like [name](url)
            name_field = entry.get('name', entry.get('skill', ''))
            link_match = re.match(r'\[([^\]]+)\]\(([^)]+)\)', name_field)
            if link_match:
                entry['name'] = link_match.group(1)
                entry['url'] = link_match.group(2)

            # Only include rows that look like actual skill entries (have a name)
            if entry.get('name') and len(entry['name']) > 1:
                skills.append(entry)

    if skills:
        return skills

    return parse_markdown_bullets(text)


def _clean_heading(text: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'^[^\w\[]+\s*', '', text).strip()
    return text.lower().replace(' ', '-') or 'general'


def parse_markdown_bullets(text: str) -> list[dict]:
    """Extract skill rows from the current awesome-hermes-skills list format."""
    skills = []
    current_category = "general"

    bold_re = re.compile(r'^- \*\*([^*]+)\*\*\s+—\s+(.+)$')
    link_re = re.compile(r'^- \[([^\]]+)\]\(([^)]+)\)(?: by \[[^\]]+\]\([^)]+\))?\s+—\s+(.+)$')
    summary_re = re.compile(r'<summary><h3[^>]*>(.*?)</h3></summary>')

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if line.startswith('## '):
            current_category = _clean_heading(line.removeprefix('## '))
            continue

        if line.startswith('### '):
            current_category = _clean_heading(line.removeprefix('### '))
            continue

        summary_match = summary_re.search(line)
        if summary_match:
            current_category = _clean_heading(summary_match.group(1))
            continue

        match = bold_re.match(line)
        if match:
            name, desc = match.groups()
            skills.append({
                'name': name.strip(),
                'description': desc.strip(),
                'category': current_category,
            })
            continue

        match = link_re.match(line)
        if match:
            name, url, desc = match.groups()
            skills.append({
                'name': name.strip(),
                'url': url.strip(),
                'description': desc.strip(),
                'category': current_category,
            })

    return skills


def skills_to_document(skills: list[dict], category: str) -> str:
    """Convert a list of skill dicts to a document for LightRAG ingestion."""
    lines = [f"# Hermes Skills Catalog — {category.title()}\n"]
    for s in skills:
        name = s.get('name', 'Unknown')
        desc = s.get('description', s.get('desc', ''))
        use_case = s.get('use case', s.get('use_case', s.get('usecase', '')))
        url = s.get('url', '')

        lines.append(f"## {name}")
        if desc:
            lines.append(f"{desc}")
        if use_case:
            lines.append(f"Use case: {use_case}")
        if url:
            lines.append(f"Install: `hermes skills install {url}`")
        lines.append("")
    return "\n".join(lines)


def main():
    readme_path = Path("pipeline/output/awesome-hermes-skills-readme.md")
    output_path = Path("pipeline/output/skills-catalog.jsonl")
    batches_path = Path("pipeline/output/skills-batches.jsonl")

    text = readme_path.read_text()
    skills = parse_markdown_tables(text)

    # Write individual skill records
    output_path.write_text("\n".join(json.dumps(s) for s in skills))
    print(f"Parsed {len(skills)} skills -> {output_path}")

    # Group by category for batch ingestion
    categories = {}
    for s in skills:
        cat = s.get('category', 'general')
        categories.setdefault(cat, []).append(s)

    # Write as documents (one per category)
    batches = []
    for cat, cat_skills in categories.items():
        doc_text = skills_to_document(cat_skills, cat)
        batches.append({
            "text": doc_text,
            "source_url": f"https://github.com/ZeroPointRepo/awesome-hermes-skills#category-{cat}",
            "category": cat,
            "count": len(cat_skills),
        })

    batches_path.write_text("\n".join(json.dumps(b) for b in batches))
    print(f"Created {len(batches)} category batches -> {batches_path}")

    for cat, cat_skills in sorted(categories.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(cat_skills)} skills")

if __name__ == "__main__":
    main()
