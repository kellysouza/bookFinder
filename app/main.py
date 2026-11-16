"""FastAPI routes and the page. No business rules here."""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from psycopg import Connection
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from app.agent import FinderAnswer, FinderRequest, answer, gateway_model
from app.db import DatabaseUnavailable, connection, postgres_answers

app = FastAPI()
PAGE = Path(__file__).parent / "page.html"


def get_model() -> Model:
    """Return the model the finder agent uses."""
    return gateway_model()


def get_connection() -> Iterator[Connection]:
    """Yield one Postgres connection, or 503 when Postgres cannot be opened."""
    try:
        yield from connection()
    except DatabaseUnavailable as error:
        raise HTTPException(status_code=503, detail="Postgres is unavailable.") from error


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
    request: FinderRequest, model: Annotated[Model, Depends(get_model)]
) -> FinderAnswer:
    """Answer the member's latest line, or 502 when the model is unavailable."""
    try:
        return await answer(request, model)
    except AgentRunError as error:
        raise HTTPException(
            status_code=502, detail="The book finder model is unavailable."
        ) from error
