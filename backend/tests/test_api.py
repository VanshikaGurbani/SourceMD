"""API routes with the pipeline/LLM faked and an in-memory SQLite database."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.agents.state import RetrievedPassage
from backend.db.base import Base, get_db
from backend.main import create_app

PASSAGE = RetrievedPassage(
    doc="NICE-NG28-Type2-Diabetes", page=29, chunk=0, score=0.7, text="offer metformin",
    source_url="", web_url="https://www.nice.org.uk/guidance/ng28",
)


def _fake_result(*_args):
    scored = [
        {"text": "Metformin is first-line.", "verdict": "SUPPORTED", "confidence": 0.9,
         "rationale": "NG28", "sources": [PASSAGE]},
        {"text": "Insulin is mandatory within 6 months.", "verdict": "CONTRADICTED", "confidence": 0.8,
         "rationale": "No.", "sources": []},
    ]
    return {"scored_claims": scored, "trust_score": 45.0, "corrected_answer": "Corrected.",
            "follow_up_questions": ["Q1?", "Q2?"]}


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr("backend.api.routes.evaluate.run_pipeline", _fake_result)
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_evaluate_persists_and_returns_report(client):
    r = client.post("/evaluate", json={"question": "First-line drug?", "ai_answer": "Metformin. Insulin at 6 months."})
    assert r.status_code == 200
    body = r.json()
    assert body["trust_score"] == 45.0
    assert [c["verdict"] for c in body["claims"]] == ["SUPPORTED", "CONTRADICTED"]
    assert body["ragas_faithfulness"] == 0.5  # legacy-named column: share of non-SUPPORTED verdicts
    assert body["follow_up_questions"] == ["Q1?", "Q2?"]

    again = client.get(f"/history/{body['id']}")
    assert again.status_code == 200
    assert again.json()["corrected_answer"] == "Corrected."


def test_history_404(client):
    assert client.get("/history/999").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [{"question": "ab", "ai_answer": "long enough answer"}, {"question": "ok question"}, {}],
)
def test_evaluate_validates_input(client, payload):
    assert client.post("/evaluate", json=payload).status_code == 422


def test_evaluate_pipeline_runtime_error_is_500(client, monkeypatch):
    def boom(*_a):
        raise RuntimeError("GROQ_API_KEY is not set.")

    monkeypatch.setattr("backend.api.routes.evaluate.run_pipeline", boom)
    r = client.post("/evaluate", json={"question": "First-line drug?", "ai_answer": "Metformin."})
    assert r.status_code == 500
    assert "GROQ_API_KEY" in r.json()["detail"]


def test_follow_up_uses_llm_answer(client, monkeypatch):
    seen = {}

    def fake_llm(prompt, **_kw):
        seen["prompt"] = prompt
        return "An SGLT-2 inhibitor is also offered."

    monkeypatch.setattr("backend.api.routes.followup.claude_complete", fake_llm)
    r = client.post(
        "/follow-up",
        json={
            "question": "What else is offered?",
            "original_question": "First-line drug?",
            "ai_answer": "Metformin.",
            "corrected_answer": "Metformin plus an SGLT-2 inhibitor.",
            "claims": [{"verdict": "SUPPORTED", "text": "Metformin is first-line."}],
        },
    )
    assert r.status_code == 200
    assert r.json() == {"answer": "An SGLT-2 inhibitor is also offered."}
    assert "[SUPPORTED] Metformin is first-line." in seen["prompt"]


def test_follow_up_llm_failure_is_500(client, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("no key")

    monkeypatch.setattr("backend.api.routes.followup.claude_complete", boom)
    r = client.post(
        "/follow-up",
        json={"question": "why?", "original_question": "q q q", "ai_answer": "a", "corrected_answer": "c"},
    )
    assert r.status_code == 500
