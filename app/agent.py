"""The finder agent, the request it answers, and the answer it gives."""

import os
from typing import Literal, Self

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_ai import Agent
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

    reply: str
    books: list[BookOption] = Field(max_length=MAX_BOOKS)


INSTRUCTIONS = (
    "The member is choosing a book to nominate for the club. "
    "Path find means they have one particular book in mind and are describing it from memory. "
    "Path suggest means they want help coming up with one. "
    "Name only real, published books with the author's real name. "
    "Leave out any book you are not confident exists. "
    "Return the current best list on every answer, starting from the books already shown: "
    "keep the ones that still fit, drop the ones the new clue rules out, and add better ones. "
    "Name books once the clues point to them with reasonable confidence. "
    "A full author name is enough for that author's best-known books; "
    "a single vague clue, such as an author's first name, gets a question and no books. "
    "For find, name one book when one clearly fits, "
    "and up to three only when several are about equally likely. "
    "For suggest, name up to three. "
    'A request too broad to choose from, such as "what should our club read next?", '
    "gets one question about what they like instead of books. "
    "The reply names no book that is not on a card, "
    'and does not think out loud ("wait", "no, let me be precise"). '
    "Do not reveal endings, twists, culprits, or deaths. "
    "When the member names or describes a book you do not recognize, say so and name no book, "
    "along the lines of \"I don't recognize that one. It may be newer than what I know. "
    'Do you remember the author, or anything else about it?" '
    "Do not invent a close-sounding title. "
    'For "newest" or "latest" by an author, name the newest you know of. '
    'When the member says yes to a book ("yes, that one"), acknowledge it and say that '
    "nominating straight from the finder is coming soon, and that for now they can add it "
    "with the club app's Add a Book form, naming the book. "
    "Do not ask another narrowing question, and do not say it was saved. "
    "When one book clearly fits, end the reply by asking whether the member would like to nominate it."
)

finder_agent: Agent[None, FinderAnswer] = Agent(
    output_type=FinderAnswer,
    instructions=INSTRUCTIONS,
)


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
