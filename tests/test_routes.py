import html
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models import Model, override_allow_model_requests
from pydantic_ai.models.test import TestModel

from app.main import app, get_model

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_real_model() -> Iterator[None]:
    with override_allow_model_requests(False):
        yield


@pytest.fixture
def use_model() -> Iterator[Callable[[Model], None]]:
    def use(model: Model) -> None:
        app.dependency_overrides[get_model] = lambda: model

    use(TestModel())
    yield use
    app.dependency_overrides.clear()


def test_page_loads():
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("copy", [
    "Hi, I'm here to help you nominate a book. Do you have one in mind, or would you like help coming up with one?",
    "I have one in mind", "I need help coming up with one",
    "Great, I'd love to help you find it. Tell me any details you can recall.",
    "Great, I'll make suggestions. Tell me what kinds of books you like.",
    "Sorry, I couldn't reach the book finder just now. Please try again.",
    "This chat is getting long. Tap New search to start fresh.",
    "Likely books", "New search",
])
def test_page_contains_the_fixed_copy(copy):
    assert copy in html.unescape(client.get("/").text)


def test_page_no_longer_has_the_nomination_form():
    assert "nomination-title" not in client.get("/").text


def test_inquire_returns_the_reply_and_cleaned_books(use_model):
    dead_wake = {"title": "Dead Wake", "author": "Erik Larson", "year": 2015, "reason": "r"}
    lowercase_copy = {"title": "dead wake", "author": "erik larson", "year": 2015, "reason": "r"}
    use_model(TestModel(custom_output_args={
        "reply": "That's Dead Wake.",
        "books": [dead_wake, lowercase_copy],
    }))
    turns = [{"speaker": "member", "text": "a ship sinks, the author is erik larson"}]
    response = client.post("/inquire", json={"path": "find", "turns": turns, "books": []})
    assert response.status_code == 200
    assert response.json() == {"reply": "That's Dead Wake.", "books": [dead_wake]}


def test_inquire_rejects_a_request_ending_with_the_finder(use_model):
    turns = [{"speaker": "finder", "text": "Which book?"}]
    response = client.post("/inquire", json={"path": "find", "turns": turns})
    assert response.status_code == 422


def test_inquire_answers_502_when_the_model_output_never_validates(use_model):
    use_model(TestModel(custom_output_args={"reply": "x", "books": "not a list"}))
    turns = [{"speaker": "member", "text": "hi"}]
    response = client.post("/inquire", json={"path": "find", "turns": turns})
    assert response.status_code == 502
    assert response.json() == {"detail": "The book finder model is unavailable."}
