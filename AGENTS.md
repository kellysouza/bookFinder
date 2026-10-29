# Instructions for coding agents

A book finder that helps a book club member find and nominate a book they have in mind, or find a book of a type they like.  
The full proposal is in docs/proposal.md.

## Spec

- `docs/proposal.md` is the spec. When a decision is made in a conversation (a feature added or left out, a limit or value chosen, an open question answered), edit the section the decision belongs to so that it states the decision, in the same change, and name that section in the pull request Summary. Change only what the decision affects. Do not add a dated log, approval history, or status notes; git and `docs/superpowers/` keep the history.
- A design under `docs/superpowers/specs/` covers one change; `docs/proposal.md` covers the whole project. If the two disagree, ask before building.

## Layout

- `app/main.py`: FastAPI routes and the page. No business rules here.
- `app/agent.py`: the Pydantic AI agent and its output model.
- `app/rules.py`: business rules in plain Python. No FastAPI, no LLM client.
- This is the starting layout. When a module takes on a second responsibility, split it by responsibility (for example, `app/rules.py` into `app/rules/quota.py` and `app/rules/scope.py`) and update this section in the same change.

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

## Changes

- Never commit to `main`. Make each change on its own branch and open a pull
  request with `gh pr create`. The description has a `## Summary` section
  (what changed and why, citing docs/proposal.md) and a `## Test plan`
  checklist (checked items were run; unchecked items are left for the reviewer).
- After pushing, run `gh pr checks --watch` and report the result.
- Never merge a pull request. The person merges after reviewing it.
