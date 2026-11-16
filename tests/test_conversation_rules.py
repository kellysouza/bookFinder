from app.rules.conversation import (
    MAX_BOOKS,
    MAX_FINDER_REPLY_CHARS,
    MAX_MEMBER_LINE_CHARS,
    MAX_MEMBER_LINES,
)


def test_a_conversation_has_at_most_30_member_lines():
    assert MAX_MEMBER_LINES == 30


def test_a_member_line_has_at_most_500_characters():
    assert MAX_MEMBER_LINE_CHARS == 500


def test_a_finder_reply_sent_back_has_at_most_2000_characters():
    assert MAX_FINDER_REPLY_CHARS == 2000


def test_the_finder_shows_at_most_3_books():
    assert MAX_BOOKS == 3
