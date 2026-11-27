from app.rules.nomination import (
    CLOSED_MEETING,
    MISSING_RECORD,
    rejection_message,
    save_is_rejected,
)


def test_save_is_rejected_when_the_meeting_is_not_accepting_nominations():
    assert save_is_rejected(meeting_is_accepting_nominations=False)


def test_save_is_allowed_when_the_meeting_is_accepting_nominations():
    assert not save_is_rejected(meeting_is_accepting_nominations=True)


def test_a_blank_title_is_rejected_and_names_the_missing_record():
    assert rejection_message(True, "  ", "Erik Larson") == MISSING_RECORD


def test_a_closed_meeting_is_rejected_with_the_meeting_message():
    assert rejection_message(False, "Dead Wake", "Erik Larson") == CLOSED_MEETING


def test_an_open_meeting_with_a_title_and_author_may_be_saved():
    assert rejection_message(True, "Dead Wake", "Erik Larson") is None
