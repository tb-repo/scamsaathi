"""Task 1.11: LangGraph spike (ADR-002 validation).

A deliberately small 4-node graph that exercises the features ScamSaathi depends on:
- typed shared state,
- conditional routing on a confidence value (fast path vs interview),
- a human-in-the-loop loop using ``interrupt`` / ``Command(resume=...)``,
- persistence in SQLite, with resume from a *new* graph instance (simulated restart),
- a hard cap on follow-up questions,
- only masked text reaching the checkpoint store (FR-061, ADR-007).

Logic is toy keyword matching; the real agents come in Phase 4. No network, no LLM.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from scamsaathi.tools.pii_masker import mask

MAX_FOLLOWUPS = 2
HIGH_CONFIDENCE = 0.6
KEYWORDS = {
    "otp": "credential_request",
    "kyc": "authority_impersonation",
    "blocked": "threat",
    "urgent": "urgency",
    "pay": "payment_request",
}


class SpikeState(TypedDict, total=False):
    masked_text: str
    answers: list[str]
    signals: list[str]
    confidence: float
    followups_asked: int
    score: int
    level: str


def extract(state: SpikeState) -> dict[str, Any]:
    text = " ".join([state["masked_text"], *state.get("answers", [])]).lower()
    signals = sorted({name for word, name in KEYWORDS.items() if word in text})
    return {"signals": signals, "confidence": min(1.0, 0.3 * len(signals))}


def route_after_extract(state: SpikeState) -> str:
    if state["confidence"] >= HIGH_CONFIDENCE or state.get("followups_asked", 0) >= MAX_FOLLOWUPS:
        return "score"
    return "interview"


def interview(state: SpikeState) -> dict[str, Any]:
    # Everything before interrupt() re-runs on resume, so it must be side-effect free.
    answer = interrupt({"questions": ["Did they ask for an OTP or ask you to pay?"]})
    return {
        "answers": [*state.get("answers", []), str(answer)],
        "followups_asked": state.get("followups_asked", 0) + 1,
    }


def score(state: SpikeState) -> dict[str, Any]:
    value = min(100, 25 * len(state["signals"]))
    level = "HIGH" if value >= 60 else "MEDIUM" if value >= 30 else "LOW"
    return {"score": value, "level": level}


def build(saver: SqliteSaver) -> CompiledStateGraph[Any, Any, Any, Any]:
    builder = StateGraph(SpikeState)
    builder.add_node("extract", extract)
    builder.add_node("interview", interview)
    builder.add_node("score", score)
    builder.add_edge(START, "extract")
    builder.add_conditional_edges("extract", route_after_extract, ["interview", "score"])
    builder.add_edge("interview", "extract")
    builder.add_edge("score", END)
    return builder.compile(checkpointer=saver)


def _config(thread: str) -> Any:
    return {"configurable": {"thread_id": thread}}


def test_clear_scam_takes_fast_path(tmp_path: Path) -> None:
    with SqliteSaver.from_conn_string(str(tmp_path / "cp.db")) as saver:
        graph = build(saver)
        result = graph.invoke(
            {"masked_text": "URGENT: KYC pending, share OTP or account blocked"}, _config("t1")
        )
        assert result["level"] == "HIGH"
        assert graph.get_state(_config("t1")).interrupts == ()
        assert result.get("followups_asked", 0) == 0


def test_vague_input_pauses_then_resumes_after_restart(tmp_path: Path) -> None:
    db = str(tmp_path / "cp.db")
    with SqliteSaver.from_conn_string(db) as saver:
        graph = build(saver)
        graph.invoke({"masked_text": "Someone called about my parcel"}, _config("t2"))
        snapshot = graph.get_state(_config("t2"))
        assert snapshot.next == ("interview",)
        assert snapshot.interrupts[0].value["questions"]

    # New saver and graph objects on the same file: simulates an API process restart.
    with SqliteSaver.from_conn_string(db) as saver:
        graph = build(saver)
        result = graph.invoke(
            Command(resume="yes, they said pay a fee and share the OTP"), _config("t2")
        )
        assert result["followups_asked"] == 1
        assert {"credential_request", "payment_request"} <= set(result["signals"])
        assert result["level"] == "MEDIUM"


def test_followup_cap_ends_interview(tmp_path: Path) -> None:
    with SqliteSaver.from_conn_string(str(tmp_path / "cp.db")) as saver:
        graph = build(saver)
        graph.invoke({"masked_text": "Got a strange call"}, _config("t3"))
        for _ in range(MAX_FOLLOWUPS):
            result = graph.invoke(Command(resume="not sure"), _config("t3"))
        assert graph.get_state(_config("t3")).next == ()
        assert result["followups_asked"] == MAX_FOLLOWUPS
        assert result["level"] == "LOW"


def test_checkpoint_store_holds_masked_text_only(tmp_path: Path) -> None:
    raw = "Bank KYC: call 9876543210 or pay to fraud.desk@ybl urgently"
    masked = mask(raw).masked_text
    db = tmp_path / "cp.db"
    with SqliteSaver.from_conn_string(str(db)) as saver:
        build(saver).invoke({"masked_text": masked}, _config("t4"))

    chunks: list[bytes] = []
    conn = sqlite3.connect(db)
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            # Table names come from sqlite_master, not user input.
            for row in conn.execute(f'SELECT * FROM "{table}"'):  # noqa: S608
                for value in row:
                    if isinstance(value, bytes):
                        chunks.append(value)
                    elif isinstance(value, str):
                        chunks.append(value.encode("utf-8"))
    finally:
        conn.close()
    blobs = b"".join(chunks)

    assert blobs, "checkpoint store should not be empty"
    assert b"9876543210" not in blobs
    assert b"fraud.desk@ybl" not in blobs
    assert b"<PHONE_1>" in blobs
