---
title: "feat: Build hermes-guide — LightRAG-Powered Hermes Coaching Skill"
type: feat
status: active
date: 2026-07-02
origin: research.md
---

# feat: Build hermes-guide — LightRAG-Powered Hermes Coaching Skill

## Overview

A native Hermes Agent skill (`/guide`) backed by a hosted LightRAG knowledge graph. The skill collects a user's current Hermes setup — SOUL.md, installed skills, goal — and returns personalized coaching: what's missing, what pairs together, what to configure next.

**The gap:** 258+ Hermes skills exist across 14 categories. Zero do setup coaching. All existing help is generic static content (blog posts, YouTube tutorials). Users want personalized answers — "MY SOUL.md, MY stack, MY goals" — and are already trying to get them awkwardly by pasting articles into Hermes itself.

**Validation:** Deep research (2026-07-02) confirmed niche unoccupied with high confidence. Demand validated via Twitter signal — SOUL.md personalization and "which skills should I install" are the top active pain points. See [research.md](../../research.md).

---

## Architecture

```
User (Hermes session)
  └── /guide skill (SKILL.md, installable via URL)
        ├── reads: ~/.hermes/soul.md
        ├── reads: ~/.hermes/skills/ (ls)
        ├── asks: "What are you trying to accomplish?"
        ├── POSTs via curl: { soul_md, skills_list, goal } → hermes-guide API
        └── formats and presents: personalized recommendations

hermes-guide API (Fly.io)
  ├── FastAPI + LightRAG (Python, uv)
  ├── POST /query  → personalized coaching response
  ├── POST /ingest → admin-only ingestion endpoint
  └── Knowledge graph (Neo4j + vector store via LightRAG)
       ├── Official Hermes docs (crawled)
       ├── 258+ skills catalog (built-in + optional + community)
       ├── Tips & Best Practices (official)
       ├── Learning Path (official)
       └── Curated SOUL.md patterns (15 hand-selected examples)
```

**Why LightRAG over plain RAG:** skills, SOUL.md sections, and context files are relational. "To build an autonomous coding agent, you need skill X, which pairs with skill Y, and requires configuring SOUL.md section Z" is multi-hop reasoning vector search alone can't surface. LightRAG's Delta Index also allows continuous ingestion without re-indexing.

---

## Implementation Phases

### Phase 1 — Backend Foundation

Stand up the LightRAG + FastAPI server locally and in production.

**Tasks:**
- [ ] Initialize Python project with `uv init` in `backend/`
- [ ] Add dependencies: `lightrag-hku`, `fastapi`, `uvicorn`
- [ ] Implement two endpoints:
  - `POST /query` — accepts `{soul_md, skills_list, goal}`, returns coaching JSON
  - `POST /ingest` — admin-only, accepts `{text, source_url}`, ingests into graph
- [ ] Add `LIGHTRAG_API_KEY` auth (Bearer token, env var)
- [ ] Makefile targets: `make up`, `make down`, `make logs`, `make status`
- [ ] Docker Compose on a non-default port (e.g., `7842`)
- [ ] `.envrc` for local secrets — never committed
- [ ] Validate: local `curl -X POST /query` returns a LightRAG response

**Key files:**
- `backend/main.py` — FastAPI app, two routes
- `backend/pyproject.toml` — uv-managed dependencies
- `docker-compose.yml` — backend service on port 7842
- `Makefile` — lifecycle targets
- `.envrc.example` — template for required env vars

---

### Phase 2 — Knowledge Graph Seeding (PAS CLI Pipeline)

Fetch all source content and ingest into LightRAG via a PAS CLI pipeline.

**Seed sources (priority order):**

| Source | Content | Volume |
|--------|---------|--------|
| Official Hermes docs | Full docs site | ~30 pages |
| Tips & Best Practices | `hermes-agent.nousresearch.com/docs/guides/tips/` | 1 page |
| Learning Path | `hermes-agent.nousresearch.com/docs/getting-started/learning-path` | 1 page |
| Built-in skills (72) | Name + description + use cases | 72 entries |
| Optional skills (101) | Name + description + use cases | 101 entries |
| Community skills (85) | Name + description + maturity tag | 85 entries |
| Curated SOUL.md examples | Hand-selected from Twitter/community | 15 examples |

**PAS pipeline stages:**

1. **fetch-docs**: Crawl `hermes-agent.nousresearch.com/docs` sitemap, extract markdown content per page
2. **fetch-skills**: Parse `awesome-hermes-skills` README + official built-in/optional skill manifests, emit structured JSON per skill
3. **fetch-soul-examples**: Read curated SOUL.md corpus from `seed-data/soul-examples/`
4. **ingest**: For each document, `POST /ingest` to running backend

