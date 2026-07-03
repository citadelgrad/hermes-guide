# hermes-guide

Personalized [Hermes Agent](https://hermes-agent.nousresearch.com) setup coaching, powered by a LightRAG knowledge graph.

## What it does

`/guide` is a Hermes skill that reads your SOUL.md and installed skills, asks what you're trying to accomplish, then returns specific recommendations — which SOUL.md sections are missing, which skills to install, what to do in the next 10 minutes. It's backed by a knowledge graph built from the official Hermes docs, 258+ skills catalog, and curated SOUL.md examples. Unlike static tutorials, it looks at YOUR actual setup.

## Install

```bash
hermes skills install https://raw.githubusercontent.com/citadelgrad/hermes-guide/main/skill/v1/guide.md
```

Then set two environment variables (Hermes will prompt you on first run):

- `HERMES_GUIDE_URL` — `https://hermes-guide.fly.dev` (hosted, free) or your self-hosted URL
- `HERMES_GUIDE_QUERY_TOKEN` — get one by opening an issue: [Request a token](https://github.com/citadelgrad/hermes-guide/issues/new?title=Token+request&body=Please+share+a+query+token)

## Usage

In any Hermes session:

```
/guide
```

Hermes will ask what you're trying to accomplish, then return:

- **SOUL.md gaps** — sections that are missing or weak for your goal
- **Skills to install** — in priority order, with rationale
- **Quick wins** — 1-2 things to do right now

## Example output

**You:** `/guide`

**Hermes:** What are you trying to accomplish with Hermes? (Be specific — e.g. "help me review code faster" or "automate my email triage")

**You:** help me ship code faster and catch bugs earlier

---

**SOUL.md**

Your SOUL.md is missing a Workflow section. This is the highest-priority gap for your goal — without it, Hermes doesn't know your branching strategy, how you handle reviews, or what "done" means for you. Add this:

```
## Workflow

I work in short-lived feature branches (1-2 days max). PRs go through one reviewer before merge.
I run tests locally before pushing. Blocking bugs > style issues — flag them separately.
I use conventional commits. Deploys are manual but CI must be green first.
```

Your Communication section exists but is thin. Add explicit failure preferences:

```
When something is wrong, say so directly. Don't soften it. List blocking issues first,
then non-blocking. If you're not sure whether something is a bug, say so — don't guess.
```

---

**Skills to install**

1. **hermes-tdd** — Install this because your goal is catching bugs earlier; TDD workflows surface defects at write-time, not review-time.
   ```bash
   hermes skills install https://github.com/citadelgrad/hermes-tdd
   ```

2. **hermes-code-review** — Install this because it codifies your review checklist so Hermes can flag issues against your actual standards, not generic ones.
   ```bash
   hermes skills install https://github.com/citadelgrad/hermes-code-review
   ```

3. **hermes-git** — Install this because it adds commit message linting, branch hygiene checks, and PR description generation — all of which reduce review cycle time.
   ```bash
   hermes skills install https://github.com/citadelgrad/hermes-git
   ```

---

**Quick wins**

1. Add the Workflow section to `~/.hermes/soul.md` right now — it takes 5 minutes and immediately improves every code-related response Hermes gives you.
2. Run `hermes skills install https://github.com/citadelgrad/hermes-tdd` and open the next file you're about to modify. Ask Hermes to write a failing test for the behavior you're adding before you write the code.

## Self-hosting

```bash
git clone https://github.com/citadelgrad/hermes-guide
cd hermes-guide
cp backend/.envrc.example .envrc
# Edit .envrc — set HERMES_GUIDE_QUERY_TOKEN, HERMES_GUIDE_ADMIN_TOKEN, OPENAI_API_KEY
make up
```

See [docs/deploy.md](docs/deploy.md) for Fly.io production deployment.

## Privacy

SOUL.md content is processed in-memory only. The API does not log request bodies, does not store SOUL.md content beyond the request lifecycle, and does not pass it to any LLM (the hosted instance uses `only_need_context: true` — raw graph context is returned for your local Hermes session to synthesize). Validation errors return field locations only — not submitted values.

For maximum privacy, self-host.

## Contributing

**SOUL.md examples:** Open an issue with the `seed-contribution` label to share a SOUL.md pattern you've found useful. Quality > quantity — we review manually before ingesting.

**Bug reports and feature requests:** GitHub Issues.

## License

MIT
