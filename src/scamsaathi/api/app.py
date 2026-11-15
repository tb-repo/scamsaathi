"""FastAPI Application for ScamSaathi (FR-070, FR-080, FR-084, FR-065)."""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

# Ensure 'src' is in sys.path so scamsaathi is discoverable when launched directly
_SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.sqlite import SqliteSaver

logger = logging.getLogger("scamsaathi.api")

from scamsaathi.agents.context import AgentContext, build_context
from scamsaathi.api.schemas import (
    ActionOut,
    AssessRequest,
    AssessResponse,
    HealthResponse,
    OfficialContactOut,
    ReasonOut,
    ResumeRequest,
    STANDARD_DISCLAIMER,
)
from scamsaathi.config import PROJECT_ROOT, get_settings
from scamsaathi.pipeline.agentic import AgentRunner, AssessmentOutcome


def outcome_to_response(
    outcome: AssessmentOutcome, session_token: str | None = None
) -> AssessResponse:
    headline = outcome.explanation.headline if outcome.explanation else None
    reasons = (
        [ReasonOut(text=r.text, evidence_ids=r.evidence_ids) for r in outcome.explanation.reasons]
        if outcome.explanation
        else []
    )
    actions = (
        [ActionOut(priority=a.priority, text=a.text) for a in outcome.advice.actions]
        if outcome.advice
        else []
    )
    contacts = (
        [
            OfficialContactOut(
                name=c.name, channel=c.channel, value=c.value, verified_on=c.verified_on
            )
            for c in outcome.advice.contacts
        ]
        if outcome.advice
        else []
    )

    return AssessResponse(
        thread_id=outcome.thread_id,
        session_token=session_token,
        status=outcome.status,
        risk_level=outcome.risk.level if outcome.risk else None,
        risk_score=outcome.risk.value if outcome.risk else None,
        headline=headline,
        reasons=reasons,
        actions=actions,
        contacts=contacts,
        questions=outcome.questions,
        typologies=outcome.typologies,
        language=outcome.language,
        disclaimer=STANDARD_DISCLAIMER,
        degraded=outcome.degraded,
        errors=outcome.errors,
    )


class AppState:
    ctx: AgentContext | None = None
    runner: AgentRunner | None = None
    sqlite_conn: sqlite3.Connection | None = None
    db_lock: threading.RLock = threading.RLock()


state = AppState()


def _purge_session_records(conn: sqlite3.Connection | None, thread_id: str) -> bool:
    """Atomic rollback of all session artifacts (metadata, checkpoints, writes) on failure.

    Returns True if purged successfully or if no conn is attached; returns False on database failure.
    """
    if state.runner is not None:
        state.runner.clear_session(thread_id)
    if conn is None:
        return True
    with state.db_lock:
        try:
            with conn:
                conn.execute("DELETE FROM session_meta WHERE thread_id = ?", (thread_id,))
                conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
                conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
            return True
        except Exception as exc:
            logger.exception("session_purge_failed", extra={"thread_id": thread_id, "error_type": type(exc).__name__})
            return False


