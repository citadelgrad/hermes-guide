# SPEC: LightRAG Evaluation Harness for hermes-guide

## Overview

Build a deterministic retrieval evaluation harness for hermes-guide. The harness will run curated cases against the `/query` API, score the returned LightRAG context, and report whether retrieval still covers the expected Hermes setup guidance.

The initial spec intentionally avoids LLM-judge scoring. hermes-guide’s first risk is bad retrieval with a healthy API, not mediocre prose.

## Current System

Relevant current behavior:

- `backend/main.py` defines the FastAPI app and `/query` endpoint.
- `/query` accepts `goal`, `skills_list`, `soul_md`, and `max_results`.
- `_intent_queries_from_payload` splits mixed goals into intent-specific LightRAG queries.
- `_query_param_for_intent` sets LightRAG `QueryParam` with `mode="mix"`, `only_need_context=True`, optional rerank, token budgets, and keyword hints.
- `_merge_intent_contexts` dedupes and preserves per-intent context slices.
- `_parse_context_to_recommendations` returns raw retrieved context as a `knowledge_context` recommendation.
- `tests/test_mixed_intent_retrieval.py` covers intent splitting, query param settings, rerank configuration, and merge behavior.
- `tests/test_skill_user_experience.py` has one opt-in live mixed-intent smoke test.

## Goals

1. Add a repeatable retrieval benchmark for hermes-guide.
2. Catch regressions in mixed-intent retrieval, expected topic coverage, irrelevant context, empty/thin context, latency, and HTTP/schema failures.
3. Support local and production runs with the same case file.
4. Support fixture mode for CI-safe runner tests.
5. Capture enough non-secret config to compare rerank and retrieval tuning experiments.

## Non-Goals

1. Do not mutate or reseed LightRAG.
2. Do not require admin tokens for retrieval evals.
3. Do not log or persist submitted SOUL.md content beyond local eval reports.
4. Do not add LLM-judge answer-quality scoring in the first version.
5. Do not make live production evals mandatory in normal CI.
6. Do not replace existing unit tests.

## Files to Add

### `evals/cases/hermes_guide_retrieval.jsonl`

Frozen curated retrieval cases.

Each line is one JSON object:

```json
{
  "id": "coding_tdd_code_review",
  "goal": "I want Hermes to help me review code faster and use TDD.",
  "skills_list": ["software-development-workflows"],
  "soul_md": "## Workflow\nI use Hermes for coding.\n",
  "expected_terms": ["code review", "test-driven", "regression tests"],
  "forbidden_terms": ["calendar", "email triage"],
  "min_context_lines": 10,
  "max_latency_ms": 5000
}
```

Required fields:

- `id`: stable case identifier.
- `goal`: user goal sent to `/query`.
- `skills_list`: installed skills sent to `/query`.
- `soul_md`: SOUL.md content sent to `/query`; may be empty.
- `expected_terms`: terms or regex-like plain strings that must appear in returned recommendation text.

Optional fields:

- `forbidden_terms`: terms that must not appear in returned recommendation text.
- `min_context_lines`: minimum acceptable `context_lines` value from API response.
- `max_latency_ms`: per-case latency ceiling.
- `expected_categories`: future use; category labels expected in recommendation metadata or retrieved context.
- `notes`: human explanation for why the case exists.

Initial case coverage:

1. Coding: code review + TDD.
2. Coding: debugging failing tests.
3. Research: academic paper discovery/synthesis.
4. Research: market/domain research.
5. Media: YouTube transcript summarization.
6. Productivity: email triage.
7. Productivity: calendar/follow-up automation.
8. DevOps: deploy troubleshooting/GitHub Actions.
9. Mixed intent: code review + TDD + YouTube transcripts.
10. Mixed intent: research + writing + skill recommendations.
11. No SOUL.md: beginner setup coaching.
12. Thin SOUL.md: workflow gaps should surface.
13. Strong SOUL.md: goal-specific skill retrieval should still work.
14. Negative relevance: coding query should not drift into calendar/email.

Start with 12–20 high-signal cases. Do not inflate the suite with low-quality duplicates.

