from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "<form" in response.text


def test_inquire_answers_with_the_declared_fields():
    response = client.post(
        "/inquire",
        json={"text": "a ship sinks, the author is erik larson"},
    )
    assert response.status_code == 200
    assert set(response.json()) == {"reply", "books", "nomination"}
