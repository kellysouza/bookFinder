"""The finder agent, the request it answers, and the answer it gives."""

import os
from typing import Literal, Self

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.rules.books import NEWEST_NOTE, asks_for_newest, drop_unusable_books
from app.rules.conversation import (
    MAX_BOOKS,
    MAX_FINDER_REPLY_CHARS,
    MAX_MEMBER_LINE_CHARS,
    MAX_MEMBER_LINES,
)

FinderPath = Literal["find", "suggest"]


class Turn(BaseModel):
    """One line of the conversation, from the member or the finder."""

    model_config = ConfigDict(extra="forbid")

    speaker: Literal["member", "finder"]
    text: str

    @model_validator(mode="after")
    def check_text(self) -> Self:
        """Reject a blank line, or one longer than the speaker's limit."""
        if not self.text.strip():
            raise ValueError("a line cannot be blank")
        limit = MAX_MEMBER_LINE_CHARS if self.speaker == "member" else MAX_FINDER_REPLY_CHARS
        if len(self.text) > limit:
            raise ValueError(f"a {self.speaker} line is at most {limit} characters")
        return self


class BookOption(BaseModel):
    """One book the finder can show."""

    model_config = ConfigDict(extra="forbid")

    title: str
    author: str
    year: int | None
    reason: str


class FinderRequest(BaseModel):
    """The chosen path, the conversation so far, and the books shown now."""

    model_config = ConfigDict(extra="forbid")

    path: FinderPath
    turns: list[Turn]
    books: list[BookOption] = Field(default=[], max_length=MAX_BOOKS)

    @model_validator(mode="after")
    def check_turns(self) -> Self:
        """Require the last turn to be the member's, within the line limit."""
        if not self.turns or self.turns[-1].speaker != "member":
            raise ValueError("the last turn must be the member's")
        member_lines = sum(1 for turn in self.turns if turn.speaker == "member")
        if member_lines > MAX_MEMBER_LINES:
            raise ValueError(f"a conversation has at most {MAX_MEMBER_LINES} member lines")
        return self


class FinderAnswer(BaseModel):
    """The reply and the current list of likely books."""

    model_config = ConfigDict(extra="forbid")

    reply: str = Field(max_length=MAX_FINDER_REPLY_CHARS)
    books: list[BookOption] = Field(max_length=MAX_BOOKS)


INSTRUCTIONS = (
    "The member is choosing a book to nominate for their book club. "
    "Path find: they have one book in mind and are describing it from memory. "
    "Path suggest: they want ideas. "
    "Do not hallucinate or invent books. "
    "Name only real, published books by their real authors, "
    "and leave out any you are not sure of. "
    "On every answer, return the current best list: keep shown books that still fit, "
    "drop ones the new clue rules out, and add better ones. "
    "One vague clue, such as only a first name, gets a question and no books. "
    "A full author name is enough for their best-known books, "
    "and several clues that together point to one book, such as a first name, "
    "a word from the title, and the genre, are enough to name it. "
    "For find, name one book when one fits, "
    "or up to three when several are equally likely. "
    "For suggest, name up to three. "
    "A request too broad to choose from gets one question about what they like. "
    "Never mention a book that is not on a card, never think out loud, "
    "and never reveal endings, twists, culprits, or deaths. "
    "If you don't recognize a book they describe, name none and say: "
    "\"I don't recognize that one. It may be newer than what I know. "
    'Do you remember the author, or anything else about it?" '
    'For an author\'s "newest" or "latest", name the newest you know of. '
    "When one book fits, ask whether they would like to nominate it. "
    'When they say yes ("yes, that one"), say that nominating from the finder '
    "is coming soon and that for now they can add the book, by name, "
    "with the club app's Add a Book form. "
    "Do not ask anything else, and do not say it was saved."
)

MAX_MODEL_REPLY_CHARS = MAX_FINDER_REPLY_CHARS - len(NEWEST_NOTE) - 1

finder_agent: Agent[None, FinderAnswer] = Agent(
    output_type=FinderAnswer,
    instructions=INSTRUCTIONS,
)


@finder_agent.output_validator
def check_reply(output: FinderAnswer) -> FinderAnswer:
    """Ask again when the reply is blank or leaves no room for the newest note."""
    if not output.reply.strip():
        raise ModelRetry("Write a reply to the member.")
    if len(output.reply) > MAX_MODEL_REPLY_CHARS:
        raise ModelRetry(f"Keep the reply to at most {MAX_MODEL_REPLY_CHARS} characters.")
    return output


def gateway_model() -> OpenAIChatModel:
    """Return the course gateway model, reading its settings from the environment."""
    load_dotenv()
    provider = OpenAIProvider(
        base_url=os.environ["LLM_API_GATEWAY"],
        api_key=os.environ["LLM_API_TOKEN"],
    )
    return OpenAIChatModel("claude-haiku-5.5", provider=provider)


def _book_line(book: BookOption) -> str:
    """Return one book as a prompt line: title, author, and year when known."""
    parts = [book.title, book.author]
    if book.year is not None:
        parts.append(str(book.year))
    return "- " + ", ".join(parts)


def prompt_for(request: FinderRequest) -> str:
    """Return the path, the books shown now, and the conversation, as plain text."""
    lines = [f"Path: {request.path}", "Books shown now:"]
    lines += [_book_line(book) for book in request.books] or ["(none)"]
    lines.append("Conversation, oldest first:")
    lines += [f"{turn.speaker.capitalize()}: {turn.text}" for turn in request.turns]
    return "\n".join(lines)


async def answer(request: FinderRequest, model: Model) -> FinderAnswer:
    """Ask the finder agent, then clean its books and add the newest note when asked."""
    result = await finder_agent.run(prompt_for(request), model=model)
    books = drop_unusable_books(result.output.books)
    reply = result.output.reply
    last_member_line = request.turns[-1].text
    if books and asks_for_newest(last_member_line):
        reply = f"{reply} {NEWEST_NOTE}"
    return FinderAnswer(reply=reply, books=books)
