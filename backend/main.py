import hashlib
import os
import re
import secrets
from contextlib import asynccontextmanager

import structlog
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

# Configure structlog — never log "soul_md" or "content" keys
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger()

# Environment config
ADMIN_TOKEN = os.environ["HERMES_GUIDE_ADMIN_TOKEN"]
DATA_DIR = os.environ.get("LIGHTRAG_DATA_DIR", "/data")
MAX_ASYNC = int(os.environ.get("MAX_ASYNC", "2"))

# LightRAG setup
from lightrag import LightRAG, QueryParam
from lightrag.llm.gemini import gemini_complete_if_cache, gemini_embed
from lightrag.utils import EmbeddingFunc
import numpy as np

async def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs):
    return await gemini_complete_if_cache(
        "gemini-3.1-flash-lite",
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        **kwargs,
    )

async def embedding_func(texts: list[str]) -> np.ndarray:
    return await gemini_embed(texts, model="gemini-embedding-001", embedding_dim=1536)

rag = LightRAG(
    working_dir=DATA_DIR,
    llm_model_func=llm_model_func,
    embedding_func=EmbeddingFunc(
        embedding_dim=1536,
        max_token_size=8192,
        func=embedding_func,
    ),
    addon_params={"max_async": MAX_ASYNC},
)

