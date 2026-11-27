"""Questions the finder asks its database."""

from pgvector import Vector
from psycopg import Connection


def session_offerings(
    connection: Connection, session_id: int
) -> list[tuple[str, str]]:
    """Books one session showed and whether each was picked or rejected, by title."""
    rows = connection.execute(
        """
        SELECT works.title, offerings.choice
        FROM offerings
        JOIN works ON works.id = offerings.work_id
        WHERE offerings.session_id = %s
        ORDER BY works.title
        """,
        (session_id,),
    ).fetchall()
    return [(str(title), str(choice)) for title, choice in rows]


def _require_id(row: tuple[object, ...] | None) -> int:
    if row is None or not isinstance(row[0], int):
        raise RuntimeError("The insert returned no id.")
    return row[0]


def meeting_is_accepting(connection: Connection) -> bool:
    """Return whether the club meeting is accepting nominations.

    A missing row is treated as open, so a new database still accepts a save.
    """
    row = connection.execute("SELECT accepting_nominations FROM meeting WHERE id = 1").fetchone()
    if row is None:
        return True
    return bool(row[0])


def insert_session(connection: Connection, request: str) -> int:
    """Insert one search conversation and return its id."""
    row = connection.execute(
        "INSERT INTO sessions (request) VALUES (%s) RETURNING id",
        (request,),
    ).fetchone()
    return _require_id(row)


def insert_search(connection: Connection, session_id: int, words: str, outcome: str) -> None:
    """Insert one Open Library lookup."""
    connection.execute(
        "INSERT INTO searches (session_id, words_sent, outcome) VALUES (%s, %s, %s)",
        (session_id, words, outcome),
    )


def find_work_id(connection: Connection, title: str, author: str) -> int | None:
    """Return the id of this title and author, or None when the book is new."""
    row = connection.execute(
        """
        SELECT works.id
        FROM works
        JOIN authorships ON authorships.work_id = works.id
        JOIN authors ON authors.id = authorships.author_id
        WHERE lower(btrim(works.title)) = lower(%s)
          AND lower(btrim(authors.name)) = lower(%s)
        LIMIT 1
        """,
        (title.strip(), author.strip()),
    ).fetchone()
    if row is None:
        return None
    return int(row[0])


def author_id(connection: Connection, name: str) -> int:
    """Return the id of this author, inserting the row when it is new."""
    row = connection.execute(
        "INSERT INTO authors (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
        (name,),
    ).fetchone()
    if row is not None:
        return _require_id(row)
    found = connection.execute("SELECT id FROM authors WHERE name = %s", (name,)).fetchone()
    return _require_id(found)


def insert_work(
    connection: Connection,
    title: str,
    page_count: int | None,
    isbn: str | None,
    description: str | None,
) -> int:
    """Insert one confirmed book and return its id."""
    row = connection.execute(
        """
        INSERT INTO works (title, page_count, isbn, open_library_description)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (title, page_count, isbn, description),
    ).fetchone()
    return _require_id(row)


def link_author(connection: Connection, author: int, work: int) -> None:
    """Record that this author wrote this book. A repeat does nothing."""
    connection.execute(
        """
        INSERT INTO authorships (author_id, work_id) VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        (author, work),
    )


def offer_work(connection: Connection, session_id: int, work_id: int) -> None:
    """Record that this session picked this book. A repeat does nothing."""
    connection.execute(
        """
        INSERT INTO offerings (session_id, work_id, choice) VALUES (%s, %s, 'picked')
        ON CONFLICT DO NOTHING
        """,
        (session_id, work_id),
    )


def session_has_nomination(connection: Connection, session_id: int) -> bool:
    """Return whether this session already saved a nomination."""
    row = connection.execute(
        "SELECT id FROM nominations WHERE session_id = %s",
        (session_id,),
    ).fetchone()
    return row is not None


def insert_nomination(
    connection: Connection, work_id: int, session_id: int | None, member_description: str
) -> None:
    """Insert the member's saved description. The local list is the saved result."""
    connection.execute(
        """
        INSERT INTO nominations (work_id, session_id, member_description, post_succeeded)
        VALUES (%s, %s, %s, true)
        """,
        (work_id, session_id, member_description),
    )


def list_nominations(connection: Connection) -> list[tuple[str, str, int | None, str]]:
    """Return saved nominations as title, authors, page count, and the member's description."""
    rows = connection.execute(
        """
        SELECT works.title,
               string_agg(authors.name, ', ' ORDER BY authors.name),
               works.page_count,
               nominations.member_description
        FROM nominations
        JOIN works ON works.id = nominations.work_id
        JOIN authorships ON authorships.work_id = works.id
        JOIN authors ON authors.id = authorships.author_id
        GROUP BY nominations.id, works.title, works.page_count, nominations.member_description
        ORDER BY nominations.id
        """
    ).fetchall()
    listed: list[tuple[str, str, int | None, str]] = []
    for title, author, pages, description in rows:
        page_count = pages if isinstance(pages, int) else None
        listed.append((str(title), str(author), page_count, str(description)))
    return listed


def insert_passage(
    connection: Connection,
    work_id: int | None,
    session_id: int | None,
    source: str,
    body: str,
    content_hash: str,
    embedding: list[float],
) -> None:
    """Store one description and its embedding. The same hash is not stored twice."""
    connection.execute(
        """
        INSERT INTO passages (work_id, session_id, source, body, content_hash, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (content_hash) DO NOTHING
        """,
        (work_id, session_id, source, body, content_hash, Vector(embedding)),
    )


def similar_passages(
    connection: Connection, embedding: list[float], threshold: float, limit: int
) -> list[tuple[str, str, str | None, float]]:
    """Return passages whose cosine similarity meets the threshold, nearest first.

    The score is 1 minus pgvector cosine distance.
    """
    rows = connection.execute(
        """
        SELECT passages.body,
               passages.source,
               works.title,
               1 - (passages.embedding <=> %s) AS score
        FROM passages
        LEFT JOIN works ON works.id = passages.work_id
        WHERE 1 - (passages.embedding <=> %s) >= %s
        ORDER BY passages.embedding <=> %s
        LIMIT %s
        """,
        (Vector(embedding), Vector(embedding), threshold, Vector(embedding), limit),
    ).fetchall()
    return [(str(body), str(source), None if title is None else str(title), float(score)) for body, source, title, score in rows]
