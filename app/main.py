"""FastAPI routes and the page. No business rules here."""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

import logfire
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from psycopg import Connection
from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from app.agent import FinderRequest, gateway_model
from app.db import DatabaseUnavailable, connection, postgres_answers
from app.embeddings import Embedder, GatewayEmbedder
from app.finder import InquireResult, Summarize, prepare
from app.library import PassageHit, PostgresLibrary, SavedBook, SaveRejected, save_book
from app.openlibrary import OpenLibraryCatalog
from app.rules.catalog import CatalogRecord
from app.summary import write_summary

logfire.configure(service_name="bookfinder", send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()

app = FastAPI()
PAGE = Path(__file__).parent / "page.html"


class SaveRequest(BaseModel):
    """The nomination form. Title and author come from Open Library and are not edited."""

    model_config = ConfigDict(extra="forbid")

    session_id: int | None = None
    title: str
    author: str
    page_count: int | None = None
    isbn: str | None = None
    open_library_description: str | None = None
    member_description: str


class SearchRequest(BaseModel):
    """A search by meaning over stored descriptions."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(max_length=500)


def get_model() -> Model:
    """Return the model the finder agent uses."""
    return gateway_model()


def get_catalog() -> OpenLibraryCatalog:
    """Return the Open Library catalog."""
    return OpenLibraryCatalog()


def get_embedder() -> Embedder:
    """Return the course gateway embedder."""
    return GatewayEmbedder()


def get_connection() -> Iterator[Connection]:
    """Yield one Postgres connection, or 503 when Postgres cannot be opened."""
    try:
        yield from connection()
    except DatabaseUnavailable as error:
        raise HTTPException(status_code=503, detail="Postgres is unavailable.") from error


def get_summarizer() -> Summarize:
    """Return the summary call. Tests replace it so they do not need a second model shape."""
    return write_summary


def get_store(
    opened: Annotated[Connection, Depends(get_connection)],
) -> PostgresLibrary:
    """Return the Postgres store for this request."""
    return PostgresLibrary(opened, get_embedder())


@app.get("/health/postgres")
def health_postgres(
    opened: Annotated[Connection, Depends(get_connection)],
) -> dict[str, bool]:
    """Report whether the finder database answers."""
    if not postgres_answers(opened):
        raise HTTPException(status_code=503, detail="Postgres is unavailable.")
    return {"ok": True}


@app.get("/")
def home() -> HTMLResponse:
    """Return the book finder page."""
    return HTMLResponse(PAGE.read_text(encoding="utf-8"))


@app.post("/inquire")
async def inquire(
    request: FinderRequest,
    model: Annotated[Model, Depends(get_model)],
    catalog: Annotated[OpenLibraryCatalog, Depends(get_catalog)],
    store: Annotated[PostgresLibrary, Depends(get_store)],
    summarize: Annotated[Summarize, Depends(get_summarizer)],
) -> InquireResult:
    """Answer the member, confirm books in Open Library, and store the search."""
    try:
        return await prepare(request, model, catalog, store, summarize)
    except AgentRunError as error:
        raise HTTPException(
            status_code=502, detail="The book finder model is unavailable."
        ) from error


@app.get("/nominations")
def read_nominations(store: Annotated[PostgresLibrary, Depends(get_store)]) -> list[SavedBook]:
    """Return the nominations the member can reopen."""
    return store.nominations()


@app.post("/nominations")
def create_nomination(
    body: SaveRequest, store: Annotated[PostgresLibrary, Depends(get_store)]
) -> dict[str, bool]:
    """Save one nomination, or 400 when the save is rejected and nothing changes."""
    record = CatalogRecord(
        title=body.title,
        author=body.author,
        year=None,
        page_count=body.page_count,
        isbn=body.isbn,
        description=body.open_library_description,
    )
    try:
        save_book(store, body.session_id, record, body.member_description)
    except SaveRejected as error:
        raise HTTPException(status_code=400, detail=error.message) from error
    return {"ok": True}


@app.post("/similar")
def similar(
    body: SearchRequest, store: Annotated[PostgresLibrary, Depends(get_store)]
) -> list[PassageHit]:
    """Return stored descriptions close in meaning to the query."""
    return store.search(body.query)
