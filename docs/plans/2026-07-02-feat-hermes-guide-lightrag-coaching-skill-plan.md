---
title: "feat: Build hermes-guide — LightRAG-Powered Hermes Coaching Skill"
type: feat
status: active
date: 2026-07-02
origin: research.md
deepened: 2026-07-02
---

# feat: Build hermes-guide — LightRAG-Powered Hermes Coaching Skill

## Enhancement Summary

**Deepened:** 2026-07-02  
**Research agents run:** 11 (architecture, security, agent-native, performance, SKILL.md, Fly.io, ingestion pipeline, FastAPI privacy, LightRAG FastAPI best practices, simplicity, spec-flow)

### Key Improvements

1. **Two-token auth model** — `HERMES_GUIDE_QUERY_TOKEN` (users, distributed) and `HERMES_GUIDE_ADMIN_TOKEN` (operator only, never in README). Single-key design would allow any user to poison the knowledge graph.
2. **Shell injection eliminated** — `jq -n --arg` for all string fields + tempfile pattern in SKILL.md curl payload. Newlines, backticks, and quotes in SOUL.md content are fully safe.
3. **Latency target met** — `only_need_context: true` + pre-supplied keywords drops LightRAG query latency from 4–8s to 500–800ms. The 5s acceptance criterion is now achievable without heroics.
4. **Seeding parallelism** — Default `MAX_ASYNC=1` means 22+ hours to seed 288 documents. `MAX_ASYNC=8` during seeding only (reset to 2 at runtime) brings this to ~2.5 hours.
5. **Fly.io first-deploy sequence** — `fly deploy --ha=false` is mandatory on first deploy; the default 2-machine HA with 1 volume causes a crash. `performance-1x` (not `shared-cpu-1x`) required to avoid CPU credit exhaustion during entity extraction.
6. **Pydantic v2 leakage** — `exc.errors()` now includes an `"input"` key with submitted values in validation error dicts. Custom exception handler must strip it. `ConfigDict(hide_input_in_errors=True)` + `SecretStr` + `Field(repr=False)` for SOUL.md field model.
7. **Ingestion idempotency** — LightRAG does NOT auto-skip re-processed documents. Must call `rag.doc_status.get_doc_by_content_hash()` before each `ainsert()`.

### New Considerations Discovered

- Docker Compose must bind to `127.0.0.1`, not `0.0.0.0`, to prevent LAN exposure
- `EMBEDDING_RATE_LIMIT_DELAY` defaults to 0.7s (free-tier throttle) — must set to 0 in production
- Do NOT pre-chunk documents before passing to LightRAG — it always chunks internally; attempting to bypass was explicitly rejected in the issue tracker
- Uvicorn never logs request bodies by default (structurally impossible — 5-field access log tuple); the logging risk is application code calling `exc.body` in exception handlers
- No turnkey FastAPI PII middleware library exists; compose structlog processor + Pydantic model patterns

---

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
        ├── builds: JSON payload via jq (injection-safe)
        ├── POSTs via curl: { soul_md, skills_list, goal } → hermes-guide API
        └── formats and presents: personalized recommendations

hermes-guide API (Fly.io, performance-1x)
  ├── FastAPI + LightRAG (Python, uv)
  ├── POST /query  → coaching (HERMES_GUIDE_QUERY_TOKEN, any user)
  ├── POST /ingest → admin-only (HERMES_GUIDE_ADMIN_TOKEN, operator only)
  ├── GET  /health → liveness check
  ├── GET  /ready  → readiness check (LightRAG initialized)
  └── Knowledge graph on persistent Fly.io volume (/data)
       ├── Official Hermes docs (crawled via USP + trafilatura)
       ├── 258+ skills catalog (built-in + optional + community)
       ├── Tips & Best Practices (official)
       ├── Learning Path (official)
       └── Curated SOUL.md patterns (15 hand-selected examples)
