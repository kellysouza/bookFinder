import html
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models import Model, override_allow_model_requests
from pydantic_ai.models.test import TestModel

from app.library import MemoryLibrary
from app.main import (
    app,
    get_catalog,
    get_connection,
    get_model,
    get_store,
    get_summarizer,
)
from app.rules.catalog import ASK_FOR_MORE, CatalogRecord
from app.rules.nomination import CLOSED_MEETING

client = TestClient(app)

USABLE = (
    "The Lusitania's last crossing, told from the ship and from the U-boat that followed it."
)


class ConfirmingCatalog:
    """Confirms every title, or only the records it was given."""

    def __init__(self, records: dict[tuple[str, str], CatalogRecord] | None = None) -> None:
        self.records = records

    def lookup(self, title: str, author: str) -> CatalogRecord | None:
        if self.records is None:
            return CatalogRecord(title, author, 2015, 448, "9780804194617", USABLE)
        return self.records.get((title.lower(), author.lower()))

    def newest_by_author(self, author: str) -> CatalogRecord | None:
        return None


async def stub_summary(
    title: str, author: str, member_text: str, description: str | None, model: Model
) -> tuple[str, str]:
    """Return a fixed summary so the route test does not call the summary model."""
    return "The Lusitania sinks on its last crossing.", "open_library"


@pytest.fixture(autouse=True)
def no_real_model() -> Iterator[None]:
    with override_allow_model_requests(False):
        yield


@pytest.fixture
def library() -> Iterator[MemoryLibrary]:
    store = MemoryLibrary()
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_catalog] = lambda: ConfirmingCatalog()
    app.dependency_overrides[get_summarizer] = lambda: stub_summary
    yield store
    app.dependency_overrides.pop(get_store, None)
    app.dependency_overrides.pop(get_catalog, None)
    app.dependency_overrides.pop(get_summarizer, None)


@pytest.fixture
def use_model(library: MemoryLibrary) -> Iterator[Callable[[Model], None]]:
    def use(model: Model) -> None:
        app.dependency_overrides[get_model] = lambda: model

    use(TestModel())
    yield use
    app.dependency_overrides.pop(get_model, None)


def test_page_loads():
    assert client.get("/").status_code == 200


class _AnsweringConnection:
    def execute(self, _query: str) -> "_AnsweringConnection":
        return self

    def fetchone(self) -> tuple[int]:
        return (1,)


def test_postgres_health_reports_an_answer():
    def fake_connection() -> Iterator[object]:
        yield _AnsweringConnection()

    app.dependency_overrides[get_connection] = fake_connection
    try:
        response = client.get("/health/postgres")
    finally:
        app.dependency_overrides.pop(get_connection, None)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.parametrize("copy", [
    "Hi, I'm here to help you nominate a book. Do you have one in mind, or would you like help coming up with one?",
    "I have one in mind", "I need help coming up with one",
    "Great, I'd love to help you find it. Tell me any details you can recall.",
    "Great, I'll make suggestions. Tell me what kinds of books you like.",
    "Sorry, I couldn't reach the book finder just now. Please try again.",
    "This chat is getting long. Tap New search to start fresh.",
    "Likely books", "New search", "Search by meaning", "Nominations",
])
def test_page_contains_the_fixed_copy(copy):
    assert copy in html.unescape(client.get("/").text)


def test_page_has_the_nomination_form():
    page = client.get("/").text
    assert 'id="nomination-title"' in page
    assert 'id="nomination-author"' in page
    assert 'id="nomination-summary"' in page
    assert 'id="nomination-error"' in page


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
    body = response.json()
    assert body["reply"] == "That's Dead Wake."
    assert body["session_id"] == 1
    assert body["books"] == [{
        "title": "Dead Wake",
        "author": "Erik Larson",
        "year": 2015,
        "reason": "r",
        "page_count": 448,
        "isbn": "9780804194617",
        "open_library_description": USABLE,
        "summary": "The Lusitania sinks on its last crossing.",
        "summary_source": "open_library",
        "source_label": "Summary drawn from the Open Library description.",
    }]


