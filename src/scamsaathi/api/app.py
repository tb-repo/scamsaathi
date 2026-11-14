"""FastAPI Application for ScamSaathi (FR-070, FR-080, FR-084, FR-065)."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver

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


def outcome_to_response(outcome: AssessmentOutcome) -> AssessResponse:
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    ctx = build_context(settings)
    cache_dir = PROJECT_ROOT / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = cache_dir / "sessions.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    runner = AgentRunner(ctx, checkpointer=saver)

    state.ctx = ctx
    state.runner = runner
    state.sqlite_conn = conn
    yield

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
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
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
        try:
            outcome = state.runner.assess(req.text, thread_id=req.thread_id)
            return outcome_to_response(outcome)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Assessment error: {exc}",
            ) from exc

    @app.post("/resume", response_model=AssessResponse)
    def resume_thread(req: ResumeRequest) -> AssessResponse:
        if state.runner is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Pipeline runner is not initialized",
            )
        try:
            outcome = state.runner.resume(req.thread_id, req.answer)
            return outcome_to_response(outcome)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Resume error: {exc}",
            ) from exc

    @app.delete("/session/{thread_id}")
    def clear_session(thread_id: str) -> dict[str, str]:
        """User control: deletes session checkpoints for the thread (Doc 08 privacy principle 6)."""
        if state.sqlite_conn is not None:
            try:
                state.sqlite_conn.execute(
                    "DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,)
                )
                state.sqlite_conn.execute(
                    "DELETE FROM checkpoint_writes WHERE thread_id = ?", (thread_id,)
                )
                state.sqlite_conn.commit()
            except Exception:
                pass
        return {"status": "cleared", "thread_id": thread_id}

    return app


app = create_app()
