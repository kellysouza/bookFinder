from app.rules.books import asks_for_newest
from app.rules.catalog import (
    ASK_FOR_MORE,
    CatalogRecord,
    chosen_record,
    description_is_usable,
    keep_record,
    reply_after_check,
    same_book,
)


class _Book:
    def __init__(self, title: str, author: str) -> None:
        self.title = title
        self.author = author


def test_a_description_of_39_characters_is_not_usable():
    assert description_is_usable("a" * 39) is False


def test_a_latin_description_of_40_characters_is_usable():
    assert description_is_usable("a" * 40) is True


def test_a_non_latin_description_is_not_usable():
    assert description_is_usable("é" * 40) is False


def test_a_subtitle_is_the_same_book():
    assert same_book("Dead Wake", "Erik Larson", "Dead Wake: The Last Crossing", "Erik Larson")


def test_a_different_book_with_bear_in_the_title_does_not_match():
    assert same_book("Blood Music", "Greg Bear", "The Bear and the Nightingale", "Katherine Arden") is False


def test_a_later_open_library_year_replaces_the_named_book():
    named = CatalogRecord("The Way of Kings", "Brandon Sanderson", 2010, 1000, None, "x" * 40)
    newest = CatalogRecord("Wind and Truth", "Brandon Sanderson", 2024, 1300, None, "y" * 40)
    assert chosen_record(named, newest, asks_for_newest("his newest one")) == newest
    assert keep_record(_Book("The Way of Kings", "Brandon Sanderson"), newest, True)


def test_a_miss_asks_for_more_and_names_no_book():
    assert reply_after_check("That might be some other book.", 1, 0) == ASK_FOR_MORE


def test_a_partial_match_drops_the_reply_that_named_the_other_book():
    reply = reply_after_check("That might be The Bear and the Nightingale.", 2, 1)
    assert reply == "I kept only the books Open Library returned."
    assert "Nightingale" not in reply