def test_saving_dead_wake_adds_it_to_the_nomination_list(use_model):
    use_model(TestModel(custom_output_args={
        "reply": "That's Dead Wake.",
        "books": [{"title": "Dead Wake", "author": "Erik Larson", "year": 2015, "reason": "A ship sinks."}],
    }))
    turns = [{"speaker": "member", "text": "a ship sinks, the author is erik larson"}]
    found = client.post("/inquire", json={"path": "find", "turns": turns, "books": []})
    book = found.json()["books"][0]
    saved = client.post("/nominations", json={
        "session_id": found.json()["session_id"],
        "title": book["title"],
        "author": book["author"],
        "page_count": book["page_count"],
        "isbn": book["isbn"],
        "open_library_description": book["open_library_description"],
        "member_description": book["summary"],
    })
    assert saved.status_code == 200
    listed = client.get("/nominations")
    assert listed.status_code == 200
    assert listed.json() == [{
        "title": "Dead Wake",
        "author": "Erik Larson",
        "page_count": 448,
        "member_description": "The Lusitania sinks on its last crossing.",
    }]


def test_blood_music_is_offered_only_when_open_library_returns_it(use_model, library):
    blood = CatalogRecord(
        "Blood Music",
        "Greg Bear",
        1985,
        262,
        "9781857987621",
        "A scientist injects himself with intelligent cells, and they remake him completely.",
    )
    app.dependency_overrides[get_catalog] = lambda: ConfirmingCatalog({
        ("blood music", "greg bear"): blood,
    })
    use_model(TestModel(custom_output_args={
        "reply": "Maybe one of these.",
        "books": [
            {"title": "Blood Music", "author": "Greg Bear", "year": 1985, "reason": "Biology."},
            {"title": "The Bear and the Nightingale", "author": "Katherine Arden", "year": 2017, "reason": "Bear."},
        ],
    }))
    turns = [{"speaker": "member", "text": "author's name was greg something, the title had bear in it"}]
    response = client.post("/inquire", json={"path": "find", "turns": turns, "books": []})
    assert response.status_code == 200
    titles = [book["title"] for book in response.json()["books"]]
    assert titles == ["Blood Music"]
    assert "Nightingale" not in response.json()["reply"]
    assert library.nominations() == []


def test_a_miss_asks_for_more_and_offers_no_book(use_model):
    app.dependency_overrides[get_catalog] = lambda: ConfirmingCatalog({})
    use_model(TestModel(custom_output_args={
        "reply": "That might be The Bear and the Nightingale.",
        "books": [{"title": "The Bear and the Nightingale", "author": "Katherine Arden", "year": 2017, "reason": "Bear."}],
    }))
    turns = [{"speaker": "member", "text": "the title had bear in it"}]
    response = client.post("/inquire", json={"path": "find", "turns": turns, "books": []})
    assert response.status_code == 200
    assert response.json()["books"] == []
    assert response.json()["reply"] == ASK_FOR_MORE


def test_a_closed_meeting_keeps_the_saved_list_and_reports_the_error(use_model, library):
    first = client.post("/nominations", json={
        "title": "Dead Wake",
        "author": "Erik Larson",
        "page_count": 448,
        "member_description": "The club should read how that ship went down.",
    })
    assert first.status_code == 200
    library.accepting = False
    rejected = client.post("/nominations", json={
        "title": "Blood Music",
        "author": "Greg Bear",
        "member_description": "A different book.",
    })
    assert rejected.status_code == 400
    assert rejected.json()["detail"] == CLOSED_MEETING
    listed = client.get("/nominations").json()
    assert listed == [{
        "title": "Dead Wake",
        "author": "Erik Larson",
        "page_count": 448,
        "member_description": "The club should read how that ship went down.",
    }]


def test_a_missing_title_keeps_the_saved_list(library):
    client.post("/nominations", json={
        "title": "Dead Wake",
        "author": "Erik Larson",
        "member_description": "Keep this.",
    })
    rejected = client.post("/nominations", json={
        "title": "  ",
        "author": "Erik Larson",
        "member_description": "Should not replace it.",
    })
    assert rejected.status_code == 400
    assert library.nominations()[0].member_description == "Keep this."


def test_meaning_search_returns_a_stored_description(library):
    client.post("/nominations", json={
        "title": "Brave New World",
        "author": "Aldous Huxley",
        "open_library_description": "A controlled society assigns people to castes and bans old books.",
        "member_description": "A controlled society assigns people to castes and bans old books.",
    })
    response = client.post("/similar", json={"query": "a book about a controlled society"})
    assert response.status_code == 200
    bodies = [hit["body"] for hit in response.json()]
    assert any("controlled society" in body for body in bodies)


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
