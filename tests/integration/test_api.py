"""Integration tests for ScamSaathi FastAPI endpoints (IT-API-01, FR-070)."""

from __future__ import annotations

import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from scamsaathi.api.app import app, state


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert "gemini" in data["primary_provider"]
    assert "guidance only" in data["disclaimer"]


def test_assess_empty_text_returns_422_or_400(client: TestClient) -> None:
    resp = client.post("/assess", json={"text": ""})
    assert resp.status_code in (400, 422)


def test_assess_scam_message(client: TestClient) -> None:
    kyc_sms = (
        "SBI Alert: Dear customer your SBI YONO account has been blocked today. "
        "Update KYC immediately at http://sbi-kyc-update.example/pan. Share OTP to verify."
    )
    resp = client.post("/assess", json={"text": kyc_sms})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "complete"
    assert data["risk_level"] in ("HIGH", "CRITICAL")
    assert data["risk_score"] >= 80
    assert data["headline"] is not None
    assert len(data["reasons"]) > 0
    assert len(data["actions"]) > 0
    assert len(data["contacts"]) > 0
    # Must contain official Chakshu reporting link
    contact_values = [c["value"] for c in data["contacts"]]
    assert any("sancharsaathi.gov.in" in val for val in contact_values)
    assert "guidance only" in data["disclaimer"]


def test_assess_and_resume_ambiguous_case(client: TestClient) -> None:
    vague_text = "They called about my parcel."
    resp = client.post("/assess", json={"text": vague_text})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_token" in data
    session_token = data["session_token"]
    thread_id = data["thread_id"]

    if data["status"] == "needs_followup":
        assert len(data["questions"]) > 0

        # 1. Unauthorized resume attempt with wrong token fails
        bad_resume = client.post(
            "/resume",
            json={"thread_id": thread_id, "answer": "skip", "session_token": "wrong_token_123"},
        )
        assert bad_resume.status_code == 403

        # 2. Authorized resume with valid token succeeds
        resume_resp = client.post(
            "/resume",
            json={"thread_id": thread_id, "answer": "skip", "session_token": session_token},
        )
        assert resume_resp.status_code == 200
        resume_data = resume_resp.json()
        assert resume_data["status"] == "complete"
        assert resume_data["risk_level"] is not None

        # 3. Unauthorized delete attempt fails
        bad_del = client.delete(f"/session/{thread_id}?token=wrong_token")
        assert bad_del.status_code == 403

        # 4. Authorized delete succeeds
        del_resp = client.delete(f"/session/{thread_id}?token={session_token}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "cleared"
    else:
        assert data["status"] == "complete"


def test_assess_rejects_duplicate_session_id(client: TestClient) -> None:
    custom_thread_id = "test_custom_thread_123456"
    resp1 = client.post("/assess", json={"text": "Hello, please verify your account", "thread_id": custom_thread_id})
    assert resp1.status_code == 200
    token = resp1.json()["session_token"]

    # Second attempt with same thread_id is rejected with 409 Conflict
    resp2 = client.post("/assess", json={"text": "Different message attempt", "thread_id": custom_thread_id})
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()

    # Clean up session
    client.delete(f"/session/{custom_thread_id}?token={token}")


def test_delete_missing_or_nonexistent_session_returns_404(client: TestClient) -> None:
    resp = client.delete("/session/nonexistent_session_9999?token=some_token_123")
    assert resp.status_code == 404
    assert "not found or has expired" in resp.json()["detail"].lower()


def test_resume_expired_session_returns_410(client: TestClient) -> None:
    custom_thread_id = "test_expired_thread_99999"
    resp = client.post(
        "/assess",
        json={"text": "They called about my parcel from courier.", "thread_id": custom_thread_id},
    )
    assert resp.status_code == 200
    token = resp.json()["session_token"]

    # Age the session past 24 hours (86,400s)
    assert state.sqlite_conn is not None
    state.sqlite_conn.execute(
        "UPDATE session_meta SET last_accessed = ? WHERE thread_id = ?",
        (time.time() - 90000.0, custom_thread_id),
    )
    state.sqlite_conn.commit()

    # Attempt to resume expired session -> returns 410 Gone
    resume_resp = client.post(
        "/resume",
        json={"thread_id": custom_thread_id, "answer": "skip", "session_token": token},
    )
    assert resume_resp.status_code == 410
    assert "expired" in resume_resp.json()["detail"].lower()

    # Verify session_meta and checkpoints are pruned
    cur = state.sqlite_conn.cursor()
    cur.execute("SELECT thread_id FROM session_meta WHERE thread_id = ?", (custom_thread_id,))
    assert cur.fetchone() is None


def test_assess_metadata_write_failure_fails_closed(client: TestClient) -> None:
    assert state.sqlite_conn is not None

    custom_thread_id = "test_fail_closed_thread_12345"
    state.sqlite_conn.execute("DROP TRIGGER IF EXISTS fail_insert_test;")
    state.sqlite_conn.commit()
    # Create SQLite trigger specifically scoped to fail_closed test thread_id
    state.sqlite_conn.execute(
        "CREATE TRIGGER fail_insert_test BEFORE INSERT ON session_meta "
        "FOR EACH ROW WHEN NEW.thread_id = 'test_fail_closed_thread_12345' "
        "BEGIN SELECT RAISE(ABORT, 'simulated disk failure'); END;"
    )
    state.sqlite_conn.commit()
    try:
        resp = client.post(
            "/assess",
            json={"text": "Hello verification needed", "thread_id": custom_thread_id},
        )
        assert resp.status_code == 500
        assert "Failed to initialize session record" in resp.json()["detail"]

        # Verify that NO checkpoint was persisted for custom_thread_id
        cur = state.sqlite_conn.cursor()
        cur.execute("SELECT thread_id FROM checkpoints WHERE thread_id = ?", (custom_thread_id,))
        assert cur.fetchone() is None
    finally:
        state.sqlite_conn.execute("DROP TRIGGER IF EXISTS fail_insert_test;")
        state.sqlite_conn.commit()


def test_delete_session_database_failure_fails_closed(client: TestClient) -> None:
    assert state.sqlite_conn is not None

    custom_thread_id = "test_atomic_del_thread_123"
    resp = client.post(
        "/assess",
        json={"text": "Hello verification needed", "thread_id": custom_thread_id},
    )
    assert resp.status_code == 200
    token = resp.json()["session_token"]

    state.sqlite_conn.execute("DROP TRIGGER IF EXISTS fail_delete_test;")
    state.sqlite_conn.commit()
    state.sqlite_conn.execute(
        "CREATE TRIGGER fail_delete_test BEFORE DELETE ON checkpoints "
        "FOR EACH ROW WHEN OLD.thread_id = 'test_atomic_del_thread_123' "
        "BEGIN SELECT RAISE(ABORT, 'simulated checkpoint delete failure'); END;"
    )
    state.sqlite_conn.commit()
    try:
        del_resp = client.delete(f"/session/{custom_thread_id}?token={token}")
        assert del_resp.status_code == 500
        assert "Failed to clear session data" in del_resp.json()["detail"]

        # Transaction atomicity: session_meta was rolled back and still exists
        cur = state.sqlite_conn.cursor()
        cur.execute("SELECT thread_id FROM session_meta WHERE thread_id = ?", (custom_thread_id,))
        assert cur.fetchone() is not None
    finally:
        state.sqlite_conn.execute("DROP TRIGGER IF EXISTS fail_delete_test;")
        state.sqlite_conn.commit()
        client.delete(f"/session/{custom_thread_id}?token={token}")

