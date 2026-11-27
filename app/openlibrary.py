"""Read book records from the Open Library search API."""

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from app.rules.catalog import CatalogRecord, same_book

SEARCH_URL = "https://openlibrary.org/search.json"
WORK_URL = "https://openlibrary.org"


class CatalogUnavailable(Exception):
    """Open Library could not be searched. `outcome` is stored on the search row."""

    def __init__(self, outcome: str) -> None:
        super().__init__(outcome)
        self.outcome = outcome


def parse_description(payload: dict[str, Any]) -> str | None:
    """Return the work description, whether Open Library sent a string or an object."""
    description = payload.get("description")
    if isinstance(description, str):
        return description
    if isinstance(description, dict):
        value = description.get("value")
        if isinstance(value, str):
            return value
    return None


def record_from_doc(doc: dict[str, Any], description: str | None) -> CatalogRecord | None:
    """Return a catalog record from one search document, or None when it has no title or author."""
    title = doc.get("title")
    authors = doc.get("author_name") or []
    if not isinstance(title, str) or not title.strip() or not authors:
        return None
    author = authors[0]
    if not isinstance(author, str) or not author.strip():
        return None
    year = doc.get("first_publish_year")
    pages = doc.get("number_of_pages_median")
    isbns = doc.get("isbn") or []
    isbn = isbns[0] if isbns and isinstance(isbns[0], str) else None
    return CatalogRecord(
        title=title.strip(),
        author=author.strip(),
        year=year if isinstance(year, int) else None,
        page_count=pages if isinstance(pages, int) else None,
        isbn=isbn,
        description=description,
    )


def matching_doc(docs: list[dict[str, Any]], title: str, author: str) -> dict[str, Any] | None:
    """Return the first document that is the same book as the title and author."""
    for doc in docs:
        record = record_from_doc(doc, None)
        if record is not None and same_book(title, author, record.title, record.author):
            return doc
    return None


def fetch_json(url: str) -> dict[str, Any]:
    """GET one Open Library URL and return its JSON object."""
    request = urllib.request.Request(url, headers={"User-Agent": "bookfinder/ics603"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise CatalogUnavailable("rate-limiting") from error
        raise CatalogUnavailable("down") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CatalogUnavailable("down") from error
    if not isinstance(payload, dict):
        raise CatalogUnavailable("down")
    return payload


class OpenLibraryCatalog:
    """Looks up a named book, and an author's latest book, in Open Library."""

    def __init__(self, fetch: Callable[[str], dict[str, Any]] | None = None) -> None:
        self._fetch = fetch or fetch_json

    def lookup(self, title: str, author: str) -> CatalogRecord | None:
        """Return the Open Library record for this title and author, or None."""
        url = SEARCH_URL + "?" + urllib.parse.urlencode({"title": title, "author": author, "limit": 5})
        docs = self._fetch(url).get("docs") or []
        doc = matching_doc(docs, title, author)
        if doc is None:
            return None
        return record_from_doc(doc, self._work_description(doc.get("key")))

    def newest_by_author(self, author: str) -> CatalogRecord | None:
        """Return the latest Open Library record for this author, or None."""
        url = SEARCH_URL + "?" + urllib.parse.urlencode({"author": author, "sort": "new", "limit": 5})
        docs = self._fetch(url).get("docs") or []
        for doc in docs:
            record = record_from_doc(doc, None)
            if record is not None and same_book(record.title, author, record.title, record.author):
                return record_from_doc(doc, self._work_description(doc.get("key")))
        return None

    def _work_description(self, key: object) -> str | None:
        if not isinstance(key, str) or not key.startswith("/works/"):
            return None
        payload = self._fetch(WORK_URL + key + ".json")
        return parse_description(payload)
