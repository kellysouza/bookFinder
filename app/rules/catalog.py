"""Which Open Library records may be shown, and where a summary comes from."""

from dataclasses import dataclass

from app.rules.books import NamedBook, same_named_book

MIN_USABLE_DESCRIPTION = 40
MIN_LATIN_LETTER_SHARE = 0.8

ASK_FOR_MORE = (
    "I couldn't confirm that book in Open Library. "
    "Can you share another detail, such as the author or a word from the title?"
)
KEPT_NOTE = "I kept only the books Open Library returned."


@dataclass(frozen=True)
class CatalogRecord:
    """One book Open Library returned."""

    title: str
    author: str
    year: int | None
    page_count: int | None
    isbn: str | None
    description: str | None


def description_is_usable(description: str | None) -> bool:
    """Return whether an Open Library description can be rewritten as the summary.

    A usable description has at least 40 characters, and at least four in five
    of its letters are basic Latin letters. A missing, tiny, or non-English
    description is not usable.
    """
    if description is None:
        return False
    text = description.strip()
    if len(text) < MIN_USABLE_DESCRIPTION:
        return False
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    latin = sum(1 for char in letters if ("A" <= char <= "Z") or ("a" <= char <= "z"))
    return latin / len(letters) >= MIN_LATIN_LETTER_SHARE


def same_book(title: str, author: str, other_title: str, other_author: str) -> bool:
    """Return whether two title-and-author pairs are the same book."""
    left = _Named(title, author)
    right = _Named(other_title, other_author)
    if same_named_book(left, right):
        return True
    return _titles_match(title, other_title) and _authors_match(author, other_author)


def chosen_record(
    named: CatalogRecord | None, newest: CatalogRecord | None, wants_newest: bool
) -> CatalogRecord | None:
    """Return the record to show, preferring a later Open Library year when asked.

    The later record is used only when it names the same author.
    """
    if not wants_newest or newest is None:
        return named
    if named is None:
        return newest
    newest_year = newest.year if newest.year is not None else -1
    named_year = named.year if named.year is not None else -1
    if newest_year > named_year and _authors_match(named.author, newest.author):
        return newest
    return named


def keep_record(book: NamedBook, record: CatalogRecord | None, wants_newest: bool) -> bool:
    """Return whether this Open Library record may be shown for the named book."""
    if record is None:
        return False
    if same_book(book.title, book.author, record.title, record.author):
        return True
    return wants_newest and _authors_match(book.author, record.author)


def reply_after_check(reply: str, named_count: int, kept_count: int) -> str:
    """Return the reply after books Open Library did not confirm are dropped.

    When nothing is confirmed, the reply asks for more and names no book.
    When some are dropped, the reply says only the confirmed books were kept.
    """
    if named_count > 0 and kept_count == 0:
        return ASK_FOR_MORE
    if kept_count < named_count:
        return KEPT_NOTE
    return reply


def summary_source_name(source: str) -> str:
    """Return the sentence the card shows for where the summary came from."""
    if source == "open_library":
        return "Summary drawn from the Open Library description."
    if source == "model":
        return "Summary not from Open Library. It is what the model already knew."
    return "The summary is waiting for you to write it."


class _Named:
    def __init__(self, title: str, author: str) -> None:
        self.title = title
        self.author = author


def _collapsed(text: str) -> str:
    """Return the text lowercased, with whitespace runs collapsed to one space."""
    return " ".join(text.lower().split())


def _titles_match(left: str, right: str) -> bool:
    """Return whether two titles match, including a longer subtitle."""
    first = _collapsed(left)
    second = _collapsed(right)
    if first == second:
        return True
    shorter, longer = (first, second) if len(first) <= len(second) else (second, first)
    return len(shorter) >= 8 and longer.startswith(shorter)


def _authors_match(left: str, right: str) -> bool:
    """Return whether two author strings name the same person."""
    first = _collapsed(left)
    second = _collapsed(right)
    if first == second:
        return True
    words = [word for word in first.split() if len(word) > 2]
    other = second.split()
    return bool(words) and all(word in other for word in words)
