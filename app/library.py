"""Stored sessions, books, nominations, and description embeddings."""

from dataclasses import dataclass
from typing import Protocol

from psycopg import Connection

from app.embeddings import Embedder, FakeEmbedder, content_hash
from app.rules.catalog import CatalogRecord, same_book
from app.rules.nomination import ALREADY_SAVED, rejection_message
from app.rules.search import SIMILARITY_THRESHOLD, cosine_similarity, passes_threshold
from db import queries


class SaveRejected(Exception):
    """A save was refused. The nominations already stored are unchanged."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class SavedBook:
    """One nomination the member can reopen."""

    title: str
    author: str
    page_count: int | None
    member_description: str


@dataclass(frozen=True)
class PassageHit:
    """One stored description that matched a meaning search."""

    body: str
    source: str
    title: str | None
    score: float


class FinderStore(Protocol):
    """What the finder reads and writes. Postgres is the production store."""

    def meeting_is_accepting(self) -> bool:
        """Return whether a save may add a nomination."""

    def begin_session(self, request: str) -> int:
        """Store one search conversation and return its id."""

    def remember_search(self, session_id: int, words: str, outcome: str) -> None:
        """Store one catalog lookup."""

    def remember_member_text(self, session_id: int, text: str) -> None:
        """Store what the member typed, for search by meaning."""

    def remember_work(self, session_id: int, record: CatalogRecord) -> int:
        """Store a confirmed book and its Open Library description."""

    def save_nomination(
        self, session_id: int | None, record: CatalogRecord, member_description: str
    ) -> None:
        """Store the description the member saved. Raises SaveRejected when the session already has one."""

    def nominations(self) -> list[SavedBook]:
        """Return the saved nominations, oldest first."""

    def search(self, query: str) -> list[PassageHit]:
        """Return stored descriptions close in meaning to the query."""


def save_book(store: FinderStore, session_id: int | None, record: CatalogRecord, member_description: str) -> None:
    """Save a nomination when the meeting is open and the record has a title and author.

    A rejection raises SaveRejected and writes nothing.
    """
    message = rejection_message(store.meeting_is_accepting(), record.title, record.author)
    if message is not None:
        raise SaveRejected(message)
    store.save_nomination(session_id, record, member_description)


class MemoryLibrary:
    """An in-memory store for tests. Search uses the fake embedder."""

    def __init__(self, embedder: Embedder | None = None) -> None:
        self.embedder = embedder or FakeEmbedder()
        self.accepting = True
        self.sessions: list[str] = []
        self.searches: list[tuple[int, str, str]] = []
        self.works: list[CatalogRecord] = []
        self._nominations: list[tuple[int | None, int, str]] = []
        self._passages: list[tuple[list[float], str, str, str | None]] = []
        self._hashes: set[str] = set()

    def meeting_is_accepting(self) -> bool:
        return self.accepting

    def begin_session(self, request: str) -> int:
        self.sessions.append(request)
        return len(self.sessions)

    def remember_search(self, session_id: int, words: str, outcome: str) -> None:
        self.searches.append((session_id, words, outcome))

    def remember_member_text(self, session_id: int, text: str) -> None:
        self._add_passage(None, session_id, "member_typed", text, None)

    def remember_work(self, session_id: int, record: CatalogRecord) -> int:
        work_id = self._work_id(record)
        if record.description:
            self._add_passage(work_id, session_id, "open_library", record.description, record.title)
        return work_id

    def save_nomination(
        self, session_id: int | None, record: CatalogRecord, member_description: str
    ) -> None:
        if session_id is not None and any(saved == session_id for saved, _, _ in self._nominations):
            raise SaveRejected(ALREADY_SAVED)
        work_id = self._work_id(record)
        self._nominations.append((session_id, work_id, member_description))
        self._add_passage(work_id, session_id, "member_saved", member_description, record.title)

    def nominations(self) -> list[SavedBook]:
        saved: list[SavedBook] = []
        for _session, work_id, description in self._nominations:
            record = self.works[work_id - 1]
            saved.append(
                SavedBook(record.title, record.author, record.page_count, description)
            )
        return saved

    def search(self, query: str) -> list[PassageHit]:
        if not query.strip():
            return []
        vector = self.embedder.embed([query])[0]
        hits: list[PassageHit] = []
        for stored, body, source, title in self._passages:
            score = cosine_similarity(vector, stored)
            if passes_threshold(score):
                hits.append(PassageHit(body, source, title, score))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:5]

    def _work_id(self, record: CatalogRecord) -> int:
        for index, stored in enumerate(self.works, start=1):
            if same_book(record.title, record.author, stored.title, stored.author):
                return index
        self.works.append(record)
        return len(self.works)

    def _add_passage(
        self, work_id: int | None, session_id: int | None, source: str, text: str, title: str | None
    ) -> None:
        if not text.strip():
            return
        digest = content_hash(self.embedder.model, source, f"{work_id}:{session_id}", text)
        if digest in self._hashes:
            return
        self._hashes.add(digest)
        vector = self.embedder.embed([text])[0]
        self._passages.append((vector, text, source, title))


class PostgresLibrary:
    """The finder store backed by Postgres and pgvector."""

    def __init__(self, connection: Connection, embedder: Embedder) -> None:
        self._connection = connection
        self.embedder = embedder

    def meeting_is_accepting(self) -> bool:
        return queries.meeting_is_accepting(self._connection)

    def begin_session(self, request: str) -> int:
        return queries.insert_session(self._connection, request)

    def remember_search(self, session_id: int, words: str, outcome: str) -> None:
        queries.insert_search(self._connection, session_id, words, outcome)

    def remember_member_text(self, session_id: int, text: str) -> None:
        self._add_passage(None, session_id, "member_typed", text)

    def remember_work(self, session_id: int, record: CatalogRecord) -> int:
        work_id = self._work_id(record)
        if record.description:
            self._add_passage(work_id, session_id, "open_library", record.description)
        return work_id

    def save_nomination(
        self, session_id: int | None, record: CatalogRecord, member_description: str
    ) -> None:
        if session_id is not None and queries.session_has_nomination(self._connection, session_id):
            raise SaveRejected(ALREADY_SAVED)
        work_id = self._work_id(record)
        if session_id is not None:
            queries.offer_work(self._connection, session_id, work_id)
        queries.insert_nomination(self._connection, work_id, session_id, member_description)
        self._add_passage(work_id, session_id, "member_saved", member_description)

    def nominations(self) -> list[SavedBook]:
        return [
            SavedBook(title, author, pages, description)
            for title, author, pages, description in queries.list_nominations(self._connection)
        ]

    def search(self, query: str) -> list[PassageHit]:
        if not query.strip():
            return []
        vector = self.embedder.embed([query])[0]
        rows = queries.similar_passages(self._connection, vector, SIMILARITY_THRESHOLD, 5)
        return [PassageHit(body, source, title, score) for body, source, title, score in rows]

    def _work_id(self, record: CatalogRecord) -> int:
        found = queries.find_work_id(self._connection, record.title, record.author)
        if found is not None:
            return found
        work_id = queries.insert_work(
            self._connection, record.title, record.page_count, record.isbn, record.description
        )
        queries.link_author(self._connection, queries.author_id(self._connection, record.author), work_id)
        return work_id

    def _add_passage(self, work_id: int | None, session_id: int | None, source: str, text: str) -> None:
        if not text.strip():
            return
        digest = content_hash(self.embedder.model, source, f"{work_id}:{session_id}", text)
        vector = self.embedder.embed([text])[0]
        queries.insert_passage(self._connection, work_id, session_id, source, text, digest, vector)
