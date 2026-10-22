"""Response models for the book finder. No model is called yet."""

from pydantic import BaseModel, ConfigDict


class BookOption(BaseModel):
    """One book the finder can show."""

    model_config = ConfigDict(extra="forbid")

    title: str
    author: str
    summary: str
    reason: str


class Nomination(BaseModel):
    """Title, author, summary, and page count for the nomination form."""

    model_config = ConfigDict(extra="forbid")

    title: str
    author: str
    summary: str
    page_count: int | None


class InquiryResponse(BaseModel):
    """The reply, up to three books, and the nomination form."""

    model_config = ConfigDict(extra="forbid")

    reply: str
    books: list[BookOption]
    nomination: Nomination
