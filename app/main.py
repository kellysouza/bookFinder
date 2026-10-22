"""FastAPI routes and the page. No business rules here."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from app.agent import BookOption, InquiryResponse, Nomination

app = FastAPI()
PAGE = Path(__file__).parent / "page.html"

PLACEHOLDER_RESPONSE = InquiryResponse(
    reply="This is a placeholder reply.",
    books=[
        BookOption(
            title="Placeholder title",
            author="Placeholder author",
            summary="Placeholder summary",
            reason="Placeholder reason",
        )
    ],
    nomination=Nomination(
        title="Placeholder title",
        author="Placeholder author",
        summary="Placeholder summary",
        page_count=None,
    ),
)


class InquiryRequest(BaseModel):
    """The text from the one box."""

    model_config = ConfigDict(extra="forbid")

    text: str


@app.get("/")
def home() -> HTMLResponse:
    """Return the book finder page."""
    return HTMLResponse(PAGE.read_text(encoding="utf-8"))


@app.post("/inquire")
def inquire(inquiry: InquiryRequest) -> InquiryResponse:
    """Accept the typed text and return the fixed placeholder."""
    del inquiry
    return PLACEHOLDER_RESPONSE
