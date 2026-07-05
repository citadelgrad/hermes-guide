# Investigation: hermes-guide-qq1.1

## Task
Create `evals/cases/hermes_guide_retrieval.jsonl` with 14 curated retrieval eval cases.

## Files to Modify
- **Create**: `evals/cases/hermes_guide_retrieval.jsonl` (directory does not exist yet)

## Current Behavior
- No `evals/` directory exists at all
- No eval cases file exists

## Required Changes
Create `evals/cases/hermes_guide_retrieval.jsonl` with exactly 14 cases covering all required categories.

## Key Constraints from Spec
- Schema: `{id, goal, skills_list, soul_md, expected_terms, forbidden_terms?, min_context_lines?, max_latency_ms?, notes?}`
- `max_latency_ms`: 5000 single-intent, 7000 mixed-intent (mixed_* prefix cases)
- `no_soul_beginner_setup` must have `soul_md: ""`
- `negative_coding_no_calendar` must have `forbidden_terms: ["calendar", "email triage"]`
- All expected_terms cover ALL stated intents in mixed-intent cases
- Every line valid JSON

## Realistic Skills (from skill/v1/)
Available skill directory files confirm these skill names exist:
- `software-development-workflows` (referenced in spec examples)
- `media-content-operations` (referenced in spec examples)
- `devops-engineer`
- `research-agent-academic`
- `research-agent-market`
- `personal-assistant-calendar`
- `data-analysis-analyst`
- `duckduckgo-search`

## Keyword Aliases in main.py `_expand_keywords`
The backend expands these — expected_terms should align with what the graph would surface:
- tdd → test-driven development, regression tests
- youtube → youtube transcript, transcript, video summary
- email → email triage, gmail, inbox
- calendar → calendar, scheduling, followups

## Risks
- None: this is a new static data file, no code changes
- Expected terms must be realistic for what LightRAG would return from the ingested skill docs; keep them broadly present in domain docs rather than exact phrase matches
