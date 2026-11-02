"""Rules for cleaning the model's book list, and the newest-book note."""

import re
from typing import Protocol

from app.rules.conversation import MAX_BOOKS

NEWEST_NOTE = (
    "This is the newest I know of. My book knowledge stops at a cutoff, "
    "so there may be a newer one."
)

_NEWEST_PATTERN = re.compile(r"\b(newest|latest|most recent)\b", re.IGNORECASE)
_LEADING_ARTICLE = re.compile(r"^(the|a) ")


class NamedBook(Protocol):
    """A book with a title and an author."""

    title: str
    author: str


def _normalize(text: str) -> str:
    """Return the text lowercased, with whitespace runs collapsed to one space."""
    return " ".join(text.lower().split())


def _book_key(book: NamedBook) -> tuple[str, str]:
    """Return the key that two copies of the same book share."""
    title = _LEADING_ARTICLE.sub("", _normalize(book.title), count=1)
    return title, _normalize(book.author)


def drop_unusable_books[B: NamedBook](books: list[B]) -> list[B]:
    """Return the books worth showing, in their original order.

    A book is dropped when its title or author is blank, or when it repeats
    an earlier book apart from case, spacing, or a leading "the" or "a".
    At most MAX_BOOKS books are kept.
    """
    kept: list[B] = []
    seen: set[tuple[str, str]] = set()
    for book in books:
        if not book.title.strip() or not book.author.strip():
            continue
        key = _book_key(book)
        if key in seen:
            continue
        seen.add(key)
        kept.append(book)
        if len(kept) == MAX_BOOKS:
            break
    return kept


def asks_for_newest(member_line: str) -> bool:
    """Return whether the member asks for the newest, latest, or most recent book."""
    return _NEWEST_PATTERN.search(member_line) is not None