### `evals/run_retrieval_evals.py`

Command-line eval runner.

Required behavior:

- Accept a case file path.
- Read JSONL cases.
- Resolve API base URL from `--url` or `$HERMES_GUIDE_URL`; default to `http://localhost:8000` if neither is set.
- POST each case to `/query`.
- Flatten `recommendations[].text` into one searchable text blob.
- Score expected terms, forbidden terms, context line count, latency, and HTTP/schema errors.
- Print a concise terminal summary.
- Write an optional JSON report.
- Exit `0` if all required checks pass.
- Exit nonzero if any required check fails.

Suggested CLI:

```bash
python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl
python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl --url https://hermes-guide.fly.dev
python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl --report evals/reports/latest.json
python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl --fixture evals/fixtures/sample_responses.jsonl
```

Use Python stdlib first. `urllib.request` is enough; avoid adding dependencies unless needed.

Report shape:

```json
{
  "api_url": "https://hermes-guide.fly.dev",
  "started_at": "2026-07-05T00:00:00Z",
  "config": {
    "rerank_enabled": true,
    "rerank_provider": "jina",
    "query_mode": "mix"
  },
  "summary": {
    "total": 14,
    "passed": 13,
    "failed": 1,
    "expected_term_recall": 0.93,
    "forbidden_violations": 0,
    "p95_latency_ms": 1800
  },
  "cases": [
    {
      "id": "coding_tdd_code_review",
      "passed": true,
      "latency_ms": 812,
      "context_lines": 42,
      "missing_expected_terms": [],
      "forbidden_terms_found": [],
      "errors": []
    }
  ]
}
```

Terminal output should be compact:

```text
hermes-guide retrieval evals
URL: https://hermes-guide.fly.dev
Cases: 14 passed, 1 failed
Expected term recall: 93%
Forbidden violations: 0
p95 latency: 1800ms

FAIL mixed_code_tdd_youtube
  missing expected terms: youtube transcript
```

### `evals/fixtures/sample_responses.jsonl`

Fixture responses for runner tests.

Each line maps a case id to a saved response:

```json
{
  "id": "coding_tdd_code_review",
  "status": 200,
  "latency_ms": 100,
  "body": {
    "recommendations": [
      {
        "category": "knowledge_context",
        "text": "Code review skill context. Test-driven development and regression tests.",
        "priority": 2
      }
    ],
    "context_lines": 12,
    "query_mode": "mix"
  }
}
```

Fixture mode lets CI verify parsing/scoring without calling LightRAG.

### `tests/test_retrieval_eval_runner.py`

Unit tests for runner behavior.

Minimum cases:

1. Passes when all expected terms are present.
2. Fails when an expected term is missing.
3. Fails when a forbidden term is present.
4. Fails when `context_lines` is below `min_context_lines`.
5. Fails on non-200 fixture status.
6. Produces JSON report with summary and per-case details.
7. Handles empty recommendations without crashing.
8. Handles malformed fixture/body data with a clear case error.

## Files to Modify

### `Makefile`

Add phony targets:

```make
.PHONY: eval eval-live eval-fixture

eval:
	python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl

eval-live:
	HERMES_GUIDE_URL=https://hermes-guide.fly.dev python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl

eval-fixture:
	python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl --fixture evals/fixtures/sample_responses.jsonl
```

If the repo standardizes on `uv`, use the same style as the existing scripts and tests. Do not introduce a new dependency manager pattern unnecessarily.

### `backend/main.py`

Add a safe config endpoint:

`GET /config`

Return only non-secret retrieval configuration:

```json
{
  "query_mode": "mix",
  "only_need_context": true,
  "rerank_enabled": true,
  "rerank_provider": "jina",
  "rerank_model": "jina-reranker-v3",
  "related_chunk_number": 1,
  "max_async": 2,
  "max_async_rerank": 1
}
```

Rules:

- Do not return API keys.
- Do not return admin token state.
- Do not return request bodies.
- Do not return SOUL.md content.
- If provider is auto-detected from env, return the provider name only.
- If rerank is disabled or unconfigured, return `rerank_enabled: false` and `rerank_provider: null`.

