from fastapi.testclient import TestClient
from pydantic_ai.models import override_allow_model_requests
from pydantic_ai.models.test import TestModel

from app.agent import finder_agent
from app.main import app

client = TestClient(app)


def test_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "<form" in response.text


def test_inquire_answers_with_the_declared_fields(monkeypatch):
    monkeypatch.setenv("LLM_API_GATEWAY", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_API_TOKEN", "sk-test")
    test_model = TestModel(
        custom_output_args={
            "reply": "Tell me more.",
            "books": [
                {
                    "title": "Dead Wake",
                    "author": "Erik Larson",
                    "summary": "A liner sinks.",
                    "reason": "The author matches.",
                }
            ],
            "nomination": {
                "title": "Dead Wake",
                "author": "Erik Larson",
                "summary": "A liner sinks.",
                "page_count": None,
            },
        }
    )
    with override_allow_model_requests(False), finder_agent.override(model=test_model):
        response = client.post(
            "/inquire",
            json={"text": "a ship sinks, the author is erik larson"},
        )
    assert response.status_code == 200
    assert set(response.json()) == {"reply", "books", "nomination"}


def test_blank_inquiry_is_rejected_before_a_model_call():
    with override_allow_model_requests(False):
        response = client.post("/inquire", json={"text": "   "})
    assert response.status_code == 422
