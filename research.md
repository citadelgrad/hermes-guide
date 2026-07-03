# hermes-guide: Research & Validation

> Working name. Final name TBD.

## Concept

A native Hermes Agent skill that coaches users on getting more out of Hermes. It collects the user's current setup (SOUL.md, installed skills, context files, goal) and POSTs to a hosted LightRAG backend that returns personalized recommendations.

The core insight: all existing Hermes help is generic static content (blog posts, YouTube tutorials). Users clearly want *personalized* answers — "MY SOUL.md, MY stack, MY goals." That's the gap.

---

## Market Research (deep-research workflow, 2026-07-02)

### Niche is unoccupied (high confidence)
- 85 community skills catalogued across 14 categories — zero do coaching, setup advisory, or config recommendations
- The only close prior art: **Super Hermes** (278 stars) — code analysis only, zero SOUL.md or setup guidance
- A static docs repo (OnlyTerp/hermes-optimization-guide) covers setup topics but is not an installable active-coaching skill

### Technical path is clear (high confidence)
- Skills are markdown files installable from any HTTPS URL: `hermes skills install https://example.com/SKILL.md`
- No registry approval required
- Skills POST to external backends via `curl` through the agent's terminal tool
- API keys declared via `required_environment_variables` in YAML frontmatter
- LightRAG REST API supports incremental ingestion (set-merging) — no full re-index when adding new community patterns

### LightRAG is a good fit (high confidence)
- FastAPI server with `POST /documents/text` (ingest) and `POST /query` (retrieval)
- Delta Index: new skills/SOUL.md configs/Twitter patterns integrate via set merge, not full rebuild
- Per-document LLM entity extraction cost, but no cumulative re-indexing cost

---

## Demand Validation (2026-07-02)

### SOUL.md personalization is the #1 pain point
Prajwal Tomar (high-follower account) has multiple viral tweets telling people:
> "Paste this into your Hermes session and say: 'Write my SOUL.md based on my stack and goals, pick the 3 profiles I should run first'"

People are already seeking personalized SOUL.md help — just doing it awkwardly through the agent itself.

### "Which skills should I install" is a real question
- Multiple sites publishing "Top 10 Hermes Agent Skills 2026", "Best Skills: Ranked & Reviewed"
- Official docs acknowledge: "8–12 active skills is steadier day to day" — beginners have no way to know where to start
- Static ranked lists are filling the gap, not an interactive personalized tool

### Community explicitly wants practical guidance over hype
TfTHacker (active community member):
> "We need more tutorials like this. So far we are flooded with 'BREAKING NEWS Hermes crushes OpenClaw' blah blah blah."

### Setup content volume signals massive incoming user wave
DataCamp, Geeky Gadgets, Hostinger, Substack, NxCode, DigitalApplied all published setup guides in 2026. International content (Japanese) appearing too.

---

## Architecture

```
User (Hermes session)
  └── /guide skill
        ├── collects: SOUL.md, installed skills list, context files, user's goal
        ├── POSTs to: hermes-guide API (hosted LightRAG backend)
        └── returns: personalized recommendations

LightRAG Backend
  ├── Knowledge graph seeded from:
  │   ├── Official Hermes docs + changelog
  │   ├── Community-shared SOUL.md patterns (Twitter/GitHub)
  │   ├── Curated skill combinations by use case
  │   └── Common workflow patterns
  └── Graph layer maps: skills → what they enable → what they combine with
```

**Why the graph layer matters:** skills, memory, and context files are relational — the optimal setup for "autonomous coding agent" is a graph of interconnected pieces, not a flat list of tips. Multi-hop reasoning surfaces "to do X, you need skill Y, which pairs well with context file Z."

---

## Key Sources

- [Hermes Agent docs](https://hermes-agent.nousresearch.com/docs)
- [GitHub: nousresearch/hermes-agent](https://github.com/nousresearch/hermes-agent) — 208k stars
- [awesome-hermes-skills](https://github.com/ZeroPointRepo/awesome-hermes-skills) — 85 skills, none do coaching
- [Super Hermes](https://github.com/Cranot/super-hermes) — closest prior art, code analysis only
- [Prajwal Tomar SOUL.md tweet](https://x.com/PrajwalTomar_/status/2066497450358272493)
- [TfTHacker tutorial demand tweet](https://x.com/TfTHacker/status/2043549531212525852)
- [Best Hermes Skills 2026 - EasyClaw](https://easyclaw.com/blog/knowledge/best-hermes-agent-skills/)
- [Tips & Best Practices - official docs](https://hermes-agent.nousresearch.com/docs/guides/tips/)

---

## Open Questions

1. **Name** — `hermes-guide` is a placeholder. Need something more memorable.
2. **Seed data** — what's the minimum viable knowledge graph to be useful on day one?
3. **Hosting** — where does the LightRAG backend live? (Modal, fly.io, $5 VPS)
4. **Feedback loop** — how do users contribute patterns back to the graph?
