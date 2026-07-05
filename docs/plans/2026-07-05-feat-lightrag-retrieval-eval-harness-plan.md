---
title: "feat: Add LightRAG Retrieval Evaluation Harness"
type: feat
status: active
date: 2026-07-05
---

# feat: Add LightRAG Retrieval Evaluation Harness

## Overview

Add a deterministic retrieval evaluation harness for hermes-guide. The harness calls the public `/query` API with curated JSONL cases, scores the returned LightRAG context using keyword and structural checks, and produces pass/fail exit codes plus an optional JSON report. No LLM judge in phase one — the first risk is silent retrieval regressions hiding behind HTTP 200.

Source documents: `docs/lightrag-evals-prd.md`, `docs/lightrag-evals-spec.md`.

---

## Problem Statement

hermes-guide validates retrieval quality today with one live mixed-intent smoke test that checks a handful of expected words. This cannot catch:

- Retrieval regressions that still return HTTP 200
- Mixed-intent collapse (three user goals retrieving context for only one)
- Irrelevant context drifting into results (calendar topics in a coding query)
- Empty or thin context that passes the API schema check
- Reranker changes that silently alter relevance ordering
- Latency regressions from retrieval tuning

The result: a deploy could degrade Hermes coaching quality with no observable signal.

---

## Proposed Solution

Three new artifacts:

1. **`evals/cases/hermes_guide_retrieval.jsonl`** — 12–20 curated eval cases covering core Hermes use cases (coding, research, media, productivity, DevOps, mixed-intent, SOUL.md variants, negative relevance).
2. **`evals/fixtures/sample_responses.jsonl`** — frozen fixture responses per case ID for CI-safe runner testing without live LightRAG calls.
3. **`evals/run_retrieval_evals.py`** — CLI runner: reads cases, calls `/query` (or replays fixtures), scores each case, prints terminal summary, writes optional JSON report, exits nonzero on failures.

Four modifications to existing files:

- **`tests/test_retrieval_eval_runner.py`** — 8 minimum unit tests for runner scoring, report generation, error handling.
- **`Makefile`** — add `eval`, `eval-live`, `eval-fixture` targets.
- **`backend/main.py`** — add `GET /config` endpoint exposing non-secret retrieval configuration.
- **`README.md`** — add eval section documenting all three run modes.

---

## Technical Approach

### Architecture

The eval runner is a self-contained script that:
1. Reads JSONL cases from disk
2. For each case: POSTs to `/query` (or loads fixture), records latency, flattens `recommendations[].text` into a searchable blob
3. Scores: expected terms (case-insensitive all-must-match), forbidden terms (case-insensitive none-may-match), `context_lines >= min_context_lines`, `latency_ms <= max_latency_ms`, HTTP 200, valid JSON, `recommendations` is a list
4. Collects per-case results, computes suite-level summary metrics
5. Prints compact terminal output; writes JSON report if `--report` path given
6. Exits 0 if all pass, nonzero on any failure

**No new dependencies.** `urllib.request` for HTTP, `json` for parsing, `argparse` for CLI, `time` for latency, `re` for case-insensitive matching. This matches the existing `urllib.request` usage in `tests/test_skill_user_experience.py`.

### Python Environment Note

The eval runner does not import `backend.main` — it calls the HTTP API — so it runs on any Python. The runner tests in `tests/test_retrieval_eval_runner.py` similarly avoid backend imports. However, `python -m unittest discover tests` must use `backend/.venv/bin/python` because `test_mixed_intent_retrieval.py` imports `lightrag` which lives in the backend venv. All Makefile test/eval targets should use `backend/.venv/bin/python` for consistency.

### `/config` Endpoint

`_configured_rerank_provider()` already exists in `backend/main.py`. The new endpoint calls it plus reads the same `QueryParam` defaults already used in `_query_param_for_intent`. No new logic, just exposure. The eval runner calls `/config` opportunistically and records the result; if the call fails, it records config as unavailable and continues.

### Implementation Phases

#### Phase 1: Cases + Fixtures

**Files:**
- `evals/cases/hermes_guide_retrieval.jsonl` (12–20 cases)
- `evals/fixtures/sample_responses.jsonl` (one fixture per case)

**Case coverage** (14 initial cases, may grow to 20):

