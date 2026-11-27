from collections.abc import Iterator

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models import override_allow_model_requests
from pydantic_ai.models.test import TestModel

from app.summary import write_summary

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def no_real_model() -> Iterator[None]:
    with override_allow_model_requests(False):
        yield


USABLE = "A scientist injects himself with intelligent cells, and they remake him completely."


async def test_a_usable_description_is_marked_open_library():
    summary, source = await write_summary(
        "Blood Music",
        "Greg Bear",
        "biology",
        USABLE,
        TestModel(custom_output_args={"summary": "Cells remake a man."}),
    )
    assert summary == "Cells remake a man."
    assert source == "open_library"


async def test_an_empty_summary_is_left_for_the_member():
    summary, source = await write_summary(
        "Unknown",
        "Nobody",
        "a book",
        None,
        TestModel(custom_output_args={"summary": "  "}),
    )
    assert summary == ""
    assert source == "member"


async def test_a_summary_that_states_a_death_is_rejected():
    with pytest.raises(UnexpectedModelBehavior):
        await write_summary(
            "The Martian",
            "Andy Weir",
            "the martian",
            USABLE,
            TestModel(custom_output_args={"summary": "He is presumed dead on Mars."}),
        )


async def test_an_unusable_description_is_marked_as_the_model():
    _summary, source = await write_summary(
        "Blood Music",
        "Greg Bear",
        "biology",
        "trop court",
        TestModel(custom_output_args={"summary": "What the model knew."}),
    )
    assert source == "model"
