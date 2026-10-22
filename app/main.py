"""FastAPI routes and the page. No business rules here."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict

from app.agent import InquiryResponse, ask_finder

app = FastAPI()
PAGE = Path(__file__).parent / "page.html"


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
    """Accept the typed text and return the finder's reply."""
    if not inquiry.text.strip():
        raise HTTPException(status_code=422, detail="Enter a book or a kind of book.")
    return ask_finder(inquiry.text)
