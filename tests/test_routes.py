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

    yield use
    app.dependency_overrides.clear()


def test_page_loads():
    assert client.get("/").status_code == 200


def test_inquire_returns_the_reply_and_cleaned_books(use_model):
    use_model(TestModel(custom_output_args={"reply": "That's Dead Wake.", "books": [
        {"title": "Dead Wake", "author": "Erik Larson", "year": 2015, "reason": "r"},
        {"title": "dead wake", "author": "erik larson", "year": 2015, "reason": "r"}]}))
    response = client.post("/inquire", json={"path": "find", "turns": [{"speaker": "member", "text": "a ship sinks, the author is erik larson"}], "books": []})
    assert response.status_code == 200
    assert response.json() == {"reply": "That's Dead Wake.", "books": [{"title": "Dead Wake", "author": "Erik Larson", "year": 2015, "reason": "r"}]}


def test_inquire_rejects_a_request_ending_with_the_finder(use_model):
    response = client.post("/inquire", json={"path": "find", "turns": [{"speaker": "finder", "text": "Which book?"}]})
    assert response.status_code == 422


def test_inquire_answers_502_when_the_model_output_never_validates(use_model):
    use_model(TestModel(custom_output_args={"reply": "x", "books": "not a list"}))
    response = client.post("/inquire", json={"path": "find", "turns": [{"speaker": "member", "text": "hi"}]})
    assert response.status_code == 502
    assert response.json() == {"detail": "The book finder model is unavailable."}
