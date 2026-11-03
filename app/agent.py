"""The Pydantic AI agent and its output model."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


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


INSTRUCTIONS = (
    "You help a book club member nominate a book they have in mind, "
    "or a book of a type they like. "
    "Return at most three books, each with a title, author, short summary, "
    "and one-line reason. "
    "Do not give the ending, the twist, the culprit, or a death. "
    "Leave page_count empty when you do not have it. Do not invent a page count."
)

finder_agent = Agent(
    output_type=InquiryResponse,
    instructions=INSTRUCTIONS,
    defer_model_check=True,
)


def gateway_model() -> OpenAIChatModel:
    """Build the course gateway model from the environment."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    gateway = os.getenv("LLM_API_GATEWAY", "").strip().rstrip("/")
    token = os.getenv("LLM_API_TOKEN", "").strip()
    model_name = os.getenv("LLM_MODEL", "gpt-4.1-nano").strip() or "gpt-4.1-nano"
    if not gateway or not token:
        raise ValueError("Set LLM_API_GATEWAY and LLM_API_TOKEN in .env.")
    return OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(base_url=gateway, api_key=token),
    )


def ask_finder(text: str) -> InquiryResponse:
    """Ask the finder agent and return its structured reply."""
    result = finder_agent.run_sync(text, model=gateway_model())
    output = result.output
    if not isinstance(output, InquiryResponse):
        raise TypeError("The finder agent did not return an inquiry response.")
    return output
