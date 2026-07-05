# Test Results

## Status: PASSED

**11 passed, 1 skipped, 5 warnings** — 2026-07-05

## Run command

```bash
HERMES_GUIDE_ADMIN_TOKEN=test-token LIGHTRAG_DATA_DIR=/tmp/hermes-guide-test-data \
  /Volumes/qwiizlab/projects/hermes-guide/backend/.venv/bin/python -m pytest tests/ -v
```

## Suite breakdown

### tests/test_mixed_intent_retrieval.py — 6/6 PASSED
- `test_build_rerank_model_func_detects_jina_key`
- `test_merge_preserves_each_intent_before_broad_truncation`
- `test_query_param_allows_env_overrides_for_rerank_volume`
- `test_query_param_disables_rerank_when_no_model_is_configured`
- `test_query_param_enables_rerank_when_model_is_configured`
- `test_splits_goal_into_intent_queries_with_aliases`

### tests/test_skill_user_experience.py — 5/5 PASSED, 1 SKIPPED
- `test_skill_asks_one_goal_question_before_calling_api`
- `test_skill_has_no_token_friction_and_prompts_for_only_url` (2 subtests)
- `test_skill_payload_command_handles_quotes_newlines_and_installed_skills`
- `test_skill_preflight_gives_actionable_missing_url_message`
- `test_skill_presentation_contract_is_three_user_facing_sections`
- `test_live_mixed_intent_context_supports_user_visible_sections` — SKIPPED (requires `HERMES_GUIDE_LIVE_TESTS=1`)

## Warnings (non-blocking)

Third-party deprecations only — `pypinyin`, `google-genai`, `slowapi`. No project code warnings.

## Setup fix applied

Added `conftest.py` at repo root to insert the project root on `sys.path`, eliminating the need to set `PYTHONPATH` manually. Also added `pytest` as a dev dependency in `backend/pyproject.toml`.