| ID | Category | Goal summary | SOUL.md |
|----|----------|--------------|---------|
| `coding_tdd_code_review` | Coding | Review code faster + TDD | thin |
| `coding_debug_failing_tests` | Coding | Debug failing tests | thin |
| `research_academic_papers` | Research | Academic paper discovery/synthesis | thin |
| `research_market_domain` | Research | Market/domain research | thin |
| `media_youtube_transcripts` | Media | YouTube transcript summarization | thin |
| `productivity_email_triage` | Productivity | Email triage automation | thin |
| `productivity_calendar_followup` | Productivity | Calendar/follow-up automation | thin |
| `devops_deploy_troubleshoot` | DevOps | Deploy troubleshooting/GitHub Actions | thin |
| `mixed_code_tdd_youtube` | Mixed | Code review + TDD + YouTube transcripts | thin |
| `mixed_research_writing_skills` | Mixed | Research + writing + skill recommendations | thin |
| `no_soul_beginner_setup` | SOUL variant | Beginner setup coaching | empty |
| `thin_soul_workflow_gaps` | SOUL variant | Gaps surfaced with thin context | thin |
| `strong_soul_goal_specific` | SOUL variant | Goal-specific retrieval with rich context | rich |
| `negative_coding_no_calendar` | Negative | Coding query must not drift to calendar/email | thin |

**Each case schema:**
```json
{
  "id": "coding_tdd_code_review",
  "goal": "I want Hermes to help me review code faster and use TDD.",
  "skills_list": ["software-development-workflows"],
  "soul_md": "## Workflow\nI use Hermes for coding.\n",
  "expected_terms": ["code review", "test-driven", "regression tests"],
  "forbidden_terms": ["calendar", "email triage"],
  "min_context_lines": 10,
  "max_latency_ms": 5000,
  "notes": "Core coding use case. Mixed-intent: code review AND TDD must both appear."
}
```

**Fixture schema** (per case ID):
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

#### Phase 2: Runner Implementation

**File:** `evals/run_retrieval_evals.py`

```
python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl
python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl --url https://hermes-guide.fly.dev
python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl --report evals/reports/latest.json
python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl --fixture evals/fixtures/sample_responses.jsonl
```

**URL resolution priority:** `--url` arg → `$HERMES_GUIDE_URL` → `http://localhost:8000`.

**Scoring per case:**
- HTTP status == 200 (required)
- Response parses as JSON (required)
- `recommendations` is a list (required)
- All `expected_terms` present in flattened text (case-insensitive)
- No `forbidden_terms` present in flattened text (case-insensitive)
- `context_lines >= min_context_lines` (when field present)
- `latency_ms <= max_latency_ms` (when field present)

Case passes only if all required checks pass.

**Report shape:**
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

**Terminal output:**
```
hermes-guide retrieval evals
URL: http://localhost:8000
Cases: 13 passed, 1 failed
Expected term recall: 93%
Forbidden violations: 0
p95 latency: 1800ms

FAIL mixed_code_tdd_youtube
  missing expected terms: youtube transcript
```

**Privacy:** Report must not include raw SOUL.md content, full request bodies, API keys, or response text snippets (the latter only behind an explicit `--debug` flag, not implemented in phase one).

#### Phase 3: Unit Tests

**File:** `tests/test_retrieval_eval_runner.py`

Minimum 8 test cases using `unittest.TestCase` (matching project convention):

1. `test_passes_when_all_expected_terms_present` — fixture with matching terms → case passes
2. `test_fails_when_expected_term_missing` — fixture missing one term → case fails, error names the term
3. `test_fails_when_forbidden_term_present` — fixture containing a forbidden term → case fails
4. `test_fails_when_context_lines_below_minimum` — `context_lines: 3`, `min_context_lines: 10` → fails
5. `test_fails_on_non_200_status` — fixture with `status: 500` → case fails with HTTP error
6. `test_produces_json_report_with_summary_and_cases` — `--report` path → report written, has `summary.total`, `summary.passed`, `cases` list
7. `test_handles_empty_recommendations_without_crashing` — `recommendations: []` → no exception, case fails on expected terms
8. `test_handles_malformed_fixture_body_with_clear_error` — truncated/invalid JSON in fixture → case error recorded, no crash

Tests must not make network calls. All HTTP replaced by fixture mode or direct import of runner scoring logic.

#### Phase 4: Makefile + `/config` + README