The eval runner should treat `/config` as optional: if it fails, continue and record config as unavailable.

### `README.md`

Add a short section for evals:

- Local eval command.
- Production eval command.
- Fixture/CI-safe command.
- Note that live evals call the public query endpoint and do not mutate the graph.

## Scoring Rules

For each case:

- `expected_terms`: all must be present, case-insensitive.
- `forbidden_terms`: none may be present, case-insensitive.
- `min_context_lines`: API `context_lines` must be greater than or equal to the configured value.
- `max_latency_ms`: measured latency must be less than or equal to the configured value.
- HTTP status must be 200.
- Response must parse as JSON.
- Response must contain `recommendations` as a list.

Case passes only if all required checks pass.

Suite passes only if all cases pass in strict mode.

Future option: add `--min-recall` for non-strict experimentation, but strict all-pass should be the default for release checks.

## Privacy and Safety

- Do not log SOUL.md content unless the user explicitly runs the eval locally and chooses to inspect their case file.
- Reports may include case ids, scores, latency, missing terms, and forbidden violations.
- Reports should not include full request bodies by default.
- Reports may include response snippets only behind an explicit debug flag.
- Live evals must use `/query`, not `/ingest`.
- Live evals must not require `HERMES_GUIDE_ADMIN_TOKEN`.

## Example Eval Cases

```jsonl
{"id":"coding_tdd_code_review","goal":"I want Hermes to help me review code faster and use TDD.","skills_list":["software-development-workflows"],"soul_md":"## Workflow\nI use Hermes for coding.\n","expected_terms":["code review","test-driven","regression tests"],"forbidden_terms":["calendar","email triage"],"min_context_lines":10,"max_latency_ms":5000}
{"id":"media_youtube_transcripts","goal":"I want Hermes to summarize YouTube transcripts and turn videos into notes.","skills_list":["media-content-operations"],"soul_md":"## Communication\nBe concise and actionable.\n","expected_terms":["youtube","transcript","summary"],"forbidden_terms":["terraform","deploy"],"min_context_lines":8,"max_latency_ms":5000}
{"id":"mixed_code_tdd_youtube","goal":"I want Hermes to help me review code, use TDD, and summarize YouTube transcripts.","skills_list":["software-development-workflows","duckduckgo-search"],"soul_md":"## Workflow\nI use Hermes for coding and research.\n","expected_terms":["code review","test-driven","youtube","transcript"],"forbidden_terms":["calendar"],"min_context_lines":12,"max_latency_ms":7000}
```

## Implementation Sequence

1. Add eval case JSONL with 12–20 curated cases.
2. Add fixture JSONL with enough responses to test runner behavior.
3. Implement `evals/run_retrieval_evals.py` with fixture mode first.
4. Add unit tests for runner scoring and report generation.
5. Add Make targets.
6. Add `/config` endpoint.
7. Add README eval instructions.
8. Run unit tests.
9. Run fixture eval.
10. Run local live eval if the local service is available.
11. Run production live eval manually before release.

## Acceptance Criteria

- `python -m unittest discover tests` passes.
- `make eval-fixture` passes without network access.
- `make eval-live` runs against `https://hermes-guide.fly.dev` and reports per-case pass/fail.
- The eval runner exits nonzero when a fixture is missing an expected term.
- The eval runner exits nonzero when a fixture includes a forbidden term.
- The eval runner writes a JSON report when `--report` is provided.
- `/config` returns non-secret retrieval configuration.
- README documents local, live, and fixture eval commands.
- No eval report includes raw SOUL.md content by default.

## Future Work

- Add a second-stage answer-quality eval that asks a model to synthesize the final `/guide` response from retrieved context.
- Add an LLM judge rubric for final response quality: goal relevance, no fabricated skills, concrete SOUL.md guidance, prioritized skills, and quick wins.
- Add benchmark comparison tooling for rerank/no-rerank experiments.
- Store curated benchmark result snapshots for release notes.
- Add category-level scoring once retrieved context has more stable metadata.
