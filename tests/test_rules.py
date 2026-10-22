from app.rules import save_is_rejected


def test_save_is_rejected_when_the_meeting_is_not_accepting_nominations():
    assert save_is_rejected(meeting_is_accepting_nominations=False)


def test_save_is_allowed_when_the_meeting_is_accepting_nominations():
    assert not save_is_rejected(meeting_is_accepting_nominations=True)
