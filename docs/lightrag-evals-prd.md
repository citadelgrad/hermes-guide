# PRD: LightRAG Evaluation Harness for hermes-guide

## Problem Statement

hermes-guide depends on LightRAG retrieval quality, but today the project mostly verifies that the service is alive and that one live mixed-intent smoke test contains a few expected words. That is too weak. A healthy endpoint can still return irrelevant or incomplete context, collapse mixed goals into one topic, silently degrade when reranking changes, or become slower/costlier without anyone noticing.

The project needs a repeatable evaluation loop that answers the product question: when a Hermes user asks for setup coaching, did the knowledge graph retrieve the right context for their actual goal?

## Solution

Add a small, deterministic eval suite for hermes-guide retrieval quality. The first version should evaluate the `/query` API response directly, using curated JSONL cases and stable keyword/category checks rather than an LLM judge.

The eval suite should let maintainers run the same cases against local and hosted deployments, compare retrieval configurations such as rerank/no-rerank, and catch regressions in mixed-intent coverage, irrelevant context, latency, and empty or thin responses.

The solution should produce a simple pass/fail result for normal development and a richer JSON report for deeper comparisons.

## User Stories

1. As a hermes-guide maintainer, I want to run retrieval evals locally, so that I can verify LightRAG changes before deploying.
2. As a hermes-guide maintainer, I want to run retrieval evals against production, so that I can detect live knowledge graph regressions.
3. As a hermes-guide maintainer, I want deterministic eval cases, so that retrieval quality changes are visible instead of hidden behind subjective prose.
4. As a hermes-guide maintainer, I want mixed-intent eval cases, so that goals like “review code, use TDD, and summarize YouTube transcripts” do not collapse to one topic.
5. As a hermes-guide maintainer, I want sparse-SOUL and no-SOUL cases, so that onboarding users get useful guidance even before they have rich personal context.
6. As a hermes-guide maintainer, I want strong-SOUL cases, so that the graph still retrieves setup advice relevant to the user’s stated workflow.
7. As a hermes-guide maintainer, I want expected terms checked in retrieved context, so that key concepts like “code review” or “test-driven development” are not dropped.
8. As a hermes-guide maintainer, I want forbidden terms checked in retrieved context, so that irrelevant topics like calendar or email triage do not pollute coding answers.
9. As a hermes-guide maintainer, I want context-size checks, so that “successful” queries with nearly empty context fail loudly.
10. As a hermes-guide maintainer, I want latency captured per case, so that retrieval tuning does not create unacceptable user wait times.
11. As a hermes-guide maintainer, I want HTTP failures reported clearly, so that service, schema, and validation breaks are not misread as retrieval failures.
12. As a hermes-guide maintainer, I want pass/fail thresholds, so that the eval suite can be used in development and release gates.
13. As a hermes-guide maintainer, I want machine-readable reports, so that config experiments can be compared later.
14. As a hermes-guide maintainer, I want safe live evals, so that production checks do not require admin tokens or mutate the graph.
15. As a hermes-guide maintainer, I want to evaluate reranker variants, so that Jina, Cohere, disabled rerank, and token-budget changes can be compared on the same benchmark.
16. As a hermes-guide maintainer, I want non-secret retrieval config exposed, so that reports can explain what configuration produced a score.
17. As a hermes-guide maintainer, I want the eval cases to represent real product use cases, so that improvements optimize user outcomes rather than synthetic benchmarks.
18. As a hermes-guide maintainer, I want local fixture mode for CI, so that normal pull requests can verify runner behavior without paid live calls.
19. As a hermes-guide maintainer, I want live evals to be explicit/manual, so that CI does not become flaky or unexpectedly expensive.
20. As a future contributor, I want clear docs for adding eval cases, so that the benchmark grows with new Hermes skills and workflows.
21. As a future contributor, I want failures to name the exact unmet expectation, so that I can fix retrieval, case data, or seed data quickly.
22. As a future contributor, I want answer-quality evals deferred until retrieval evals are stable, so that pretty generated prose does not hide bad retrieval.

## Implementation Decisions

- The first eval layer will target retrieval quality, not final answer quality.
- The eval runner will call the public query API and inspect returned recommendation text.
- Eval cases will be stored as JSONL so cases are easy to diff, append, and review.
- Each eval case will include a user goal, installed skills, SOUL.md content, expected terms, optional forbidden terms, and minimum context requirements.
- The scoring model will prefer deterministic keyword and structural checks over an LLM judge in the first version.
- The runner will produce both human-readable terminal output and a JSON report.
- The runner will exit nonzero when required thresholds fail.
- Local and live runs will use the same case file.
- Production evals will be manual or opt-in, not automatic on every push.
- A fixture mode will be available for CI-safe runner verification without calling the live service.
- Retrieval configuration should be captured in reports when the service exposes it.
- The service should expose only non-secret configuration fields. API keys, tokens, request bodies, SOUL.md content, and raw private user input must not be logged or returned by config endpoints.
- Rerank experiments should be compared against a frozen benchmark rather than one-off manual prompts.
- The benchmark should start small and curated: roughly 12–20 cases covering core hermes-guide use cases.
- The eval suite should treat mixed-intent coverage as a first-class quality signal.
- Answer-quality or LLM-judge evals are a later phase after retrieval behavior is measurable and stable.

## Testing Decisions

- Test external behavior: the eval runner’s observable output, exit codes, parsed API responses, and report contents.
- Keep existing unit tests for intent splitting, query parameter construction, and mixed-intent context merging.
- Add runner tests that use fixture responses rather than live LightRAG calls.
- Add tests for pass and fail outcomes: missing expected terms, forbidden terms present, insufficient context, HTTP errors, and latency/report fields.
- Keep live API acceptance tests behind explicit environment flags.
- Use existing mixed-intent tests as prior art for coverage expectations.
- Use the existing live guide user-experience test as prior art for production smoke behavior, but do not rely on it as the full retrieval benchmark.

## Out of Scope

- Rebuilding the LightRAG ingestion pipeline.
- Changing seed data sources as part of the initial eval harness.
- Adding an LLM judge in phase one.
- Evaluating the final prose quality of `/guide` responses in phase one.
- Running live evals on every CI push by default.
- Returning or storing user SOUL.md content in reports.
- Adding admin-only ingestion or graph mutation behavior.
- Choosing a permanent rerank provider solely from anecdotal manual tests.

## Further Notes

The first version should be boring on purpose. Keyword checks are imperfect, but they are stable, cheap, and good at catching the current risk: retrieval regressions that still return HTTP 200.

Once the deterministic suite is useful, the project can add a second-stage answer-quality eval that feeds retrieved context into a model and judges the final `/guide` response against a rubric. That should be additive, not a replacement for retrieval evals.