**Makefile additions:**
```make
.PHONY: eval eval-live eval-fixture test

test:
	backend/.venv/bin/python -m unittest discover tests

eval:
	backend/.venv/bin/python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl

eval-live:
	HERMES_GUIDE_URL=https://hermes-guide.fly.dev backend/.venv/bin/python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl

eval-fixture:
	backend/.venv/bin/python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl --fixture evals/fixtures/sample_responses.jsonl
```

**`backend/main.py` `/config` endpoint:**
```python
@app.get("/config")
async def get_config():
    provider = _configured_rerank_provider()
    return {
        "query_mode": "mix",
        "only_need_context": True,
        "rerank_enabled": provider is not None,
        "rerank_provider": provider,
        "rerank_model": os.getenv("RERANK_MODEL") if provider else None,
        "related_chunk_number": 1,
        "max_async": 2,
        "max_async_rerank": 1,
    }
```

Rules: no API keys, no admin token state, no SOUL.md, no request bodies. If rerank disabled/unconfigured: `rerank_enabled: false`, `rerank_provider: null`.

**README eval section** (add after "Usage"):
```markdown
## Evaluations

hermes-guide ships a retrieval eval suite to detect regressions in LightRAG context quality.

# Local (requires running service at localhost:8000)
make eval

# Production
make eval-live

# CI-safe fixture mode (no network calls)
make eval-fixture

# With JSON report
python evals/run_retrieval_evals.py evals/cases/hermes_guide_retrieval.jsonl --report evals/reports/latest.json

Live evals call the public /query endpoint only. They do not mutate the knowledge graph and do not require admin tokens.
```

---

## System-Wide Impact

### Interaction Graph

`make eval` → `evals/run_retrieval_evals.py` → `POST /query` → `_intent_queries_from_payload` → `_query_param_for_intent` (sets `only_need_context=True`, skips LLM call) → LightRAG graph query → `_merge_intent_contexts` → `_parse_context_to_recommendations` → HTTP response. Eval runner scores `recommendations[].text` and `context_lines`. No callbacks or observers fire in the eval path beyond the normal request lifecycle.

`/config` endpoint is read-only and side-effect-free. It calls `_configured_rerank_provider()` which reads env vars, no I/O.

### Error & Failure Propagation

| Error | Where handled | Effect |
|-------|--------------|--------|
| HTTP non-200 from `/query` | Runner per-case scorer | Case fails with `http_error` in `errors[]` |
| Invalid JSON response | Runner per-case scorer | Case fails with `json_parse_error` |
| Missing `recommendations` key | Runner per-case scorer | Case fails with `schema_error` |
| `/config` call fails | Runner suite setup | Config recorded as `null`, run continues |
| Malformed fixture line | Fixture loader | Case fails with `fixture_error`, run continues |
| Rate limit (10/min on `/query`) | Not yet handled | Live evals with >10 cases may hit 429; runner should handle gracefully |

**Rate limit note**: The spec does not mention handling slowapi's 10/min rate limit on `/query`. With 14+ cases, a live eval run could hit this. The runner should treat HTTP 429 as a case error (not a silent pass) and report it clearly. Consider adding a brief inter-request delay for live runs, or note this ceiling in README.

### State Lifecycle Risks

The eval runner is stateless. It writes no data to the backend. `--report` path creates a local file. Fixture mode reads files only. No partial-failure orphan risk.

### API Surface Parity

`/config` is a new public endpoint. It should be documented alongside `/query` in the README. No auth required (consistent with `/query`).

### Integration Test Scenarios

1. **Mixed-intent case passes**: `mixed_code_tdd_youtube` returns context containing both "code review" and "youtube transcript" — verifies that intent splitting and context merging both work end-to-end.
2. **Negative relevance holds**: `negative_coding_no_calendar` returns coding context without "calendar" — verifies topic isolation.
3. **No-SOUL beginner case**: `no_soul_beginner_setup` returns a `soul_md_gap` recommendation plus `knowledge_context` — verifies the empty-soul path.
4. **Fixture mode exit code**: running `eval-fixture` with a fixture that has a missing expected term should exit nonzero — CI gate behavior.
5. **`/config` + report correlation**: running with `--report` and checking that `config.rerank_enabled` matches the actual server env var state.

---

## Acceptance Criteria