def cleanup_expired_sessions(conn: sqlite3.Connection, ttl_seconds: float = 86400.0) -> int:
    """Enforces 24-hour storage limitation (DPDP Principle 4 / FR-084) by pruning expired checkpoints."""
    cutoff = time.time() - ttl_seconds
    with state.db_lock:
        try:
            cur = conn.cursor()
            cur.execute("SELECT thread_id FROM session_meta WHERE last_accessed < ?", (cutoff,))
            expired = [row[0] for row in cur.fetchall()]
            for tid in expired:
                cur.execute("DELETE FROM checkpoints WHERE thread_id = ?", (tid,))
                cur.execute("DELETE FROM writes WHERE thread_id = ?", (tid,))
                cur.execute("DELETE FROM session_meta WHERE thread_id = ?", (tid,))
                if state.runner is not None:
                    state.runner.clear_session(tid)
            # Prune any orphaned checkpoints/writes not tracked in session_meta (trusted maintenance path)
            try:
                cur.execute("DELETE FROM checkpoints WHERE thread_id NOT IN (SELECT thread_id FROM session_meta)")
                cur.execute("DELETE FROM writes WHERE thread_id NOT IN (SELECT thread_id FROM session_meta)")
            except sqlite3.OperationalError:
                pass
            conn.commit()
            if expired:
                logger.info(f"purged_{len(expired)}_expired_sessions")
            return len(expired)
        except Exception as exc:
            logger.warning(f"session_ttl_cleanup_failed: {type(exc).__name__}")
            return 0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    ctx = build_context(settings)
    cache_dir = PROJECT_ROOT / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = cache_dir / "sessions.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_meta (
            thread_id TEXT PRIMARY KEY,
            session_token TEXT NOT NULL,
            created_at REAL NOT NULL,
            last_accessed REAL NOT NULL
        )
    """)
    conn.commit()
    cleanup_expired_sessions(conn)

    saver = SqliteSaver(conn)
    saver.setup()
    runner = AgentRunner(ctx, checkpointer=saver)

    state.ctx = ctx
    state.runner = runner
    state.sqlite_conn = conn

    # Periodic background cleanup task for idle server retention (runs hourly)
    async def _periodic_cleanup(c: sqlite3.Connection, interval_s: float = 3600.0) -> None:
        while True:
            try:
                await asyncio.sleep(interval_s)
                cleanup_expired_sessions(c)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(f"periodic_cleanup_error: {type(exc).__name__}")

    cleanup_task = asyncio.create_task(_periodic_cleanup(conn))
    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    if state.sqlite_conn is not None:
        state.sqlite_conn.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="ScamSaathi API",
        description="Agentic AI Assistant for Mobile Scam Defense in India",
        version="0.1.0",
        lifespan=lifespan,
    )

    _rate_limit_records: dict[str, list[float]] = {}
    app.state.rate_limit_records = _rate_limit_records
    _RATE_LIMIT_MAX_REQUESTS = 60
    _RATE_LIMIT_WINDOW_SECONDS = 60.0
    _RATE_LIMIT_MAX_TRACKED_IPS = 1000

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next: Any) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        direct_ip = request.client.host if request.client else "unknown"
        settings = get_settings()
        trusted = settings.trusted_proxy_set

        # Reverse Proxy Deployment Prerequisite:
        # Trust X-Forwarded-For only when the direct connecting peer is in trusted_proxies.
        # Production reverse proxies (e.g. Nginx, Envoy, AWS ALB) MUST be configured
        # to strip or overwrite any client-supplied X-Forwarded-For header before appending
        # the verified client IP. When so configured, the first IP in the header is the authentic client.
        if direct_ip in trusted and "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        else:
            client_ip = direct_ip

        now = time.time()
        window_start = now - _RATE_LIMIT_WINDOW_SECONDS

        records: dict[str, list[float]] = getattr(app.state, "rate_limit_records", _rate_limit_records)
        max_tracked = getattr(app.state, "rate_limit_max_tracked_ips", _RATE_LIMIT_MAX_TRACKED_IPS)

        # 1. Prune expired IP keys whose timestamps have elapsed outside the active window
        stale = [ip for ip, timestamps in records.items() if not timestamps or timestamps[-1] <= window_start]
        for ip in stale:
            records.pop(ip, None)

        # 2. Strict memory bounding without resetting active clients' counters:
        # Evicting active clients during a high-cardinality burst would wipe their request counts
        # and allow rate-limit bypass. Therefore, active clients are never evicted mid-window.
        # If active tracking capacity is saturated, new untracked clients are rejected with 429
        # until active windows naturally elapse and release capacity slots.
        # For horizontally scaled / multi-process production deployments, use an external shared
        # rate limiter (e.g., Redis fixed-window or sliding-window token bucket).
        if len(records) >= max_tracked and client_ip not in records:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many concurrent clients. Rate limit capacity reached. Please try again shortly."},
            )

        history = [ts for ts in records.get(client_ip, []) if ts > window_start]
        if len(history) >= _RATE_LIMIT_MAX_REQUESTS:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Please slow down and try again later."},
            )
        history.append(now)
        records[client_ip] = history
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8501",
            "http://127.0.0.1:8501",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    def health_check() -> HealthResponse:
        settings = get_settings()
        return HealthResponse(
            status="ok",
            version="0.1.0",
            mode=settings.mode.value,
            primary_provider="gemini" if settings.gemini_api_key else "deterministic",
            primary_model_fast=settings.gemini_model_fast,
            primary_model_reasoning=settings.gemini_model_reasoning,
            fallback_provider="groq" if settings.groq_api_key else None,
            fallback_model_fast=settings.groq_model_fast if settings.groq_api_key else None,
            fallback_model_reasoning=settings.groq_model_reasoning if settings.groq_api_key else None,
            disclaimer=STANDARD_DISCLAIMER,
        )

    @app.post("/assess", response_model=AssessResponse)
    def assess_message(req: AssessRequest) -> AssessResponse:
        if state.runner is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Pipeline runner is not initialized",
            )

        thread_id = req.thread_id or uuid.uuid4().hex
        if not re.match(r"^[A-Za-z0-9_-]{8,64}$", thread_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid thread_id format (must be 8-64 alphanumeric characters)"
            )

        session_token = secrets.token_urlsafe(32)
        now = time.time()

        # Architecture Tradeoff Note:
        # Serializing assess/resume/cleanup under state.db_lock guarantees 100% SQLite transaction
        # integrity and checkpointer isolation across concurrent FastAPI worker threads on a single connection.
        # For high-throughput production scaling, migrate from a single shared SQLite connection to
        # connection-per-request pooling (WAL mode) or a multi-tenant concurrency-safe checkpointer
        # (e.g., PostgresSaver / RedisSaver) to avoid serializing model invocation latency across concurrent requests.
        with state.db_lock:
            if state.sqlite_conn is not None:
                cleanup_expired_sessions(state.sqlite_conn)

                # Prevent session takeover: reject duplicate thread_id if already exists
                cur = state.sqlite_conn.cursor()
                cur.execute("SELECT session_token FROM session_meta WHERE thread_id = ?", (thread_id,))
                if cur.fetchone() is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Session ID already exists; cannot overwrite an existing session.",
                    )
                try:
                    state.sqlite_conn.execute(
                        "INSERT INTO session_meta (thread_id, session_token, created_at, last_accessed) "
                        "VALUES (?, ?, ?, ?)",
                        (thread_id, session_token, now, now),
                    )
                    state.sqlite_conn.commit()
                except sqlite3.IntegrityError as exc:
                    if "UNIQUE" in str(exc) or "PRIMARY KEY" in str(exc):
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Session ID already exists; cannot overwrite an existing session.",
                        ) from exc
                    logger.error(f"session_meta_insert_failed: {type(exc).__name__}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to initialize session record.",
                    ) from exc
                except Exception as exc:
                    logger.error(f"session_meta_insert_failed: {type(exc).__name__}", exc_info=True)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to initialize session record.",
                    ) from exc

            try:
                outcome = state.runner.assess(req.text, thread_id=thread_id)
                return outcome_to_response(outcome, session_token=session_token)
            except ValueError as exc:
                _purge_session_records(state.sqlite_conn, thread_id)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            except HTTPException:
                _purge_session_records(state.sqlite_conn, thread_id)
                raise
            except Exception as exc:
                _purge_session_records(state.sqlite_conn, thread_id)
                logger.exception("api_assess_error", extra={"error_type": type(exc).__name__})
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An internal error occurred while processing the assessment.",
                ) from exc

    @app.post("/resume", response_model=AssessResponse)
    def resume_thread(
        req: ResumeRequest,
        x_session_token: str | None = Header(None, alias="X-Session-Token"),
    ) -> AssessResponse:
        if state.runner is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Pipeline runner is not initialized",
            )
        if not re.match(r"^[A-Za-z0-9_-]{8,64}$", req.thread_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid thread_id format"
            )

        token_to_verify = req.session_token or x_session_token

        # Architecture Tradeoff Note:
        # Serializing assess/resume/cleanup under state.db_lock guarantees 100% SQLite transaction
        # integrity and checkpointer isolation across concurrent FastAPI worker threads on a single connection.
        # For high-throughput production scaling, migrate from a single shared SQLite connection to
        # connection-per-request pooling (WAL mode) or a multi-tenant concurrency-safe checkpointer
        # (e.g., PostgresSaver / RedisSaver) to avoid serializing model invocation latency across concurrent requests.
        with state.db_lock:
            if state.sqlite_conn is not None:
                cur = state.sqlite_conn.cursor()
                cur.execute(
                    "SELECT session_token, last_accessed FROM session_meta WHERE thread_id = ?",
                    (req.thread_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Session not found or has expired.",
                    )
                stored_token, last_accessed = row
                if time.time() - last_accessed > 86400.0:
                    if not _purge_session_records(state.sqlite_conn, req.thread_id):
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to prune expired session data from storage.",
                        )
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Session has expired (24-hour TTL) and has been pruned.",
                    )

                if token_to_verify is None or not secrets.compare_digest(token_to_verify, stored_token):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Session ownership verification failed: invalid or missing session token",
                    )
                state.sqlite_conn.execute(
                    "UPDATE session_meta SET last_accessed = ? WHERE thread_id = ?",
                    (time.time(), req.thread_id),
                )
                state.sqlite_conn.commit()

            try:
                outcome = state.runner.resume(req.thread_id, req.answer)
                return outcome_to_response(outcome, session_token=token_to_verify)
            except HTTPException:
                raise
            except Exception as exc:
                logger.exception("api_resume_error", extra={"error_type": type(exc).__name__})
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An internal error occurred while resuming the assessment.",
                ) from exc

    @app.delete("/session/{thread_id}")
    def clear_session(
        thread_id: str,
        token: str | None = None,
        x_session_token: str | None = Header(None, alias="X-Session-Token"),
    ) -> dict[str, str]:
        """User control: deletes session checkpoints and in-memory PII maps (DPDP principle 6).

        Session token should preferably be provided in the 'X-Session-Token' HTTP header.
        """
        if not re.match(r"^[A-Za-z0-9_-]{8,64}$", thread_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid thread_id format"
            )

        token_to_verify = x_session_token or token

        # Architecture Tradeoff Note:
        # Serializing assess/resume/cleanup under state.db_lock guarantees 100% SQLite transaction
        # integrity and checkpointer isolation across concurrent FastAPI worker threads on a single connection.
        # For high-throughput production scaling, migrate from a single shared SQLite connection to
        # connection-per-request pooling (WAL mode) or a multi-tenant concurrency-safe checkpointer
        # (e.g., PostgresSaver / RedisSaver) to avoid serializing model invocation latency across concurrent requests.
        with state.db_lock:
            if state.sqlite_conn is not None:
                cur = state.sqlite_conn.cursor()
                cur.execute("SELECT session_token FROM session_meta WHERE thread_id = ?", (thread_id,))
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Session not found or has expired.",
                    )
                stored_token = row[0]
                if token_to_verify is None or not secrets.compare_digest(token_to_verify, stored_token):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Session ownership verification failed: invalid or missing session token",
                    )
                if not _purge_session_records(state.sqlite_conn, thread_id):
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to clear session data from storage.",
                    )
            elif state.runner is not None:
                state.runner.clear_session(thread_id)

            return {"status": "cleared", "thread_id": thread_id}

    return app


app = create_app()
