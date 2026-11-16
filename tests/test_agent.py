from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models import override_allow_model_requests
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel

from app.agent import (
    MAX_MODEL_REPLY_CHARS,
    BookOption,
    FinderRequest,
    answer,
    gateway_model,
    prompt_for,
)
from app.rules.books import NEWEST_NOTE
from app.rules.conversation import MAX_FINDER_REPLY_CHARS

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def no_real_model() -> Iterator[None]:
    with override_allow_model_requests(False):
        yield


def member(text: str) -> dict[str, str]:
    return {"speaker": "member", "text": text}


def finder(text: str) -> dict[str, str]:
    return {"speaker": "finder", "text": text}


def book(title: str) -> dict[str, object]:
    return {"title": title, "author": "Author", "year": None, "reason": "r"}


def request_with(*turns: dict[str, str]) -> FinderRequest:
    return FinderRequest(path="find", turns=list(turns))


def test_prompt_names_the_path_the_conversation_in_order_and_the_current_books():
    request = FinderRequest(
        path="find",
        turns=[member("it's by Becky Chambers"), finder("Here are her best-known books."), member("it was about space travel")],
        books=[BookOption(title="A Psalm for the Wild-Built", author="Becky Chambers", year=2021, reason="r")],
    )
    prompt = prompt_for(request)
    assert "Path: find" in prompt
    assert prompt.index("it's by Becky Chambers") < prompt.index("Here are her best-known books.") < prompt.index("it was about space travel")
    assert "A Psalm for the Wild-Built" in prompt and "Becky Chambers" in prompt and "2021" in prompt


def test_prompt_shows_none_without_books_and_leaves_out_an_unknown_year():
    assert "Books shown now:\n(none)" in prompt_for(request_with(member("hi")))
    request = FinderRequest(path="suggest", turns=[member("hi")], books=[book("Dead Wake")])
    assert "- Dead Wake, Author\n" in prompt_for(request)


def test_gateway_model_reads_the_environment_when_called(monkeypatch):
    monkeypatch.setenv("LLM_API_GATEWAY", "http://gateway.test/v1")
    monkeypatch.setenv("LLM_API_TOKEN", "test-token")
    model = gateway_model()
    assert isinstance(model, OpenAIChatModel)
    assert model.model_name == "claude-haiku-5.5"
    assert model.base_url.startswith("http://gateway.test/v1")


async def test_answer_drops_repeated_and_blank_books():
    output = {"reply": "Here you go.", "books": [book("The Martian"), book("martian"), book("  ")]}
    result = await answer(request_with(member("the martian")), TestModel(custom_output_args=output))
    assert [b.title for b in result.books] == ["The Martian"]


async def test_answer_adds_the_newest_note_when_the_latest_line_asks_and_books_are_named():
    output = {"reply": "That would be Wind and Truth.", "books": [book("Wind and Truth")]}
    result = await answer(request_with(member("Brandon Sanderson's newest one")), TestModel(custom_output_args=output))
    assert result.reply == "That would be Wind and Truth. " + NEWEST_NOTE


async def test_answer_adds_no_note_without_books():
    output = {"reply": "Which author?", "books": []}
    result = await answer(request_with(member("the newest one")), TestModel(custom_output_args=output))
    assert NEWEST_NOTE not in result.reply


async def test_answer_adds_no_note_when_only_an_earlier_line_asked():
    turns = [member("Brandon Sanderson's newest one"), finder("That would be Wind and Truth."), member("yes, that one")]
    output = {"reply": "Great choice!", "books": [book("Wind and Truth")]}
    result = await answer(FinderRequest(path="find", turns=turns), TestModel(custom_output_args=output))
    assert NEWEST_NOTE not in result.reply


async def test_answer_keeps_a_longest_reply_with_the_newest_note_within_the_limit():
    output = {"reply": "x" * MAX_MODEL_REPLY_CHARS, "books": [book("Wind and Truth")]}
    result = await answer(request_with(member("the newest one")), TestModel(custom_output_args=output))
    assert result.reply.endswith(NEWEST_NOTE)
    assert len(result.reply) <= MAX_FINDER_REPLY_CHARS


async def test_answer_fails_when_the_model_keeps_replying_too_long():
    output = {"reply": "x" * (MAX_MODEL_REPLY_CHARS + 1), "books": []}
    with pytest.raises(UnexpectedModelBehavior):
        await answer(request_with(member("hi")), TestModel(custom_output_args=output))


async def test_answer_fails_when_the_model_keeps_replying_blank():
    output = {"reply": "   ", "books": []}
    with pytest.raises(UnexpectedModelBehavior):
        await answer(request_with(member("hi")), TestModel(custom_output_args=output))


@pytest.mark.parametrize("turns", [
    [],                                               # no member line
    [member("hi"), finder("Which book?")],            # last turn is the finder's
    [member("   ")],                                  # blank line
    [member("x" * 501)],                              # member line too long
    [member("hi"), finder("y" * 2001), member("ok")],  # finder reply too long
    [member(f"line {n}") for n in range(31)],         # 31 member lines
])
def test_request_is_rejected(turns):
    with pytest.raises(ValidationError):
        FinderRequest(path="find", turns=turns)


def test_request_accepts_30_member_lines_of_500_characters():
    FinderRequest(path="suggest", turns=[member("x" * 500) for _ in range(30)])


def test_request_rejects_four_current_books_and_an_unknown_path():
    with pytest.raises(ValidationError):
        FinderRequest(path="find", turns=[member("hi")], books=[book("a"), book("b"), book("c"), book("d")])
    with pytest.raises(ValidationError):
        FinderRequest(path="browse", turns=[member("hi")])
