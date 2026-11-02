"""Run the finder against the real model on hand-written cases and count the expectations met.

Run from the repo root: uv run python scripts/evaluate_finder.py [case-id ...]
This is a measurement, not a gate, so it exits 0 however many expectations fail.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.models import Model

from app.agent import (
    BookOption,
    FinderAnswer,
    FinderRequest,
    Turn,
    answer,
    gateway_model,
)
from app.rules.books import NEWEST_NOTE

CASES_FILE = Path(__file__).with_name("finder_cases.json")

Case = dict[str, Any]
Check = tuple[bool, str]


def load_cases(ids: list[str]) -> list[Case]:
    """Return the cases whose ids are given, or every case when none are."""
    cases: list[Case] = json.loads(CASES_FILE.read_text())
    if not ids:
        return cases
    return [case for case in cases if case["id"] in ids]


def _member(text: str) -> Turn:
    """Return one member turn."""
    return Turn(speaker="member", text=text)


async def _run_one_at_a_time(
    case: Case, turns: list[Turn], books: list[BookOption], model: Model
) -> FinderAnswer:
    """Send each line as its own request, carrying the replies and cards forward."""
    latest: FinderAnswer | None = None
    for line in case["lines"]:
        turns.append(_member(line))
        latest = await answer(FinderRequest(path=case["path"], turns=turns, books=books), model)
        turns.append(Turn(speaker="finder", text=latest.reply))
        books = latest.books
    if latest is None:
        raise ValueError("a case needs at least one line")
    return latest


async def run_case(case: Case, model: Model) -> FinderAnswer:
    """Build the case's request, or requests, and return the final answer."""
    turns = [Turn.model_validate(turn) for turn in case.get("prior_turns", [])]
    books = [BookOption.model_validate(book) for book in case.get("prior_books", [])]
    if case.get("one_at_a_time"):
        return await _run_one_at_a_time(case, turns, books, model)
    turns += [_member(line) for line in case["lines"]]
    return await answer(FinderRequest(path=case["path"], turns=turns, books=books), model)


def check(case: Case, final: FinderAnswer) -> list[Check]:
    """Return whether each expectation in the case held, with a description of it."""
    checks: list[Check] = []
    titles = [book.title.lower() for book in final.books]
    if "expect_title" in case:
        wanted = case["expect_title"]
        checks.append((any(wanted in title for title in titles), f'"{wanted}" on the cards'))
    if case.get("expect_no_books"):
        checks.append((not final.books, "no cards"))
    if case.get("expect_note"):
        checks.append((NEWEST_NOTE in final.reply, "the newest note in the reply"))
    if "expect_reply_contains" in case:
        wanted = case["expect_reply_contains"]
        checks.append((wanted in final.reply, f'"{wanted}" in the reply'))
    return checks


def expectation_count(case: Case) -> int:
    """Return how many expectations the case has."""
    keys = ("expect_title", "expect_no_books", "expect_note", "expect_reply_contains")
    return sum(1 for key in keys if case.get(key))


def print_answer(final: FinderAnswer) -> None:
    """Print the reply and the cards as title / author / year."""
    print(f"  reply: {final.reply}")
    for book in final.books:
        year = book.year if book.year is not None else "unknown"
        print(f"  card: {book.title} / {book.author} / {year}")
    if not final.books:
        print("  card: (none)")


async def evaluate(case: Case, model: Model) -> int:
    """Run and print one case, and return how many of its expectations were met."""
    print(f"== {case['id']} ({case['path']}) ==")
    for line in case["lines"]:
        print(f"  member: {line}")
    try:
        final = await run_case(case, model)
    except (AgentRunError, ValueError) as error:
        print(f"  ERROR {type(error).__name__}: {error}")
        return 0
    print_answer(final)
    met = 0
    for passed, description in check(case, final):
        print(f"  {'PASS' if passed else 'FAIL'}: expected {description}")
        met += passed
    return met


async def evaluate_all(cases: list[Case]) -> None:
    """Run every case against one gateway model and print the summary line."""
    model = gateway_model()
    met = 0
    for case in cases:
        met += await evaluate(case, model)
    total = sum(expectation_count(case) for case in cases)
    print(f"{met} of {total} expectations met")


def main() -> None:
    """Run the cases named on the command line, or all of them."""
    asyncio.run(evaluate_all(load_cases(sys.argv[1:])))


if __name__ == "__main__":
    main()