**Key files:**
- `pipeline/pipeline.yaml` — PAS CLI pipeline definition
- `pipeline/stages/fetch-docs.py` — doc crawler
- `pipeline/stages/fetch-skills.py` — skill catalog parser
- `pipeline/stages/ingest.py` — LightRAG ingestion client
- `seed-data/soul-examples/*.md` — 15 curated SOUL.md examples (hand-authored)

**Validation gate:** after ingestion, query the backend with a known test case:
```
goal: "I want Hermes to monitor my email and summarize daily"
skills: []
soul_md: ""
```
Expected response references: gateway setup, email skill, cron configuration, SOUL.md communication section.

---

### Phase 3 — Hermes Skill (SKILL.md)

Write the installable SKILL.md that connects user → backend.

**SKILL.md frontmatter:**
```yaml
---
name: guide
description: Personalized coaching for getting more out of Hermes — SOUL.md, skills, and workflow
version: 0.1.0
author: [your handle]
license: MIT

metadata:
  hermes:
    tags: [Coaching, Setup, SOUL.md, Skills, Onboarding]

required_environment_variables:
  - name: HERMES_GUIDE_URL
    prompt: "hermes-guide API URL"
    help: "Hosted at https://hermes-guide.fly.dev — or self-host"
    required_for: "coaching API access"
  - name: HERMES_GUIDE_API_KEY
    prompt: "Your hermes-guide API key"
    help: "Get one free at https://github.com/[your-org]/hermes-guide"
    required_for: "authentication"
---
```

**Skill instruction body (what the agent does):**
1. Read `~/.hermes/soul.md` (or note if missing)
2. List files in `~/.hermes/skills/` to get installed skills
3. Ask user: "What are you trying to accomplish with Hermes today?"
4. Assemble JSON payload: `{soul_md, skills_list, goal}`
5. `curl -s -X POST $HERMES_GUIDE_URL/query -H "Authorization: Bearer $HERMES_GUIDE_API_KEY" -H "Content-Type: application/json" -d <payload>`
6. Parse and present the response as structured recommendations:
   - **SOUL.md gaps** — sections missing or weak for the stated goal
   - **Recommended skills** — what to install, in priority order, with rationale
   - **Quick wins** — one or two things to try in the next 10 minutes

**Key file:**
- `skill/guide.md` — the installable SKILL.md

**Test protocol:**
- Run against local backend
- Test three personas: new user (empty setup), intermediate (5 skills, basic SOUL.md), advanced (15 skills, rich SOUL.md)
- Verify response quality and specificity for each

---

### Phase 4 — Deploy & Distribute

Get the backend live and the skill installable from a public URL.

**Tasks:**
- [ ] Deploy backend to Fly.io (`fly launch` from `backend/`)
- [ ] Set production secrets via `fly secrets set`
- [ ] Verify `POST /query` returns valid responses at production URL
- [ ] Host `guide.md` at a stable public URL (GitHub raw or custom domain)
- [ ] Write `README.md`:
  - One-line description
  - Install command: `hermes skills install https://raw.githubusercontent.com/.../guide.md`
  - What it does (screenshot or example output)
  - Self-hosting instructions (Docker Compose)
- [ ] Create GitHub release tagging v0.1.0

**Fly.io config:**
- `fly.toml` in `backend/`
- 1x shared-cpu-1x (sufficient for LightRAG inference)
- Persistent volume for graph storage (`/data`)
- Health check on `GET /health`

---

## Acceptance Criteria

### Functional
- [ ] `/guide` skill installs in one command from a public URL
- [ ] Skill correctly reads user's SOUL.md and skills list
- [ ] Backend returns coaching response in < 5 seconds
- [ ] Response quality: given an empty setup + stated goal, returns ≥ 3 specific, actionable recommendations grounded in the knowledge graph
- [ ] Response quality: given a rich setup, identifies gaps the user hasn't noticed
- [ ] Ingestion pipeline runs end-to-end via `pas run pipeline/pipeline.yaml`

### Non-Functional
- [ ] Backend deployed and reachable at production URL
- [ ] `LIGHTRAG_API_KEY` auth on all endpoints (no public write access)
- [ ] No secrets committed to git (`.envrc` in `.gitignore`)
- [ ] README has install command, example output, self-hosting path
- [ ] Docker Compose works for local self-hosting (`make up`)

### Quality Gate
- [ ] Test persona "new user" → useful recommendations, not generic advice
- [ ] Test persona "advanced user" → identifies actual gaps, not obvious ones
- [ ] Knowledge graph contains all 258+ skills as queryable entities

