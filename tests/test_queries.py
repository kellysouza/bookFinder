"""Tests for the questions the finder asks its database."""

import os
from collections.abc import Iterator

import psycopg
import pytest
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg import Connection

from app.embeddings import FakeEmbedder
from app.library import PostgresLibrary, SavedBook, SaveRejected, save_book
from app.rules.catalog import CatalogRecord
from app.rules.nomination import CLOSED_MEETING
from db.queries import session_offerings

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL is not set",
)


@pytest.fixture
def connection() -> Iterator[Connection]:
    """Yield a connection whose writes are rolled back when the test ends."""
    with (
        psycopg.connect(os.environ["DATABASE_URL"]) as conn,
        conn.transaction(force_rollback=True),
    ):
        yield conn


def test_session_offerings_include_a_session_that_showed_nothing(
    connection: Connection,
):
    shown = connection.execute(
        "INSERT INTO sessions (request) VALUES (%s) RETURNING id",
        ("Two books",),
    ).fetchone()
    empty = connection.execute(
        "INSERT INTO sessions (request) VALUES (%s) RETURNING id",
        ("No books",),
    ).fetchone()
    blood_music = connection.execute(
        "INSERT INTO works (title) VALUES (%s) RETURNING id",
        ("Blood Music",),
    ).fetchone()
    dead_wake = connection.execute(
        "INSERT INTO works (title) VALUES (%s) RETURNING id",
        ("Dead Wake",),
    ).fetchone()
    assert shown is not None and empty is not None
    assert blood_music is not None and dead_wake is not None
    connection.execute(
        "INSERT INTO offerings (session_id, work_id, choice) VALUES (%s, %s, %s)",
        (shown[0], blood_music[0], "picked"),
    )
    connection.execute(
        "INSERT INTO offerings (session_id, work_id, choice) VALUES (%s, %s, %s)",
        (shown[0], dead_wake[0], "rejected"),
    )

    assert session_offerings(connection, shown[0]) == [
        ("Blood Music", "picked"),
        ("Dead Wake", "rejected"),
    ]
    assert session_offerings(connection, empty[0]) == []


def test_a_saved_nomination_is_listed_and_a_closed_meeting_does_not_add_another(
    connection: Connection,
):
    register_vector(connection)
    store = PostgresLibrary(connection, FakeEmbedder())
    description = "Query test summary for Dead Wake, not the seed row."
    record = CatalogRecord(
        "Dead Wake",
        "Erik Larson",
        2015,
        448,
        "9780804194617",
        "The Lusitania's last crossing, told from the ship and from the U-boat.",
    )
    session_id = store.begin_session("a ship sinks, the author is erik larson")
    store.save_nomination(session_id, record, description)
    saved = [book for book in store.nominations() if book.member_description == description]
    assert saved == [SavedBook("Dead Wake", "Erik Larson", 448, description)]
    connection.execute("UPDATE meeting SET accepting_nominations = false WHERE id = 1")
    before = store.nominations()
    with pytest.raises(SaveRejected, match=CLOSED_MEETING):
        save_book(
            store,
            None,
            CatalogRecord("Blood Music", "Greg Bear", 1985, None, None, None),
            "A different book.",
        )
    assert store.nominations() == before


def test_pgvector_returns_a_related_description_and_hides_an_unrelated_one(
    connection: Connection,
):
    register_vector(connection)
    store = PostgresLibrary(connection, FakeEmbedder())
    related = "A controlled society assigns people to castes and bans old books."
    session_id = store.begin_session("something like Brave New World")
    store.remember_work(
        session_id,
        CatalogRecord("Brave New World", "Aldous Huxley", 1932, 311, None, related),
    )
    hits = store.search("a book about a controlled society")
    assert any(hit.body == related and hit.title == "Brave New World" for hit in hits)
    assert store.search("a recipe for banana bread with walnuts") == []
