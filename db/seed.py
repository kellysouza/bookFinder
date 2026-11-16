"""Load sample rows into an empty database. Stops if rows already exist."""

import os
import sys

import psycopg
from dotenv import load_dotenv
from psycopg import Connection

load_dotenv()

LATER_REQUEST = (
    "I want something funny about the end of the world, but I also "
    "keep thinking about that mystery on a train I passed over earlier."
)


def inserted_id(
    connection: Connection, statement: str, values: tuple[object, ...]
) -> int:
    """Insert one row and return the id Postgres generated."""
    row = connection.execute(statement, values).fetchone()
    if row is None or not isinstance(row[0], int):
        raise RuntimeError("The insert returned no id.")
    return row[0]


def main() -> None:
    """Insert the sample sessions, searches, books, and nominations."""
    with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
        existing = connection.execute("SELECT count(*) FROM sessions").fetchone()
        if existing is not None and existing[0] > 0:
            sys.exit("sessions already has rows, so nothing was changed.")

        greg_bear = inserted_id(
            connection,
            "INSERT INTO authors (name) VALUES (%s) RETURNING id",
            ("Greg Bear",),
        )
        erik_larson = inserted_id(
            connection,
            "INSERT INTO authors (name) VALUES (%s) RETURNING id",
            ("Erik Larson",),
        )
        agatha_christie = inserted_id(
            connection,
            "INSERT INTO authors (name) VALUES (%s) RETURNING id",
            ("Agatha Christie",),
        )
        paula_hawkins = inserted_id(
            connection,
            "INSERT INTO authors (name) VALUES (%s) RETURNING id",
            ("Paula Hawkins",),
        )
        andy_weir = inserted_id(
            connection,
            "INSERT INTO authors (name) VALUES (%s) RETURNING id",
            ("Andy Weir",),
        )
        terry_pratchett = inserted_id(
            connection,
            "INSERT INTO authors (name) VALUES (%s) RETURNING id",
            ("Terry Pratchett",),
        )
        neil_gaiman = inserted_id(
            connection,
            "INSERT INTO authors (name) VALUES (%s) RETURNING id",
            ("Neil Gaiman",),
        )
        inserted_id(
            connection,
            "INSERT INTO authors (name) VALUES (%s) RETURNING id",
            ("Octavia E. Butler",),
        )

        blood_music_session = inserted_id(
            connection,
            "INSERT INTO sessions (request) VALUES (%s) RETURNING id",
            ("Blood Music by Greg Bear",),
        )
        ship_session = inserted_id(
            connection,
            "INSERT INTO sessions (request) VALUES (%s) RETURNING id",
            ("a ship sinks, the author is erik larson",),
        )
        train_session = inserted_id(
            connection,
            "INSERT INTO sessions (request) VALUES (%s) RETURNING id",
            ("a mystery on a train",),
        )
        martian_session = inserted_id(
            connection,
            "INSERT INTO sessions (request) VALUES (%s) RETURNING id",
            ("The Martian",),
        )
        later_session = inserted_id(
            connection,
            "INSERT INTO sessions (request) VALUES (%s) RETURNING id",
            (LATER_REQUEST,),
        )

        blood_music = inserted_id(
            connection,
            "INSERT INTO works "
            "(title, page_count, isbn, open_library_description) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (
                "Blood Music",
                None,
                "9781857987621",
                "A scientist injects himself with intelligent cells, and they remake him.",
            ),
        )
        dead_wake = inserted_id(
            connection,
            "INSERT INTO works "
            "(title, page_count, isbn, open_library_description) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (
                "Dead Wake",
                448,
                "9780804194617",
                "The Lusitania's last crossing, told from the ship and from the U-boat.",
            ),
        )
        orient_express = inserted_id(
            connection,
            "INSERT INTO works "
            "(title, page_count, isbn, open_library_description) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (
                "Murder on the Orient Express",
                240,
                "9780008264604",
                "A snowbound train, and one passenger is dead.",
            ),
        )
        girl_on_the_train = inserted_id(
            connection,
            "INSERT INTO works "
            "(title, page_count, isbn, open_library_description) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (
                "The Girl on the Train",
                360,
                "9781400026791",
                "A commuter sees the same couple each day, and then the woman is gone.",
            ),
        )
        the_martian = inserted_id(
            connection,
            "INSERT INTO works "
            "(title, page_count, isbn, open_library_description) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (
                "The Martian",
                407,
                None,
                "An astronaut is left on Mars and has to grow food until a rescue can reach him.",
            ),
        )
        project_hail_mary = inserted_id(
            connection,
            "INSERT INTO works "
            "(title, page_count, isbn, open_library_description) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            ("Project Hail Mary", 496, "9780593135204", None),
        )
        good_omens = inserted_id(
            connection,
            "INSERT INTO works "
            "(title, page_count, isbn, open_library_description) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (
                "Good Omens",
                400,
                "9780060853976",
                "An angel and a demon misplace the Antichrist and try to stop the apocalypse.",
            ),
        )

        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO searches (session_id, words_sent, outcome) "
                "VALUES (%s, %s, %s)",
                [
                    (blood_music_session, "Blood Music Greg Bear", "books came back"),
                    (
                        ship_session,
                        "a ship sinks, the author is erik larson",
                        "nothing matched",
                    ),
                    (ship_session, "Dead Wake Erik Larson", "books came back"),
                    (train_session, "mystery train", "rate-limiting"),
                    (train_session, "mystery train", "down"),
                    (
                        train_session,
                        "Murder on the Orient Express Agatha Christie",
                        "books came back",
                    ),
                    (martian_session, "The Martian Andy Weir", "books came back"),
                    (later_session, LATER_REQUEST, "books came back"),
                ],
            )
            cursor.executemany(
                "INSERT INTO authorships (author_id, work_id) VALUES (%s, %s)",
                [
                    (greg_bear, blood_music),
                    (erik_larson, dead_wake),
                    (agatha_christie, orient_express),
                    (paula_hawkins, girl_on_the_train),
                    (andy_weir, the_martian),
                    (andy_weir, project_hail_mary),
                    (terry_pratchett, good_omens),
                    (neil_gaiman, good_omens),
                ],
            )
            cursor.executemany(
                "INSERT INTO offerings (session_id, work_id, choice) "
                "VALUES (%s, %s, %s)",
                [
                    (blood_music_session, blood_music, "picked"),
                    (ship_session, dead_wake, "picked"),
                    (train_session, orient_express, "rejected"),
                    (train_session, girl_on_the_train, "rejected"),
                    (martian_session, the_martian, "picked"),
                    (martian_session, project_hail_mary, "rejected"),
                    (later_session, orient_express, "picked"),
                    (later_session, good_omens, "rejected"),
                ],
            )
            cursor.executemany(
                "INSERT INTO nominations "
                "(work_id, session_id, member_description, post_succeeded) "
                "VALUES (%s, %s, %s, %s)",
                [
                    (
                        blood_music,
                        blood_music_session,
                        "I couldn't put this down.",
                        True,
                    ),
                    (
                        dead_wake,
                        ship_session,
                        "The club should read how that ship went down.",
                        False,
                    ),
                    (
                        orient_express,
                        later_session,
                        "I passed on this once, and I want it for the next meeting.",
                        True,
                    ),
                    (
                        blood_music,
                        None,
                        "A later member still wants Blood Music, for a different reason.",
                        True,
                    ),
                ],
            )
    print("Sample rows loaded.")


if __name__ == "__main__":
    main()
