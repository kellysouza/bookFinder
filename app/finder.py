"""Confirm the model's books in the catalog, then draft a summary for each one kept."""

from collections.abc import Awaitable, Callable
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.models import Model

from app.agent import BookOption, FinderRequest, answer
from app.library import FinderStore
from app.openlibrary import CatalogUnavailable
from app.rules.books import asks_for_newest
from app.rules.catalog import (
    CatalogRecord,
    chosen_record,
    keep_record,
    reply_after_check,
    summary_source_name,
)
from app.rules.conversation import MAX_BOOKS
from app.summary import SummarySource, write_summary

Summarize = Callable[[str, str, str, str | None, Model], Awaitable[tuple[str, SummarySource]]]


class ShownBook(BaseModel):
    """One confirmed book, with the Open Library record and the summary source."""

    model_config = ConfigDict(extra="forbid")

    title: str
    author: str
    year: int | None
    reason: str
    page_count: int | None
    isbn: str | None
    open_library_description: str | None
    summary: str
    summary_source: SummarySource
    source_label: str


class InquireResult(BaseModel):
    """The reply, the confirmed books, and the session that stored the search."""

    model_config = ConfigDict(extra="forbid")

    reply: str
    books: list[ShownBook] = Field(max_length=MAX_BOOKS)
    session_id: int


class Catalog(Protocol):
    """The lookup the finder uses. Open Library is the production catalog."""

    def lookup(self, title: str, author: str) -> CatalogRecord | None:
        """Return the record for this title and author, or None when nothing matches."""

    def newest_by_author(self, author: str) -> CatalogRecord | None:
        """Return that author's latest record, or None."""


def lookup_one(
    book: BookOption, catalog: Catalog, wants_newest: bool
) -> tuple[CatalogRecord | None, str]:
    """Return the record to show for one named book, and how the lookup ended.

    The outcome is one of the search table's allowed values.
    """
    try:
        named = catalog.lookup(book.title, book.author)
    except CatalogUnavailable as error:
        return None, error.outcome
    outcome = "books came back" if named is not None else "nothing matched"
    if not wants_newest:
        if keep_record(book, named, False):
            return named, outcome
        return None, outcome
    try:
        newest = catalog.newest_by_author(book.author)
    except CatalogUnavailable:
        newest = None
    chosen = chosen_record(named, newest, True)
    if keep_record(book, chosen, True):
        return chosen, "books came back"
    return None, outcome


async def prepare(
    request: FinderRequest,
    model: Model,
    catalog: Catalog,
    store: FinderStore,
    summarize: Summarize = write_summary,
) -> InquireResult:
    """Answer the member, keep only confirmed books, and store the search."""
    found = await answer(request, model)
    wants_newest = asks_for_newest(request.turns[-1].text)
    kept: list[tuple[BookOption, CatalogRecord]] = []
    searches: list[tuple[str, str]] = []
    for book in found.books:
        record, outcome = lookup_one(book, catalog, wants_newest)
        searches.append((f"{book.title} {book.author}", outcome))
        if record is not None:
            kept.append((book, record))
    reply = reply_after_check(found.reply, len(found.books), len(kept))
    member_text = request.turns[-1].text
    session_id = request.session_id
    if session_id is None:
        session_id = store.begin_session(member_text)
    store.remember_member_text(session_id, member_text)
    for words, outcome in searches:
        store.remember_search(session_id, words, outcome)
    shown: list[ShownBook] = []
    for book, record in kept:
        summary, source = await summarize(
            record.title, record.author, member_text, record.description, model
        )
        store.remember_work(session_id, record)
        shown.append(_shown(book, record, summary, source))
    return InquireResult(reply=reply, books=shown, session_id=session_id)


def _shown(book: BookOption, record: CatalogRecord, summary: str, source: SummarySource) -> ShownBook:
    year = record.year if record.year is not None else book.year
    return ShownBook(
        title=record.title,
        author=record.author,
        year=year,
        reason=book.reason,
        page_count=record.page_count,
        isbn=record.isbn,
        open_library_description=record.description,
        summary=summary,
        summary_source=source,
        source_label=summary_source_name(source),
    )
