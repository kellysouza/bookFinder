"""Questions the finder asks its database."""

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
