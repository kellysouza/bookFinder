"""Score the finder on a fixed set of cases. Not collected by pytest.

Run from the repo root:

    uv run python -m evals.run_finder
    uv run python -m evals.run_finder --model gemini-3.5-flash

The judge is gpt-4.1-nano on both runs, so it is not the model being scored.

The first command is the baseline, claude-haiku-5.5. The second changes only
the model. claude-haiku-5.5 accepts only temperature 1, so temperature is not
the factor. Both write a JSON report under evals/results/.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import logfire
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext, LLMJudge

from app.agent import FinderRequest, Turn, answer, gateway_model
from app.rules.books import NEWEST_NOTE

logfire.configure(service_name="bookfinder", send_to_logfire="if-token-present")
logfire.instrument_pydantic_ai()

RUBRIC = (
    "PASS only if the reply does not reveal an ending, a twist, a culprit, or a death, "
    "and it does not say the book was saved. "
    "FAIL if it does any of those. Extra caution alone does not fail it."
)
JUDGE_MODEL = "gpt-4.1-nano"
BASELINE_MODEL = "claude-haiku-5.5"
RESULTS = Path(__file__).parent / "results"

CASES: list[tuple[str, str, str, str]] = [
    (
        "1-blood-music",
        "find",
        "author's name was greg something, the title had bear in it, and it was biology science fiction",
        "blood music",
    ),
    ("2-controlled-society", "suggest", "a book with themes like Brave New World", "1984|fahrenheit 451"),
    ("3-huxley", "suggest", "a sci-fi book by Aldous Huxley", "brave new world"),
    ("4-dead-wake", "find", "a ship sinks, the author is erik larson", "dead wake"),
    ("5-train", "find", "agatha something, murder on a train", "orient express"),
    ("6-space", "suggest", "a book about space travel with mystery and aliens", "(any)"),
    ("7-martian", "find", "the martian", "the martian"),
    ("8-summary-train", "find", "agatha christie, murder on a train", "orient express"),
    ("9-vague", "find", "hi", "(none)"),
    ("10-weather", "find", "what's the weather today", "(none)"),
    ("11-greg-alone", "find", "the author's name was greg something", "(none)"),
    ("12-broad", "suggest", "what should our club read next?", "(none)"),
    ("13-newest", "find", "Brandon Sanderson's newest one", "(note)"),
    ("14-made-up", "find", "the new Becky Chambers book, The Lantern Orchard", "(none)"),
    ("15-typo", "find", "the hunger gmes", "hunger games"),
]


@dataclass
class ExpectedBooks(Evaluator):
    """A code check: the expected title is on the cards, or the cards are empty."""

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        output = str(ctx.output).lower()
        expected = str(ctx.expected_output)
        if expected == "(none)":
            return "books: (none)" in output
        if expected == "(note)":
            return NEWEST_NOTE.lower() in output
        if expected == "(any)":
            return "books: (none)" not in output
        return any(option.strip().lower() in output for option in expected.split("|"))


def dataset() -> Dataset[str, str, dict[str, str]]:
    """Return the versioned cases. The proposal's examples are the first eight."""
    cases = [
        Case(
            name=name,
            inputs=f"{path}\n{line}",
            expected_output=expected,
            metadata={"path": path, "set": "finder-v1"},
        )
        for name, path, line, expected in CASES
    ]
    return Dataset(
        name="finder-v1",
        cases=cases,
        evaluators=[
            ExpectedBooks(),
            LLMJudge(rubric=RUBRIC, include_input=True, model=gateway_model(JUDGE_MODEL)),
        ],
    )


def _request(case_input: str) -> FinderRequest:
    path, line = case_input.split("\n", 1)
    if path not in ("find", "suggest"):
        raise ValueError("A case input starts with find or suggest.")
    return FinderRequest(path=path, turns=[Turn(speaker="member", text=line)])


async def _ask(case_input: str, model_name: str) -> str:
    result = await answer(_request(case_input), gateway_model(model_name))
    if not result.books:
        titles = "(none)"
    else:
        titles = "; ".join(book.title for book in result.books)
    return f"{result.reply}\nBooks: {titles}"


def _score_value(result: object) -> object:
    return getattr(result, "value", result)


def main() -> None:
    """Run the set once at the given temperature and write the case results."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=BASELINE_MODEL)
    args = parser.parse_args()
    model_name = str(args.model)

    async def task(case_input: str) -> str:
        return await _ask(case_input, model_name)

    report = dataset().evaluate_sync(task, name=model_name, max_concurrency=1)
    report.print(include_output=True, include_reasons=True)
    saved = []
    for case in report.cases:
        scores = {name: _score_value(result) for name, result in case.assertions.items()}
        scores.update({name: _score_value(result) for name, result in case.scores.items()})
        saved.append({"name": case.name, "output": case.output, "scores": scores})
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{model_name}.json"
    path.write_text(json.dumps({"model": model_name, "cases": saved}, indent=2))
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
