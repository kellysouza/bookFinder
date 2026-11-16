"""Tests for the questions the finder asks its database."""

import os
from collections.abc import Iterator

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg import Connection

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
