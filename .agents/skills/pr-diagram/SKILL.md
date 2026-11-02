---
name: pr-diagram
description: Use when a pull request is ready to open, is being opened, or is already open and its description needs a diagram of the change, or an updated diagram after new commits.
---

# PR diagram

Add exactly one Mermaid diagram of the change to the pull request description, under a `## Diagram` heading.

## Read the change

- Read the Changes section of `AGENTS.md` for what the description must contain.
- Read the diff (`gh pr diff <number>`, or `git diff main...HEAD` before the pull request exists) and the current description (`gh pr view <number> --json body`).

## Choose one diagram

- Pick the type that fits the change: a `sequenceDiagram` for a request or call path, a `flowchart` for a decision or a set of modules.
- Use at most **eight boxes**: sequence participants or flowchart nodes. Each box is a **file or function in the diff**, named as it appears in the code, such as `answer()` in `app/agent.py`. Leave out services, models, and people that are not code in the diff; put them in an arrow label instead.
- Check **every arrow** against the code at the pull request's head: the caller really calls the callee, or the file really imports or posts to the other. Drop any arrow you cannot point to a line for.
- Write every arrow label and note as **plain text on one line**: no `<br/>`, no HTML, and no parentheses, quotes, semicolons, or `#`. A box name may keep a function's `()`.

## Update the description

- Keep every other part of the description exactly as it is, including the Summary, the Test plan, and the checklist states.
- Put the `## Diagram` section after the Summary. If a `## Diagram` section already exists, replace only that section.
- Apply it with `gh pr edit <number> --body-file <file>`, then open the pull request on GitHub and check that the diagram renders.

## Before you report done

- At most eight boxes, each a file or function in the diff.
- Every arrow checked against the code.
- Arrow labels and notes plain text on one line.
- The rest of the description unchanged.
