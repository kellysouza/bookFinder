from typing import cast

import pytest
from psycopg import Connection

from app.db import DatabaseUnavailable, connect, postgres_answers


class AnsweringConnection:
    def execute(self, _query: str) -> "AnsweringConnection":
        return self

    def fetchone(self) -> tuple[int]:
        return (1,)


def test_postgres_answers_when_select_one_returns_one():
    assert postgres_answers(cast(Connection, AnsweringConnection())) is True


def test_connect_reports_a_missing_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.db.load_dotenv", lambda: False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseUnavailable, match="DATABASE_URL is not set"):
        connect()
