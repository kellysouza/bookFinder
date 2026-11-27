"""The summary call, once per book Open Library confirmed."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models import Model

from app.rules.catalog import description_is_usable

SummarySource = Literal["open_library", "model", "member"]


class JacketSummary(BaseModel):
    """The jacket summary, in the model's own words."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=500)


SUMMARY_INSTRUCTIONS = (
    "Write a jacket summary in your own words. "
    "Do not copy the Open Library description. "
    "Do not reveal the ending, the twist, the culprit, or a death. "
    "When the note says the description is usable, base the summary on it. "
    "When the note says it is not usable, use what you already know. "
    "If you do not know the book, return an empty summary."
)

summary_agent: Agent[None, JacketSummary] = Agent(
    output_type=JacketSummary,
    instructions=SUMMARY_INSTRUCTIONS,
)

_DEATH_WORDS = ("dead", "death", "dies", "died", "killed")


@summary_agent.output_validator
def reject_a_death(output: JacketSummary) -> JacketSummary:
    """Ask again when the summary states a death. A murder in the setup may stay."""
    words = set(re.findall(r"[a-z]+", output.summary.lower()))
    if words & set(_DEATH_WORDS):
        raise ModelRetry("Do not mention a death. Leave that out and write the summary again.")
    return output


async def write_summary(
    title: str,
    author: str,
    member_text: str,
    description: str | None,
    model: Model,
) -> tuple[str, SummarySource]:
    """Return the summary and where it came from.

    A usable Open Library description is rewritten and marked open_library.
    Otherwise the model may use what it knows, marked model.
    An empty summary is left for the member to write.
    """
    source: SummarySource = "open_library" if description_is_usable(description) else "model"
    note = "usable" if source == "open_library" else "not usable"
    prompt = (
        f"Title: {title}\nAuthor: {author}\nMember: {member_text}\n"
        f"Open Library description ({note}): {description or '(none)'}"
    )
    result = await summary_agent.run(prompt, model=model)
    text = result.output.summary.strip()
    if not text:
        return "", "member"
    return text, source
