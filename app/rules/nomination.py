"""Business rules for choosing and saving a nomination."""


def save_is_rejected(meeting_is_accepting_nominations: bool) -> bool:
    """Return whether a save is rejected because the meeting is closed.

    A save is rejected when the meeting is not accepting nominations.
    The book is not added.
    """
    return not meeting_is_accepting_nominations


MISSING_RECORD = "The title and author from Open Library are missing, so the book was not added."
CLOSED_MEETING = "This meeting is not accepting nominations. The book was not added."
ALREADY_SAVED = "This search already has a nomination. The saved description was left unchanged."


def rejection_message(
    meeting_is_accepting_nominations: bool, title: str, author: str
) -> str | None:
    """Return the error to show, or None when the save may be written.

    A blank title or author is rejected. A closed meeting is rejected.
    Either way the nominations already stored stay as they are.
    """
    if not title.strip() or not author.strip():
        return MISSING_RECORD
    if save_is_rejected(meeting_is_accepting_nominations):
        return CLOSED_MEETING
    return None
