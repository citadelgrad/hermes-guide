# hermes-guide Deployment Runbook

## Prerequisites

- Fly.io account + CLI installed: `brew install flyctl`
- Authenticated: `fly auth login`
- OpenAI API key (for LightRAG embeddings + LLM)
- Working directory: `backend/` inside this repo

## First Deploy (order matters — do not skip steps)

### Step 1: Create the volume BEFORE launching

```bash
cd backend/
fly volumes create lightrag_data --region sjc --size 10
```

This MUST happen before `fly launch`. The volume needs to exist before the mount is configured.

### Step 2: Launch without deploying

```bash
fly launch --no-deploy
```

When prompted:
- App name: `hermes-guide` (or your preferred name)
- Region: `sjc` (or nearest)
- **Say NO to deploying** — we set secrets first

### Step 3: Set production secrets

```bash
fly secrets set \
  HERMES_GUIDE_ADMIN_TOKEN="$(openssl rand -hex 32)" \
  GEMINI_API_KEY="sk-..." \
  LIGHTRAG_DATA_DIR="/data" \
  EMBEDDING_RATE_LIMIT_DELAY="0" \
  MAX_ASYNC="2"
```

**CRITICAL:** Never commit these values. Never put `HERMES_GUIDE_ADMIN_TOKEN` in the README or anywhere public. Verify with `fly secrets list` (values are redacted).

### Step 4: First deploy — MUST use --ha=false

```bash
fly deploy --ha=false
```

**Why `--ha=false`:** Fly.io defaults to 2 machines for high availability. With only 1 volume, the second machine cannot mount it and crashes immediately. `--ha=false` deploys exactly 1 machine.

### Step 5: Verify

```bash
fly status

# Should return 200
curl -s https://hermes-guide.fly.dev/health

# Should return 200 (LightRAG initialized)
curl -s https://hermes-guide.fly.dev/ready

# Test query — should return recommendations JSON (no auth required)
curl -s -X POST https://hermes-guide.fly.dev/query \
  -H "Content-Type: application/json" \
  -d '{"goal": "I want Hermes to help me review code", "skills_list": [], "soul_md": ""}'
```

## Go/No-Go Checklist (run before announcing to users)

- [ ] `/health` returns 200
- [ ] `/ready` returns 200
- [ ] `POST /query` with test payload returns >=1 recommendation in < 5s (no auth needed)
- [ ] `POST /ingest` with no token -> 403 (graph poisoning prevented)
- [ ] `POST /ingest` with ADMIN_TOKEN -> 202 (admin ingest works)
- [ ] `fly secrets list` shows `HERMES_GUIDE_ADMIN_TOKEN` (value redacted — good)
- [ ] `git log -p | grep -i admin_token` returns nothing (token never committed)
- [ ] `EMBEDDING_RATE_LIMIT_DELAY=0` confirmed in secrets

## Seed the Production Knowledge Graph

After first successful deploy, run the ingestion pipelines against production:

```bash
# HERMES_GUIDE_URL and HERMES_GUIDE_ADMIN_TOKEN are written to .envrc by make provision.
# direnv loads them automatically. Or export manually:

# Run docs pipeline
python pipeline/run-docs-pipeline.py

# Run skills pipeline
python pipeline/run-skills-pipeline.py
```

Note: Seeding takes ~2.5 hours with MAX_ASYNC=8 (set this env var during seeding, reset to 2 after).

## Subsequent Deploys

```bash
cd backend/
fly deploy  # --ha=false only needed on first deploy
```

## Machine Size Reference

| Use case | Machine type | Why |
|----------|-------------|-----|
| Production (default) | `performance-1x` (1 CPU, 1gb) | Entity extraction needs sustained CPU |
| Seeding run | `performance-2x` (2 CPU, 2gb) | `fly scale vm performance-2x --memory 2048` during seed |
| After seeding | Back to default | `fly scale vm performance-1x --memory 1024` |
