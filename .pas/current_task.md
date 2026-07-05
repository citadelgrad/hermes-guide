# Current Task: hermes-guide-qq1.1

## Title
feat: Curate eval case JSONL — hermes_guide_retrieval.jsonl

## Description
Create evals/cases/hermes_guide_retrieval.jsonl with 14 curated retrieval eval cases.

### Why
Without curated cases there is nothing to run. This file is the ground truth for what good retrieval looks like — it should represent real Hermes user goals, not synthetic benchmarks.

### What to Build
File: evals/cases/hermes_guide_retrieval.jsonl

14 cases covering:
- coding_tdd_code_review — code review + TDD (mixed intent)
- coding_debug_failing_tests — debugging
- research_academic_papers — academic discovery/synthesis
- research_market_domain — market research
- media_youtube_transcripts — YouTube summarization
- productivity_email_triage — email triage
- productivity_calendar_followup — calendar automation
- devops_deploy_troubleshoot — deploy/GitHub Actions
- mixed_code_tdd_youtube — 3-way mixed intent
- mixed_research_writing_skills — research + writing
- no_soul_beginner_setup — empty soul_md (beginner)
- thin_soul_workflow_gaps — thin soul_md
- strong_soul_goal_specific — rich soul_md
- negative_coding_no_calendar — coding must not return calendar/email context

Each case schema: {id, goal, skills_list, soul_md, expected_terms, forbidden_terms (opt), min_context_lines (opt), max_latency_ms (opt), notes (opt)}

See docs/lightrag-evals-spec.md for example cases.

## Acceptance Criteria
- File exists at evals/cases/hermes_guide_retrieval.jsonl
- Exactly 14 cases (12-20 is acceptable if coverage warrants)
- Every case has: id, goal, skills_list, soul_md, expected_terms
- All 14 category types listed above are represented
- Mixed-intent cases have expected_terms covering ALL stated intents — not just one topic
- negative_coding_no_calendar has forbidden_terms: [calendar, email triage]
- no_soul_beginner_setup has soul_md: empty string
- Every line is valid JSON (jq -c . evals/cases/hermes_guide_retrieval.jsonl passes without error)
- Case IDs are unique and snake_case
- max_latency_ms is 5000 for single-intent, 7000 for mixed-intent cases

## Status
IN_PROGRESS
