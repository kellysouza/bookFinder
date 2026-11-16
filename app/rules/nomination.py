"""Business rules for choosing and saving a nomination."""


def save_is_rejected(meeting_is_accepting_nominations: bool) -> bool:
    """Return whether a save is rejected because the meeting is closed.

    A save is rejected when the meeting is not accepting nominations.
    The book is not added.
    """
    return not meeting_is_accepting_nominations