```

**Auth model:** Two separate bearer tokens. `HERMES_GUIDE_QUERY_TOKEN` is distributed to users (README, install instructions). `HERMES_GUIDE_ADMIN_TOKEN` is operator-only — set via `fly secrets set`, never committed or documented publicly. `/ingest` accepts only the admin token, preventing graph poisoning.

**Why LightRAG over plain RAG:** skills, SOUL.md sections, and context files are relational. "To build an autonomous coding agent, you need skill X, which pairs with skill Y, and requires configuring SOUL.md section Z" is multi-hop reasoning vector search alone can't surface. LightRAG's Delta Index also allows continuous ingestion without re-indexing. With `only_need_context: true`, query latency is 500–800ms — the LLM synthesis call is eliminated from the hot path; the Hermes Claude session handles synthesis instead.

---

## Implementation Phases

### Phase 1 — Backend Foundation

Stand up the LightRAG + FastAPI server locally and in production.

**Tasks:**
- [ ] Initialize Python project with `uv init` in `backend/`
- [ ] Add dependencies: `lightrag-hku`, `fastapi`, `uvicorn`, `slowapi`
- [ ] Implement four endpoints:
  - `POST /query` — accepts `{soul_md, skills_list, goal, max_results?}`, returns coaching JSON
  - `POST /ingest` — admin-only, accepts `{text, source_url}`, returns 202 + background task
  - `GET /health` — liveness (always 200 if process is alive)
  - `GET /ready` — readiness (200 only after LightRAG graph is initialized)
- [ ] Two-token auth middleware:
  - `/query` validates `HERMES_GUIDE_QUERY_TOKEN`
  - `/ingest` validates `HERMES_GUIDE_ADMIN_TOKEN`
- [ ] Rate limiting via slowapi on `/query` (e.g., 60/minute per token)
- [ ] Makefile targets: `make up`, `make down`, `make logs`, `make status`
- [ ] Docker Compose on a non-default port (e.g., `7842`), binding to `127.0.0.1` only
- [ ] `.envrc` for local secrets — never committed
- [ ] Validate: local `curl -X POST /query` returns a LightRAG response

**Response JSON schema:**
```json
{
  "recommendations": [
    {"category": "soul_md_gap", "text": "...", "priority": 1},
    {"category": "skill", "text": "...", "priority": 2},
    {"category": "quick_win", "text": "...", "priority": 1}
  ],
  "graph_nodes_used": 12,
  "query_mode": "hybrid"
}
```

**LightRAG query construction:**
```python
query = f"""
User goal: {payload.goal}
Currently installed skills: {', '.join(payload.skills_list) or 'none'}
SOUL.md present: {'yes' if payload.soul_md else 'no'}

Given this setup, what specific skills should they add, what SOUL.md sections
are missing or weak, and what are the highest-impact next actions?
"""
result = await rag.aquery(
    query,
    param=QueryParam(
        mode="mix",               # mix = hybrid graph + naive vector; official default as of PR #3287 (June 2026)
        only_need_context=True,   # eliminates LightRAG's LLM call; Hermes synthesizes
        top_k=payload.max_results or 5,
    )
)
```

**Ingestion as BackgroundTask:**
```python
@app.post("/ingest", status_code=202)
async def ingest(payload: IngestRequest, background_tasks: BackgroundTasks, ...):
    background_tasks.add_task(run_ingest, payload.text, payload.source_url)
    return {"status": "accepted"}
```

**Pydantic model for SOUL.md content (maximum privacy):**
```python
from pydantic import BaseModel, SecretStr, ConfigDict, Field

