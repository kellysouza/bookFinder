"""The finder's Postgres connection. SQL lives here."""

import os
from collections.abc import Iterator

import psycopg
from dotenv import load_dotenv
from psycopg import Connection


class DatabaseUnavailable(Exception):
    """The finder could not open Postgres."""


def load_database_url() -> str:
    """Return the pooled connection string from the environment."""
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise DatabaseUnavailable("DATABASE_URL is not set.")
    return url


def connect() -> Connection:
    """Open one pooled connection, or raise when Postgres cannot be reached."""
    try:
        return psycopg.connect(load_database_url())
    except psycopg.Error as error:
        raise DatabaseUnavailable("Postgres did not connect.") from error


def postgres_answers(connection: Connection) -> bool:
    """Return whether this connection answers SELECT 1."""
    row = connection.execute("SELECT 1").fetchone()
    return row is not None and row[0] == 1


def connection() -> Iterator[Connection]:
    """Yield one connection and close it when the caller finishes."""
    with connect() as opened:
        yield opened