- [ ] `backend/.venv/bin/python -m unittest discover tests` passes (all existing + new tests)
- [ ] `make eval-fixture` exits 0 with all fixture cases passing
- [ ] `make eval-fixture` exits nonzero when a fixture is missing an expected term
- [ ] `make eval-fixture` exits nonzero when a fixture contains a forbidden term
- [ ] `python evals/run_retrieval_evals.py ... --report path.json` writes a valid JSON report with `summary` and `cases` keys
- [ ] `GET /config` returns non-secret retrieval configuration (no API keys, no SOUL.md)
- [ ] README documents `make eval`, `make eval-live`, `make eval-fixture`
- [ ] No eval report includes raw SOUL.md content by default
- [ ] Runner handles HTTP 429 (rate limit) as a case error without crashing
- [ ] `make eval-live` runs against `https://hermes-guide.fly.dev` and reports per-case pass/fail (manual gate before release)

---

## Implementation Sequence

Follow the spec's ordering — it's correct:

1. `evals/cases/hermes_guide_retrieval.jsonl` — curate 14 cases
2. `evals/fixtures/sample_responses.jsonl` — one fixture per case
3. `evals/run_retrieval_evals.py` — implement runner with fixture mode first, live mode second
4. `tests/test_retrieval_eval_runner.py` — 8 unit tests
5. `Makefile` — add `test`, `eval`, `eval-live`, `eval-fixture` targets
6. `backend/main.py` — add `GET /config`
7. `README.md` — add eval section
8. `backend/.venv/bin/python -m unittest discover tests` — all pass
9. `make eval-fixture` — passes
10. `make eval` (local service running) — review results
11. `make eval-live` — manual, before release only

---

## Dependencies & Prerequisites

- Local service running for `make eval`: `make up` first
- Production deployment for `make eval-live`: existing `fly.toml` + deployed backend
- No new Python packages: runner is stdlib-only
- The backend venv (`backend/.venv`) must be provisioned: `cd backend && uv sync`

---

## Risk Analysis

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Eval cases too synthetic; retrieval passes on fixture but fails live | Medium | Seed cases from real Hermes usage patterns in `seed-data/`; run live eval before marking harness done |
| Rate limit (10/min) causes 429 on live eval with 14+ cases | Medium | Handle 429 as case error; document workaround (run in batches or increase limit for eval) |
| `context_lines` count differs between local and production (graph content differs) | Low-Medium | Use conservative `min_context_lines` thresholds; note that live evals require seeded production graph |
| `_configured_rerank_provider()` returns wrong value if env not set correctly | Low | `/config` response serves as sanity check; compare against known env before trusting scores |
| eval fixtures go stale as API response shape evolves | Low | Fix by keeping fixture schema minimal; add schema validation test |

---

## Out of Scope (This Phase)

- LLM judge / answer-quality scoring for `/guide` responses
- Eval case coverage for `/guide` endpoint (only `/query` scored)
- Running live evals on every CI push
- Admin ingestion or graph mutation
- Rerank benchmark comparison tooling (deferred to future phase)
- Category-level scoring (awaits stable context metadata)
- `--min-recall` non-strict mode for experimentation

---

## Future Work

- Phase 2: answer-quality eval that feeds retrieved context into a model and judges `/guide` response against a rubric (goal relevance, no fabricated skills, concrete SOUL.md guidance)
- Benchmark comparison tooling for rerank/no-rerank experiments using frozen snapshots
- `--min-recall` threshold for exploratory runs
- Category-level scoring when context metadata stabilizes
- Seed `docs/solutions/` with LightRAG retrieval quirks and JSONL fixture conventions learned during implementation

---

## Sources & References

### Origin Documents

- **PRD**: `docs/lightrag-evals-prd.md` — problem statement, user stories, implementation decisions, testing decisions, out-of-scope
- **SPEC**: `docs/lightrag-evals-spec.md` — file-level implementation spec, scoring rules, privacy rules, acceptance criteria, implementation sequence

### Internal References

- `/query` endpoint: `backend/main.py` — `QueryRequest`, `QueryResponse`, `_intent_queries_from_payload`, `_query_param_for_intent`, `_merge_intent_contexts`, `_parse_context_to_recommendations`
- Rerank config: `backend/main.py` — `_configured_rerank_provider()`
- Existing unit tests (pattern reference): `tests/test_mixed_intent_retrieval.py`
- Existing live smoke test (prior art): `tests/test_skill_user_experience.py`
- Existing urllib.request usage (pattern reference): `tests/test_skill_user_experience.py`
- Backend venv: `backend/.venv/bin/python` — required for tests that import `lightrag`

### Related Work

- Prior plan: `docs/plans/2026-07-02-feat-hermes-guide-lightrag-coaching-skill-plan.md`
