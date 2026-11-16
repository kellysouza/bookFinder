from dataclasses import dataclass

import pytest

from app.rules.books import asks_for_newest, drop_unusable_books


@dataclass
class Book:
    title: str
    author: str


def test_drops_a_book_with_a_blank_title_or_author():
    books = [Book("  ", "Greg Bear"), Book("Blood Music", ""), Book("Dead Wake", "Erik Larson")]
    assert drop_unusable_books(books) == [Book("Dead Wake", "Erik Larson")]


def test_drops_a_repeat_that_differs_by_case_spacing_or_leading_article():
    books = [Book("The Martian", "Andy Weir"), Book("martian", "andy  weir"), Book("A Martian", "Andy Weir")]
    assert drop_unusable_books(books) == [Book("The Martian", "Andy Weir")]


def test_keeps_the_same_title_by_a_different_author():
    books = [Book("Solaris", "Stanisław Lem"), Book("Solaris", "Someone Else")]
    assert len(drop_unusable_books(books)) == 2


def test_keeps_at_most_three_books_in_order():
    books = [Book(f"Book {n}", "Author") for n in range(5)]
    assert [b.title for b in drop_unusable_books(books)] == ["Book 0", "Book 1", "Book 2"]


@pytest.mark.parametrize(
    "line",
    ["Brandon Sanderson's newest one", "what's her LATEST book?", "the most recent Expanse book"],
)
def test_asks_for_newest(line):
    assert asks_for_newest(line)


@pytest.mark.parametrize(
    "line",
    ["the new Becky Chambers book", "something newer than Dune", "yes, that one"],
)
def test_does_not_ask_for_newest(line):
    assert not asks_for_newest(line)