# Pydantic models
class QueryRequest(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    goal: str
    skills_list: list[str] = []
    soul_md: SecretStr = Field(default=SecretStr(""), repr=False)
    max_results: int = Field(default=5, ge=1, le=20)

    def get_soul_content(self) -> str:
        return self.soul_md.get_secret_value()


class QueryResponse(BaseModel):
    recommendations: list[dict]
    context_lines: int
    query_mode: str


class IngestRequest(BaseModel):
    text: str
    source_url: str


# Auth
security = HTTPBearer()


def require_admin_token(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not secrets.compare_digest(creds.credentials, ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")


# Rate limiter
limiter = Limiter(key_func=get_remote_address)


# Lifespan — storages don't auto-initialize without this
@asynccontextmanager
async def lifespan(app: FastAPI):
    await rag.initialize_storages()
    await rag.check_and_migrate_data()
    app.state.ready = True
    yield
    await rag.finalize_storages()


app = FastAPI(title="hermes-guide", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


# Exception handler — strips Pydantic v2 "input" key that would leak SOUL.md content
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    safe_errors = [
        {k: v for k, v in err.items() if k not in ("input", "url", "ctx")}
        for err in exc.errors()
    ]
    logger.warning("validation_error", method=request.method, path=request.url.path)
    return JSONResponse(status_code=422, content={"detail": safe_errors})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


# Endpoints
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    if not getattr(app.state, "ready", False):
        raise HTTPException(status_code=503, detail="Not ready")
    return {"status": "ready"}


@app.post("/query")
@limiter.limit("10/minute")
async def query(request: Request, payload: QueryRequest):
    soul_content = payload.get_soul_content()
    contexts = []

    for intent in _intent_queries_from_payload(payload, soul_content):
        param = QueryParam(
            mode="mix",                # official default as of PR #3287 (June 2026)
            only_need_context=True,    # eliminates LightRAG's internal LLM call; cuts latency to 500-800ms
            top_k=max(3, min(payload.max_results, 8)),
            hl_keywords=["soul.md", "skills", "hermes", "configuration", "setup", *intent["keywords"][:8]],
            ll_keywords=intent["keywords"][:10],
        )
        context = await rag.aquery(intent["query"], param=param)
        contexts.append({"intent": intent["intent"], "context": context})

    context = _merge_intent_contexts(contexts)

    # Parse context into structured recommendations
    # When only_need_context=True, context is raw graph text — parse into recommendations
    recommendations = _parse_context_to_recommendations(context, payload)

    return QueryResponse(
        recommendations=recommendations,
        context_lines=len(context.split("\n")) if context else 0,
        query_mode="mix",
    )


def _keywords_from_text(text: str) -> list[str]:
    stopwords = {
        "about", "after", "before", "build", "from", "help", "hermes", "into",
        "should", "that", "their", "them", "this", "want", "what", "when", "which",
        "with", "would", "your",
    }
    keywords = []
    seen = set()
    for word in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()):
        if word in stopwords or word in seen:
            continue
        keywords.append(word)
        seen.add(word)
    return keywords


def _intent_queries_from_payload(payload: QueryRequest, soul_content: str) -> list[dict]:
    """Build one broad query plus per-intent queries so mixed goals do not collapse to one topic."""
    soul_block = f"SOUL.md content:\n{soul_content}" if soul_content else ""
    skills = [s.strip().lower() for s in payload.skills_list if s.strip()]
    goal = payload.goal.strip()

    base_context = f"""Currently installed skills: {', '.join(payload.skills_list) if payload.skills_list else 'none'}
SOUL.md present: {'yes, content follows' if soul_content else 'no'}
{soul_block}"""

    phrases = _intent_phrases_from_goal(goal)
    queries = []

    for phrase in phrases:
        keywords = _expand_keywords(_keywords_from_text(phrase) + skills)
        if not keywords:
            continue
        queries.append({
            "intent": phrase,
            "keywords": keywords,
            "query": f"""User goal intent: {phrase}
Retrieval aliases: {', '.join(keywords)}
Full user goal: {goal}
{base_context}

For this specific intent, what Hermes skills, documentation, or setup guidance are relevant?""",
        })

    broad_keywords = _expand_keywords(_keywords_from_text(goal) + skills)
    queries.append({
        "intent": "combined goal",
        "keywords": broad_keywords,
        "query": f"""User goal: {goal}
Retrieval aliases: {', '.join(broad_keywords)}
{base_context}

Given this full setup, what specific skills should they add, what SOUL.md sections
are missing or weak, and what are the highest-impact next actions?""",
    })

    return queries[:5]


def _intent_phrases_from_goal(goal: str) -> list[str]:
    normalized = re.sub(r"\b(?:and|plus|also|along with|as well as)\b", ",", goal, flags=re.IGNORECASE)
    parts = [part.strip(" .;:-") for part in re.split(r"[,;\n]+", normalized) if part.strip(" .;:-")]

    phrases = []
    seen = set()
    for part in parts:
        cleaned = re.sub(
            r"^(?:i\s+want\s+hermes\s+to\s+help\s+me|i\s+want\s+to|help\s+me|which\s+hermes\s+skill\s+should\s+i\s+install\s+to)\s+",
            "",
            part,
            flags=re.IGNORECASE,
        ).strip()
        if len(cleaned) < 4:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        phrases.append(cleaned)
        seen.add(key)

    return phrases or [goal]


def _expand_keywords(keywords: list[str]) -> list[str]:
    aliases = {
        "review": ["code review", "review code", "pull request", "code-review"],
        "code": ["code review", "software development"],
        "tdd": ["test-driven development", "test driven", "tests", "regression tests"],
        "test": ["test-driven development", "tdd", "regression tests"],
        "tests": ["test-driven development", "tdd", "regression tests"],
        "youtube": ["youtube transcript", "youtube content", "transcript", "video summary"],
        "transcript": ["youtube transcript", "youtube content", "video summary"],
        "transcripts": ["youtube transcript", "youtube content", "transcript"],
        "email": ["email triage", "gmail", "inbox"],
        "calendar": ["calendar", "scheduling", "followups"],
    }

    expanded = []
    seen = set()
    for keyword in keywords:
        for candidate in [keyword, *aliases.get(keyword, [])]:
            candidate = candidate.strip().lower()
            if candidate and candidate not in seen:
                expanded.append(candidate)
                seen.add(candidate)
    return expanded


def _merge_intent_contexts(contexts: list[dict], max_chars: int = 6000) -> str:
    """Merge LightRAG context from multiple intents while preserving each intent's slice."""
    sections = []
    seen_lines = set()
    per_intent_budget = max(900, max_chars // max(1, len(contexts)))

    for item in contexts:
        raw_context = (item.get("context") or "").strip()
        if not raw_context:
            continue

        lines = []
        for line in raw_context.splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            key = re.sub(r"\s+", " ", normalized.lower())
            if key in seen_lines:
                continue
            seen_lines.add(key)
            lines.append(line)

        if not lines:
            continue

        section = f"Intent: {item.get('intent', 'goal')}\n" + "\n".join(lines)
        sections.append(section[:per_intent_budget])

    merged = "\n\n".join(sections)
    if len(merged) <= max_chars:
        return merged

    return merged[:max_chars].rsplit("\n", 1)[0]


def _parse_context_to_recommendations(context: str, payload: QueryRequest) -> list[dict]:
    """Parse raw LightRAG context into structured recommendations."""
    if not context:
        return [{"category": "quick_win", "text": "Start by writing a SOUL.md to tell Hermes about yourself.", "priority": 1}]

    # Return context as a single recommendation block for Hermes session to synthesize
    # (Hermes Claude handles synthesis; we just surface the knowledge graph context)
    recs = []

    if not payload.get_soul_content():
        recs.append({
            "category": "soul_md_gap",
            "text": "You haven't written a SOUL.md yet. This is the highest-leverage thing you can do — it tells Hermes who you are, how you work, and what you care about.",
            "priority": 1,
        })

    recs.append({
        "category": "knowledge_context",
        "text": context[:6000],  # cap for response size
        "priority": 2,
    })

    return recs


async def _run_ingest(text: str, source_url: str):
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    try:
        from lightrag.utils import DocStatus
        existing = await rag.doc_status.get_doc_by_content_hash(content_hash)
        if existing and existing.status == DocStatus.PROCESSED:
            logger.info("skipping_duplicate", source_url=source_url)
            return
    except Exception:
        pass  # doc_status API may vary by LightRAG version

    try:
        await rag.ainsert(text)
        logger.info("ingested", source_url=source_url)
    except Exception as e:
        logger.error("ingest_failed", source_url=source_url, error=str(e))
        raise


@app.post("/ingest", status_code=202, dependencies=[Depends(require_admin_token)])
@limiter.limit("30/minute")
async def ingest(request: Request, payload: IngestRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_ingest, payload.text, payload.source_url)
    return {"status": "accepted", "source_url": payload.source_url}
