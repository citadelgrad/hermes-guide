import hashlib
import os
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
QUERY_TOKEN = os.environ["HERMES_GUIDE_QUERY_TOKEN"]
ADMIN_TOKEN = os.environ["HERMES_GUIDE_ADMIN_TOKEN"]
DATA_DIR = os.environ.get("LIGHTRAG_DATA_DIR", "/data")
MAX_ASYNC = int(os.environ.get("MAX_ASYNC", "2"))

# LightRAG setup
from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc
import numpy as np

async def llm_model_func(prompt, system_prompt=None, history_messages=None, **kwargs):
    return await openai_complete_if_cache(
        "gpt-4o-mini",
        prompt,
        system_prompt=system_prompt,
        history_messages=history_messages,
        **kwargs,
    )

async def embedding_func(texts: list[str]) -> np.ndarray:
    return await openai_embed(texts, model="text-embedding-3-small")

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


def require_query_token(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not secrets.compare_digest(creds.credentials, QUERY_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid token")


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


@app.post("/query", dependencies=[Depends(require_query_token)])
@limiter.limit("60/minute")
async def query(request: Request, payload: QueryRequest):
    soul_content = payload.get_soul_content()

    # Build query string with context embedded — user_prompt only affects LLM generation
    # not retrieval, so keywords must be in the query string itself
    query_str = f"""User goal: {payload.goal}
Currently installed skills: {', '.join(payload.skills_list) if payload.skills_list else 'none'}
SOUL.md present: {'yes, content follows' if soul_content else 'no'}
{('SOUL.md content:\n' + soul_content) if soul_content else ''}

Given this setup, what specific skills should they add, what SOUL.md sections
are missing or weak, and what are the highest-impact next actions?"""

    param = QueryParam(
        mode="mix",                # official default as of PR #3287 (June 2026)
        only_need_context=True,    # eliminates LightRAG's internal LLM call; cuts latency to 500-800ms
        top_k=payload.max_results,
        hl_keywords=["soul.md", "skills", "hermes", "configuration", "setup"],
        ll_keywords=payload.skills_list or [],
    )

    context = await rag.aquery(query_str, param=param)

    # Parse context into structured recommendations
    # When only_need_context=True, context is raw graph text — parse into recommendations
    recommendations = _parse_context_to_recommendations(context, payload)

    return QueryResponse(
        recommendations=recommendations,
        context_lines=len(context.split("\n")) if context else 0,
        query_mode="mix",
    )


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
        "text": context[:4000],  # cap for response size
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
