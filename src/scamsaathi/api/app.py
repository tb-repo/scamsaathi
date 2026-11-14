"""FastAPI Application for ScamSaathi (FR-070, FR-080, FR-084, FR-065)."""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
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


state = AppState()


def cleanup_expired_sessions(conn: sqlite3.Connection, ttl_seconds: float = 86400.0) -> int:
    """Enforces 24-hour storage limitation (DPDP Principle 4 / FR-084) by pruning expired checkpoints."""
    cutoff = time.time() - ttl_seconds
    try:
        cur = conn.cursor()
        cur.execute("SELECT thread_id FROM session_meta WHERE last_accessed < ?", (cutoff,))
        expired = [row[0] for row in cur.fetchall()]
        for tid in expired:
            cur.execute("DELETE FROM checkpoints WHERE thread_id = ?", (tid,))
            cur.execute("DELETE FROM writes WHERE thread_id = ?", (tid,))
            cur.execute("DELETE FROM session_meta WHERE thread_id = ?", (tid,))
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
        logger.warning(f"session_ttl_cleanup_failed: {exc}")
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
                logger.warning(f"periodic_cleanup_error: {exc}")

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
        if state.sqlite_conn is not None:
            cleanup_expired_sessions(state.sqlite_conn)

        thread_id = req.thread_id or uuid.uuid4().hex
        if not re.match(r"^[A-Za-z0-9_-]{8,64}$", thread_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid thread_id format (must be 8-64 alphanumeric characters)"
            )

        session_token = secrets.token_urlsafe(32)
        now = time.time()
        if state.sqlite_conn is not None:
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
                logger.error(f"session_meta_insert_failed: {exc}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to initialize session record.",
                ) from exc
            except Exception as exc:
                logger.error(f"session_meta_insert_failed: {exc}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to initialize session record.",
                ) from exc

        try:
            outcome = state.runner.assess(req.text, thread_id=thread_id)
            return outcome_to_response(outcome, session_token=session_token)
        except ValueError as exc:
            if state.sqlite_conn is not None:
                try:
                    state.sqlite_conn.execute("DELETE FROM session_meta WHERE thread_id = ?", (thread_id,))
                    state.sqlite_conn.commit()
                except Exception:
                    pass
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except HTTPException:
            if state.sqlite_conn is not None:
                try:
                    state.sqlite_conn.execute("DELETE FROM session_meta WHERE thread_id = ?", (thread_id,))
                    state.sqlite_conn.commit()
                except Exception:
                    pass
            raise
        except Exception as exc:
            if state.sqlite_conn is not None:
                try:
                    state.sqlite_conn.execute("DELETE FROM session_meta WHERE thread_id = ?", (thread_id,))
                    state.sqlite_conn.commit()
                except Exception:
                    pass
            logger.exception("api_assess_error", extra={"error": str(exc)})
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
                state.sqlite_conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (req.thread_id,))
                state.sqlite_conn.execute("DELETE FROM writes WHERE thread_id = ?", (req.thread_id,))
                state.sqlite_conn.execute("DELETE FROM session_meta WHERE thread_id = ?", (req.thread_id,))
                state.sqlite_conn.commit()
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
            logger.exception("api_resume_error", extra={"error": str(exc)})
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
        """User control: deletes session checkpoints and in-memory PII maps (DPDP principle 6)."""
        if not re.match(r"^[A-Za-z0-9_-]{8,64}$", thread_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid thread_id format"
            )

        token_to_verify = token or x_session_token
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
            state.sqlite_conn.execute("DELETE FROM session_meta WHERE thread_id = ?", (thread_id,))
            try:
                state.sqlite_conn.execute(
                    "DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,)
                )
                state.sqlite_conn.execute(
                    "DELETE FROM writes WHERE thread_id = ?", (thread_id,)
                )
                state.sqlite_conn.commit()
            except Exception as exc:
                logger.warning(f"session_db_clear_failed: {exc}")

        if state.runner is not None:
            state.runner.clear_session(thread_id)

        return {"status": "cleared", "thread_id": thread_id}

    return app


app = create_app()