---

## Technical Considerations

### LightRAG Query Construction
The `/query` endpoint should construct the LightRAG query from the user payload, not expose raw LightRAG params. Example:
```python
query = f"""
User goal: {payload.goal}
Currently installed skills: {', '.join(payload.skills_list) or 'none'}
SOUL.md present: {'yes' if payload.soul_md else 'no'}

Given this setup, what specific skills should they add, what SOUL.md sections are missing or weak, and what are the highest-impact next actions?
"""
```
Use `mode="hybrid"` in LightRAG query for best results (graph + vector).

### SOUL.md Privacy
Users paste their SOUL.md into the API. This may contain personal preferences, work context, or sensitive goals. The backend must:
- Not log request bodies
- Not store SOUL.md content beyond the request lifecycle
- Document this clearly in the README

### Skill Versioning
SKILL.md should be versioned. Users who install via URL get the latest — use a versioned URL pattern (`/v1/guide.md`) to allow breaking changes without breaking existing installs.

### Incremental Graph Updates
When community patterns are added later (e.g., popular Twitter SOUL.md examples), use `POST /ingest` — LightRAG set-merging handles this without full re-index. Schedule via Hermes cron or manual trigger.

---

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| LightRAG response quality poor on first query | Medium | Test with known good queries before launch; tune system prompt |
| SOUL.md privacy concerns deter adoption | Low-Medium | Clear no-logging policy in README; offer self-hosting |
| Fly.io cold starts slow first response | Low | Keep 1 machine always-on (min_machines_running = 1) |
| awesome-hermes-skills catalog structure changes | Low | Pin to a specific commit SHA in pipeline |
| Users don't have HERMES_GUIDE_URL/key friction | Medium | Make the hosted URL the default; key is optional for self-hosted |

---

## Beads Issues

Create these issues in order. Issues 2–4 can parallelize after Issue 1 closes.

```
Issue 1: Set up LightRAG FastAPI backend with Docker and Makefile
Issue 2: PAS pipeline — fetch and ingest official Hermes docs (depends: 1)
Issue 3: PAS pipeline — fetch and ingest 258+ skills catalog (depends: 1)
Issue 4: Curate 15 SOUL.md seed examples corpus (no dependency — manual work)
Issue 5: Write and test guide.md SKILL.md (depends: 1, 2, 3)
Issue 6: Deploy backend to Fly.io (depends: 5)
Issue 7: Write README and publish v0.1.0 (depends: 6)
```

---

## Future Considerations

- **Feedback loop:** users can submit their SOUL.md patterns via GitHub Issues (label: `seed-contribution`). Manual review → `POST /ingest`. Keep it human-curated for quality.
- **Name change:** `hermes-guide` is a placeholder. Revisit when distribution is live and community feedback arrives.
- **Leaderboard / popular setups:** aggregate anonymized skill combinations by goal type (opt-in) and surface "most common setup for X" answers.
- **Skill tap:** once the project has traction, submit to the official awesome-hermes-skills catalog.

---

## Sources & References

### Origin
- **Research document:** [research.md](../../research.md) — market research + demand validation (2026-07-02)
  - Key decisions carried forward: niche is unoccupied (high confidence), curl-via-terminal is the HTTP mechanism, LightRAG set-merging enables continuous ingestion

### Hermes Documentation
- [Creating Skills](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills) — SKILL.md frontmatter schema, `required_environment_variables`, terminal tool pattern
- [Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) — install mechanism, `~/.hermes/skills/` directory
- [Tips & Best Practices](https://hermes-agent.nousresearch.com/docs/guides/tips/) — seed data source
- [Learning Path](https://hermes-agent.nousresearch.com/docs/getting-started/learning-path) — seed data source

### Community
- [awesome-hermes-skills](https://github.com/ZeroPointRepo/awesome-hermes-skills) — 258+ skills catalog (seed data + competitive landscape)
- [Super Hermes](https://github.com/Cranot/super-hermes) — closest prior art (code analysis only, not coaching)

### Demand Signals
- [Prajwal Tomar SOUL.md tweet](https://x.com/PrajwalTomar_/status/2066497450358272493) — viral "write my SOUL.md" thread
- [TfTHacker tutorial demand](https://x.com/TfTHacker/status/2043549531212525852) — explicit community ask for practical guidance

### Technical
- [LightRAG GitHub](https://github.com/HKUDS/LightRAG) — REST API, Delta Index, ingestion endpoints
- [LightRAG paper (EMNLP 2025)](https://arxiv.org/abs/2410.05779) — set-merging incremental ingestion