class QueryRequest(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    goal: str
    skills_list: list[str] = []
    soul_md: SecretStr = Field(default=SecretStr(""), repr=False)
    max_results: int = 5

    def get_soul_content(self) -> str:
        return self.soul_md.get_secret_value()
```

**Custom validation exception handler (strips Pydantic v2 `"input"` key):**
```python
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    safe_errors = [
        {k: v for k, v in err.items() if k not in ("input", "url", "ctx")}
        for err in exc.errors()
    ]
    logger.warning("Validation error on %s %s", request.method, request.url.path, exc_info=False)
    return JSONResponse(status_code=422, content={"detail": safe_errors})
```

**Key files:**
- `backend/main.py` — FastAPI app, routes, exception handlers
- `backend/pyproject.toml` — uv-managed dependencies
- `docker-compose.yml` — backend service on `127.0.0.1:7842`
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

**Library choices (from research):**
- **Crawling:** `ultimate-sitemap-parser` (USP) v1.8.1 — handles nested sitemaps, broken XML gracefully
- **HTML → markdown:** `trafilatura` with `include_tables=True, favor_recall=True` — strips boilerplate, preserves code blocks
- **README table parsing:** `md-spreadsheet-parser` — extracts skill catalog rows from awesome-hermes-skills tables
- **Retry:** `tenacity` with `wait_exponential_jitter` — jitter prevents thundering herd on rate limit errors
- **Concurrency during ingest:** `asyncio.Semaphore(8)` 

**CRITICAL: Do not pre-chunk.** LightRAG always chunks documents internally. The architecture for chunking is an intentional invariant — bypass attempts were explicitly rejected in the LightRAG issue tracker. Pass full document text to `ainsert()`.

**Idempotency pattern (LightRAG does NOT skip re-processed docs automatically):**
```python
content_hash = hashlib.sha256(text.encode()).hexdigest()
existing = await rag.doc_status.get_doc_by_content_hash(content_hash)
if existing and existing.status == DocStatus.PROCESSED:
    logger.info("Skipping already-processed doc: %s", source_url)
    return

await rag.ainsert(text)
```

**Dead Letter Queue for failed ingestions:**
```python
# pipeline/stages/ingest.py
failed = []
for doc in documents:
    try:
        await ingest_with_retry(doc)
    except Exception as e:
        failed.append({"url": doc.url, "error": str(e)})

if failed:
    Path("pipeline/dlq.jsonl").write_text(
        "\n".join(json.dumps(f) for f in failed)
    )
```

Reprocess DLQ with: `pas run pipeline/pipeline.yaml --stage=ingest --input=pipeline/dlq.jsonl`

**Seeding concurrency settings (reset to runtime values after seeding completes):**

| Variable | Seeding | Runtime |
|----------|---------|---------|
| `MAX_ASYNC` | 8 | 2 |
| `MAX_PARALLEL_INSERT` | 4 | 2 |
| `EMBEDDING_FUNC_MAX_ASYNC` | 4 | 2 |
| `EMBEDDING_RATE_LIMIT_DELAY` | 0 | 0 |

**PAS pipeline stages:**

1. **discover-urls** — USP crawl of `hermes-agent.nousresearch.com/docs` sitemap → URL list
2. **fetch-docs** — trafilatura extract per URL → markdown files
3. **extract-markdown** — trafilatura HTML → markdown for each fetched page
4. **parse-readme** — md-spreadsheet-parser on awesome-hermes-skills README → skill JSON per row
5. **load-soul-files** — read `seed-data/soul-examples/*.md` → document objects
6. **ingest-to-lightrag** — idempotency check + `ainsert()` with Semaphore(8) + DLQ
7. **validate** — check DocStatus counts + NetworkX on graphml (verify node/edge/orphan rates)

**Key files:**
- `pipeline/pipeline.yaml` — PAS CLI pipeline definition
- `pipeline/stages/discover-urls.py` — USP sitemap crawler
- `pipeline/stages/fetch-docs.py` — trafilatura extractor
- `pipeline/stages/parse-readme.py` — skill catalog parser
- `pipeline/stages/ingest.py` — LightRAG ingestion client with idempotency + DLQ
- `pipeline/stages/validate.py` — post-ingest graph health check
- `seed-data/soul-examples/*.md` — 15 curated SOUL.md examples (hand-authored)

**Validation gate:**
```bash
# After ingestion, query with a known test case:
curl -s -X POST $HERMES_GUIDE_URL/query \
  -H "Authorization: Bearer $HERMES_GUIDE_QUERY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"goal": "I want Hermes to monitor my email and summarize daily", "skills_list": [], "soul_md": ""}'

# Expected response references: gateway setup, email skill, cron configuration, SOUL.md communication section
```

---

### Phase 3 — Hermes Skill (SKILL.md)

Write the installable SKILL.md that connects user → backend.

**SKILL.md frontmatter (complete, validated against Hermes schema):**
```yaml
---
name: guide
description: Personalized Hermes coaching — SOUL.md gaps, skill recommendations, quick wins
version: 1.0.0
author: citadelgrad
license: MIT
platforms: [macos, linux]

metadata:
  hermes:
    tags: [coaching, setup, soul-md, skills, onboarding, productivity]
    category: productivity
    requires_toolsets: [terminal]
    config:
      - key: guide.max_results
        description: Number of recommendations to return
        default: "5"
        prompt: "Max recommendations"

required_environment_variables:
  - name: HERMES_GUIDE_URL
    prompt: "hermes-guide API URL"
    help: "Hosted at https://hermes-guide.fly.dev — or self-host: https://github.com/citadelgrad/hermes-guide"
    required_for: "coaching API access"
  - name: HERMES_GUIDE_QUERY_TOKEN
    prompt: "Your hermes-guide query token"
    help: "Get one free at https://github.com/citadelgrad/hermes-guide"
    required_for: "authentication"
---
```

**Skill instruction body (what the agent does):**

1. **Preflight check** — verify `HERMES_GUIDE_URL` and `HERMES_GUIDE_QUERY_TOKEN` are set; surface clear error if missing
2. **Read SOUL.md** — `cat ~/.hermes/soul.md` or note "not found" if absent (graceful — many users haven't written one yet)
3. **List installed skills** — `ls ~/.hermes/skills/` to get installed skill names
4. **Ask the user** — "What are you trying to accomplish with Hermes today?"
5. **Assemble JSON payload via jq** (injection-safe):

```bash
SOUL=$(cat ~/.hermes/soul.md 2>/dev/null || echo "")
SKILLS=$(ls ~/.hermes/skills/ 2>/dev/null | tr '\n' ',' | sed 's/,$//')
MAX=${HERMES_GUIDE_MAX_RESULTS:-5}

PAYLOAD=$(jq -n \
  --arg soul    "$SOUL" \
  --arg skills  "$SKILLS" \
  --arg goal    "$USER_GOAL" \
  --argjson max "$MAX" \
  '{soul_md: $soul, skills_list: ($skills | split(",") | map(select(length > 0))),
    goal: $goal, max_results: $max}')

RESPONSE=$(curl -fsSL -X POST "$HERMES_GUIDE_URL/query" \
  -H "Authorization: Bearer $HERMES_GUIDE_QUERY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")
```

6. **Parse and present** the response as structured recommendations:
   - **SOUL.md gaps** — sections missing or weak for the stated goal
   - **Recommended skills** — what to install, in priority order, with rationale
   - **Quick wins** — one or two things to try in the next 10 minutes

**Key notes for implementation:**
- Use `-fsSL` curl flags: `-f` fails on HTTP errors, `-s` silent, `-S` show errors, `-L` follow redirects
- `jq -n --arg` handles all quoting — newlines, backticks, and double-quotes in SOUL.md are safe
- Missing SOUL.md is a coaching opportunity, not an error: respond with soul.md creation guidance

**Key file:**
- `skill/guide.md` — the installable SKILL.md

**Test protocol:**
- Run against local backend first
- Test three personas: new user (empty setup), intermediate (5 skills, basic SOUL.md), advanced (15 skills, rich SOUL.md)
- Verify response quality and specificity for each

---

### Phase 4 — Deploy & Distribute

Get the backend live and the skill installable from a public URL.

**Fly.io first-deploy sequence (order matters):**

```bash
cd backend/

# 1. Create volume BEFORE launch (launch prompts will ask; say no to deploy yet)
fly volumes create lightrag_data --region sjc --size 10

# 2. Launch without deploying
fly launch --no-deploy

# 3. Set production secrets
fly secrets set \
  HERMES_GUIDE_QUERY_TOKEN="$(openssl rand -hex 32)" \
  HERMES_GUIDE_ADMIN_TOKEN="$(openssl rand -hex 32)" \
  EMBEDDING_RATE_LIMIT_DELAY=0

# 4. Deploy with HA disabled (MANDATORY on first deploy — 2 machines, 1 volume = crash)
fly deploy --ha=false

# 5. Verify
fly status
curl -s https://hermes-guide.fly.dev/health
```

**fly.toml:**
```toml
app = "hermes-guide"
primary_region = "sjc"

[build]
  dockerfile = "Dockerfile"

[[vm]]
  cpu_kind = "performance"   # shared-cpu-1x exhausts burst credits during entity extraction
  cpus = 1
  memory = "512mb"           # minimum safe; upgrade to 2gb if OOM during seeding

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "suspend"
  auto_start_machines = true
  min_machines_running = 1

  [[http_service.checks]]
    grace_period = "15s"
    interval = "30s"
    method = "GET"
    path = "/health"
    timeout = "10s"

[[mounts]]
  source = "lightrag_data"
  destination = "/data"
  initial_size = "10gb"
  snapshot_retention = 5
  auto_extend_size_threshold = 80
  auto_extend_size_increment = "5gb"
  auto_extend_size_limit = "50gb"
```

**Remaining deploy tasks:**
- [ ] Verify `POST /query` returns valid responses at production URL
- [ ] Host `guide.md` at stable public URL (GitHub raw: `https://raw.githubusercontent.com/citadelgrad/hermes-guide/main/skill/guide.md`)
- [ ] Write `README.md`:
  - Install command: `hermes skills install https://raw.githubusercontent.com/citadelgrad/hermes-guide/main/skill/guide.md`
  - What it does + example output
  - How to get a query token (free, from GitHub)
  - Self-hosting instructions
  - Privacy policy section (see below)
- [ ] Create GitHub release tagging v0.1.0

**Go/No-Go checklist before public announcement:**
- [ ] `/health` returns 200
- [ ] `/ready` returns 200 (LightRAG initialized)
- [ ] `POST /query` with test payload returns ≥ 3 recommendations in < 3s
- [ ] `POST /ingest` with `HERMES_GUIDE_QUERY_TOKEN` returns 403 (wrong token rejects)
- [ ] `POST /ingest` with `HERMES_GUIDE_ADMIN_TOKEN` returns 202
- [ ] `EMBEDDING_RATE_LIMIT_DELAY=0` confirmed in fly secrets
- [ ] knowledge graph contains ≥ 258 skill nodes (validate query)
- [ ] README privacy section published
- [ ] No admin token in README, git history, or any public location

---

## Acceptance Criteria

### Functional
- [ ] `/guide` skill installs in one command from a public URL
- [ ] Skill correctly reads user's SOUL.md and skills list
- [ ] Backend returns coaching response in < 5 seconds (target: < 2s with `only_need_context: true`)
- [ ] Response quality: given an empty setup + stated goal, returns ≥ 3 specific, actionable recommendations grounded in the knowledge graph
- [ ] Response quality: given a rich setup, identifies gaps the user hasn't noticed
- [ ] Ingestion pipeline runs end-to-end via `pas run pipeline/pipeline.yaml`

### Non-Functional
- [ ] Backend deployed and reachable at production URL
- [ ] Two-token auth on all endpoints (query token ≠ admin token)
- [ ] No secrets committed to git (`.envrc` in `.gitignore`)
- [ ] Docker Compose binds to `127.0.0.1` only
- [ ] README has install command, example output, self-hosting path, and privacy section
- [ ] Docker Compose works for local self-hosting (`make up`)

### Quality Gate
- [ ] Test persona "new user" → useful recommendations, not generic advice
- [ ] Test persona "advanced user" → identifies actual gaps, not obvious ones
- [ ] Knowledge graph contains all 258+ skills as queryable entities
- [ ] Canary sentinel test passes: SOUL.md content never appears in server logs

---

## Security

### Two-Token Auth (Critical)
Single-key design allows any user with a query token to call `/ingest` and poison the knowledge graph. The fix is structural: two separate tokens with no overlap.

| Token | Endpoint | Distribution |
|-------|----------|-------------|
| `HERMES_GUIDE_QUERY_TOKEN` | `/query` | README, GitHub, free to users |
| `HERMES_GUIDE_ADMIN_TOKEN` | `/ingest` | `fly secrets set` only, never published |

Use `secrets.compare_digest` (not `==`) for token comparison to prevent timing attacks:
```python
import secrets
if not secrets.compare_digest(credentials.credentials, HERMES_GUIDE_QUERY_TOKEN):
    raise HTTPException(status_code=401, ...)
```

### SOUL.md Privacy (C2 Critical)
SOUL.md content reaches the LLM provider API unless `only_need_context: true` is used. With `only_need_context: true`, LightRAG returns raw graph context without an LLM synthesis call — the Hermes session handles synthesis locally. This is the primary privacy mitigation.

**Application-level guarantees:**
- Uvicorn access log: structurally cannot contain request bodies (5-field tuple)
- Exception handlers: strip Pydantic v2 `"input"` key and never read `exc.body`
- `SecretStr` + `ConfigDict(hide_input_in_errors=True)` on the request model
- structlog processor redacts `content` and `soul_md` keys before any log emission
- No request body logging in middleware (never call `await request.body()` in middleware)

**Infrastructure caveat (document in README):** Application-level guarantees do not extend to nginx, caddy, or API gateway layers. If your self-hosted deployment logs `$request_body`, that's outside our control.

**README privacy section (accurate claim):**
> SOUL.md content is processed in-memory only. The API does not log request bodies, does not store SOUL.md content beyond the request lifecycle, and does not pass it to any LLM (the hosted instance uses `only_need_context: true`). Validation errors return field locations only — not submitted values. For maximum privacy, self-host.

### Rate Limiting
`slowapi` on `/query` at 60 requests/minute per token. `/ingest` rate limit is unnecessary (admin-only, operator controls usage).

### Docker Compose Binding
All compose services bind to `127.0.0.1:<port>`, not `0.0.0.0`. Prevents LAN exposure during local development.

---

## Technical Considerations

### LightRAG Query Construction
The `/query` endpoint constructs the LightRAG query from the user payload. Pass `only_need_context: true` to eliminate LightRAG's internal LLM synthesis call — this cuts latency from 4–8s to 500–800ms and keeps SOUL.md content from reaching an additional LLM provider.

**Critical:** `user_prompt` (the `QueryParam` field) only shapes LLM generation — it does NOT affect retrieval. Keywords that drive graph traversal must be in the query string itself or in `hl_keywords`/`ll_keywords`. Embed goal, skills, and context directly in the query string.

Use `mode="mix"` (official recommended default as of June 2026, PR #3287) — combines hybrid graph paths with naive vector search. Best for mixed queries that combine specific named entities (skills, tools) with thematic concepts (goals, domains).

Pre-supply `hl_keywords` and `ll_keywords` if possible to skip keyword extraction (saves another ~200ms):
```python
param = QueryParam(
    mode="mix",
    only_need_context=True,
    top_k=max_results,
    hl_keywords=["soul.md", "skills", "hermes", "configuration"],  # themes
    ll_keywords=skills_list,  # user's installed skills → specific entity lookup
)
```

**Lifespan handler required** (storages don't auto-initialize without it):
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await rag.initialize_storages()
    await rag.check_and_migrate_data()
    yield
    await rag.finalize_storages()

app = FastAPI(lifespan=lifespan)
```

**Streaming for production** — `mix` mode can take 15–25s on mid-size graphs. Use `StreamingResponse` to avoid client timeout while maintaining the 5s UX target (first tokens arrive quickly):
```python
@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    async def generate():
        async for chunk in await rag.aquery(query, param=QueryParam(mode="mix", stream=True)):
            yield json.dumps({"delta": chunk}) + "\n"
    return StreamingResponse(generate(), media_type="application/x-ndjson")
```

### SOUL.md Privacy
Users paste their SOUL.md into the API. Application-level mitigations (see Security section). The key structural protection is `only_need_context: true` — raw SOUL.md content is used only as query context in the Hermes session, never forwarded to an additional LLM.

### Skill Versioning
SKILL.md is versioned via `version: 1.0.0` in frontmatter. Use a versioned URL path (`/v1/guide.md`) to allow breaking changes without breaking existing installs.

### Incremental Graph Updates
When community patterns are added later, use `POST /ingest` with the admin token — LightRAG set-merging handles this without full re-index. The idempotency check (`get_doc_by_content_hash`) ensures re-running the pipeline is safe.

---

## Dependencies & Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| LightRAG response quality poor on first query | Medium | Test with known good queries before launch; tune system prompt; validate graph node count |
| SOUL.md privacy concerns deter adoption | Low-Medium | `only_need_context: true` + clear README privacy section; offer self-hosting |
| Fly.io cold start on first request after suspend | Low | `min_machines_running = 1` keeps one machine warm always |
| awesome-hermes-skills catalog structure changes | Low | Pin to specific commit SHA in pipeline; `get_doc_by_content_hash` idempotency means safe to re-run |
| seeding takes too long | Medium | `MAX_ASYNC=8` during seeding reduces ~22h → ~2.5h; run overnight |
| CPU exhaustion on `shared-cpu-1x` during entity extraction | Medium (mitigated) | `performance-1x` specified in fly.toml |
| `fly deploy` default HA crashes first deploy | High (mitigated) | `fly deploy --ha=false` in first-deploy sequence |
| Pydantic v2 `"input"` key leaks SOUL.md in 422 responses | Medium (mitigated) | Custom exception handler strips `input`, `url`, `ctx` keys |

---

## Beads Issues

Create these issues in order. Issues 2–4 can parallelize after Issue 1 closes.

```
hermes-guide-vrf: Set up LightRAG FastAPI backend with Docker and Makefile
  → Two-token auth (QUERY_TOKEN + ADMIN_TOKEN)
  → /health, /ready, /query, /ingest endpoints
  → Pydantic SecretStr model + custom exception handler
  → Docker Compose on 127.0.0.1:7842
  → slowapi rate limiting on /query

hermes-guide-5w1: Curate 15 SOUL.md seed examples corpus (no dependency — manual work)
  → Hand-select from Twitter/GitHub community examples
  → Store in seed-data/soul-examples/*.md

hermes-guide-pipeline-docs: PAS pipeline — discover and ingest official Hermes docs (depends: hermes-guide-vrf)
  → USP sitemap crawler
  → trafilatura HTML → markdown
  → Idempotency via get_doc_by_content_hash
  → Tenacity retry + DLQ

hermes-guide-pipeline-skills: PAS pipeline — parse and ingest 258+ skills catalog (depends: hermes-guide-vrf)
  → md-spreadsheet-parser on awesome-hermes-skills README
  → Batch related docs into single ainsert() calls
  → Validate node count post-ingest

hermes-guide-skill: Write and test guide.md SKILL.md (depends: hermes-guide-vrf, pipeline issues)
  → jq -n --arg payload construction
  → requires_toolsets: [terminal]
  → Preflight env var check
  → Test 3 personas

hermes-guide-deploy: Deploy backend to Fly.io (depends: hermes-guide-skill)
  → fly deploy --ha=false
  → performance-1x, 512mb
  → Seed production graph
  → Go/No-Go checklist

hermes-guide-readme: Write README and publish v0.1.0 (depends: hermes-guide-deploy)
  → Install command
  → Privacy section
  → Self-hosting instructions
```

---

## Future Considerations

- **Feedback loop:** users can submit their SOUL.md patterns via GitHub Issues (label: `seed-contribution`). Manual review → `POST /ingest` with admin token. Keep it human-curated for quality.
- **Name change:** `hermes-guide` is a placeholder. Revisit when distribution is live and community feedback arrives.
- **Leaderboard / popular setups:** aggregate anonymized skill combinations by goal type (opt-in) and surface "most common setup for X" answers.
- **Skill tap:** once the project has traction, submit to the official awesome-hermes-skills catalog.
- **upgrade path:** if `lru_cache`-style per-request caching becomes necessary (repeated identical queries), add `functools.lru_cache` on the query function before reaching for Redis.

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
- [Fly.io Docs — Machines](https://fly.io/docs/machines/) — `performance-1x`, volume pre-creation, HA deploy
- [FastAPI Exception Handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/) — custom handler patterns
- [Pydantic v2 SecretStr](https://docs.pydantic.dev/latest/concepts/types/#secret-types) — `SecretStr`, `hide_input_in_errors`
- [structlog](https://www.structlog.org/en/stable/) — processor chain for PII redaction
- [ultimate-sitemap-parser](https://github.com/mediacloud/ultimate-sitemap-parser) — USP v1.8.1
- [trafilatura](https://trafilatura.readthedocs.io/) — HTML → markdown extraction
- [tenacity](https://tenacity.readthedocs.io/) — `wait_exponential_jitter` retry
- [slowapi](https://slowapi.readthedocs.io/) — FastAPI rate limiting
