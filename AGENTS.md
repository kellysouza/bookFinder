# Instructions for coding agents

A book finder that helps a book club member nominate a book they have in mind, or a book of a type they like.
The full proposal is in docs/proposal.md.

## Layout

- `app/main.py`: FastAPI routes and the page. No business rules here.
- `app/agent.py`: the Pydantic AI agent and its output model.
- `app/rules.py`: business rules in plain Python. No FastAPI, no LLM client.

## Commands

```bash
uv run fastapi dev app/main.py   # run the app
uv run ruff check                # lint, including the complexity limit
uv run mypy                      # check types
uv run pytest                    # run the tests
```

## Rules

- Tests never call a real model. Use `TestModel` with
  `override_allow_model_requests(False)`.
- Read `LLM_API_TOKEN` and `LLM_API_GATEWAY` from the environment. Never
  write a key into a file other than `.env`.
- Run `uv run ruff check`, `uv run mypy`, and `uv run pytest` after every
  change, and include their output in your report. Do not report a change as
  done while any of them fails.
- Never weaken a check to make it pass: do not raise `max-complexity`, add a
  `# noqa` or `# type: ignore` comment, or skip a test.
