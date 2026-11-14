"""Integration tests for ScamSaathi FastAPI endpoints (IT-API-01, FR-070)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from scamsaathi.api.app import app


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

    if data["status"] == "needs_followup":
        assert len(data["questions"]) > 0
        thread_id = data["thread_id"]

        resume_resp = client.post("/resume", json={"thread_id": thread_id, "answer": "skip"})
        assert resume_resp.status_code == 200
        resume_data = resume_resp.json()
        assert resume_data["status"] == "complete"
        assert resume_data["risk_level"] is not None

        # Clean session
        del_resp = client.delete(f"/session/{thread_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "cleared"
    else:
        assert data["status"] == "complete"

