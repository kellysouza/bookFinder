# Choose, then chat with the model: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder `POST /inquire` with a chat. The member chooses "I have one in mind" or "I need help coming up with one", sends clues, and one model replies and keeps a pinned list of up to three likely books.

**Architecture:** The page holds the conversation and the current cards and sends all of them on every Send. `app/agent.py` turns that request into one prompt and runs a Pydantic AI agent whose output is a reply plus zero to three books. Plain-Python rules in `app/rules/` then clean the books and add the newest-book note. `app/main.py` exposes one route and gets the model through a FastAPI dependency, so tests swap in `TestModel`.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, Pydantic AI 2.59 (`OpenAIChatModel` through the course gateway), plain HTML, CSS, and JavaScript, pytest, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-11-01-choose-then-chat-design.md`, with the mockup beside it: `docs/superpowers/specs/2026-11-01-choose-then-chat-mockup.html`.

## Global Constraints

- Model name: `claude-haiku-5.5`. Gateway values come from the environment variables `LLM_API_GATEWAY` (base URL) and `LLM_API_TOKEN` (key). They are read when a request is made, never at import, because CI has neither.
- Tests never call a real model: `TestModel` with `override_allow_model_requests(False)`.
- No new dependencies.
- `uv run ruff check`, `uv run mypy`, and `uv run pytest` pass after every task. No `# noqa` or `# type: ignore` is added, and `max-complexity` is not raised.
- `app/main.py` has routes and the page only. `app/agent.py` has the agent and its models. `app/rules/` is plain Python and imports neither FastAPI nor `pydantic_ai`.
- At most 3 books. Member lines are at most 30 per conversation and 500 characters each. Finder replies sent back are at most 2,000 characters.
- Fixed copy, verbatim:
  - Greeting: `Hi, I'm here to help you nominate a book. Do you have one in mind, or would you like help coming up with one?`
  - Buttons: `I have one in mind` (path `find`) and `I need help coming up with one` (path `suggest`)
  - Follow-up for find: `Great, I'd love to help you find it. Tell me any details you can recall.`
  - Follow-up for suggest: `Great, I'll make suggestions. Tell me what kinds of books you like.`
  - Newest note: `This is the newest I know of. My book knowledge stops at a cutoff, so there may be a newer one.`
  - Error line: `Sorry, I couldn't reach the book finder just now. Please try again.`
  - Limit line: `This chat is getting long. Tap New search to start fresh.`
  - Area heading: `Likely books`. Header button: `+` with `New search`.

## Review Focus

1. **A whitespace-only title or author from the model** (`"  "`). The card is dropped, not shown blank. Test in Task 1.
2. **A duplicate that differs only by case, extra spaces, or a leading "The" or "A"** (`The Martian` / `martian`). Only the first is kept. Test in Task 1.
3. **A request whose last turn is a finder reply, or that has no member line.** It is rejected with 422 before any model call. Test in Task 2.
4. **The model's output fails validation every time.** The route answers 502, not 500, so the page shows the error line and keeps the chat. Test in Task 3.
5. **"newest" asked in an earlier line, then "yes, that one" with the cards still up.** The note is not added again, because it follows the latest member line only. Test in Task 2.

---

### Task 1: Split `app/rules.py` and add the book and conversation rules

**Files:**
- Delete: `app/rules.py`
- Create: `app/rules/__init__.py` (a docstring only), `app/rules/nomination.py`, `app/rules/books.py`, `app/rules/conversation.py`
- Modify: `tests/test_rules.py` (import from `app.rules.nomination`), `AGENTS.md` (Layout section). Nothing else imports `app.rules` yet.
- Create: `tests/test_book_rules.py`, `tests/test_conversation_rules.py`
- Also commit the design, mockup, and this plan: `docs/superpowers/specs/2026-11-01-choose-then-chat-design.md`, `docs/superpowers/specs/2026-11-01-choose-then-chat-mockup.html`, `docs/superpowers/plans/2026-11-01-choose-then-chat.md`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `app.rules.nomination.save_is_rejected(meeting_is_accepting_nominations: bool) -> bool` (moved unchanged)
  - `app.rules.books.NamedBook`: a `typing.Protocol` with attributes `title: str` and `author: str`
  - `app.rules.books.drop_unusable_books[B: NamedBook](books: list[B]) -> list[B]`
  - `app.rules.books.asks_for_newest(member_line: str) -> bool`
  - `app.rules.books.NEWEST_NOTE: str` (the fixed copy above)
  - `app.rules.conversation.MAX_MEMBER_LINES = 30`, `MAX_MEMBER_LINE_CHARS = 500`, `MAX_FINDER_REPLY_CHARS = 2000`, `MAX_BOOKS = 3`

- [ ] **Step 1: Commit the design, mockup, and plan on the feature branch**

```bash
git add docs/superpowers/specs/2026-11-01-choose-then-chat-design.md docs/superpowers/specs/2026-11-01-choose-then-chat-mockup.html docs/superpowers/plans/2026-11-01-choose-then-chat.md
git commit -m "Add the choose-then-chat design, mockup, and plan."
```

- [ ] **Step 2: Write the failing tests**

`tests/test_rules.py` changes only its import to `from app.rules.nomination import save_is_rejected`.

`tests/test_book_rules.py` uses a small dataclass `Book(title: str, author: str)` defined in the test file:

```python
def test_drops_a_book_with_a_blank_title_or_author():
    books = [Book("  ", "Greg Bear"), Book("Blood Music", ""), Book("Dead Wake", "Erik Larson")]
    assert drop_unusable_books(books) == [Book("Dead Wake", "Erik Larson")]

def test_drops_a_repeat_that_differs_by_case_spacing_or_leading_article():
    books = [Book("The Martian", "Andy Weir"), Book("martian", "andy  weir"), Book("A Martian", "Andy Weir")]
    assert drop_unusable_books(books) == [Book("The Martian", "Andy Weir")]

def test_keeps_the_same_title_by_a_different_author():
    books = [Book("Solaris", "Stanisław Lem"), Book("Solaris", "Someone Else")]
    assert len(drop_unusable_books(books)) == 2

def test_keeps_at_most_three_books_in_order():
    books = [Book(f"Book {n}", "Author") for n in range(5)]
    assert [b.title for b in drop_unusable_books(books)] == ["Book 0", "Book 1", "Book 2"]

@pytest.mark.parametrize("line", ["Brandon Sanderson's newest one", "what's her LATEST book?", "the most recent Expanse book"])
def test_asks_for_newest(line):
    assert asks_for_newest(line)

@pytest.mark.parametrize("line", ["the new Becky Chambers book", "something newer than Dune", "yes, that one"])
def test_does_not_ask_for_newest(line):
    assert not asks_for_newest(line)
```

`tests/test_conversation_rules.py` asserts the four constants equal 30, 500, 2000, and 3.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_rules.py tests/test_book_rules.py tests/test_conversation_rules.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.rules.nomination'` (and the same for `books` and `conversation`).

- [ ] **Step 4: Implement the package**

- Move `save_is_rejected` to `app/rules/nomination.py` unchanged, then delete `app/rules.py`.
- `drop_unusable_books`:
  - Strip each title and author. Drop the book if either is empty.
  - Compare books by a key: lowercase, whitespace runs collapsed to one space, and one leading `the ` or `a ` removed from the title.
  - Keep the first book for each key, keep the input order, and stop at `MAX_BOOKS`.
- `asks_for_newest`: a case-insensitive regex for the whole words `newest`, `latest`, or `most recent`.
- Constants as listed in Interfaces.

- [ ] **Step 5: Update the Layout section of `AGENTS.md`**

Replace the `app/rules.py` line with:

```markdown
- `app/rules/`: business rules in plain Python. No FastAPI, no LLM client.
  - `app/rules/nomination.py`: whether a save is accepted.
  - `app/rules/books.py`: cleaning the model's book list, and the newest-book note.
  - `app/rules/conversation.py`: the limits on a conversation.
```

Keep the rest of the section unchanged, including the "This is the starting layout" line.

- [ ] **Step 6: Run all checks**

Run: `uv run ruff check && uv run mypy && uv run pytest`
Expected: all pass, with the new tests in the count.

- [ ] **Step 7: Commit**

```bash
git add app/rules app/rules.py tests/test_rules.py tests/test_book_rules.py tests/test_conversation_rules.py AGENTS.md
git commit -m "Split the rules by responsibility and add the book and conversation rules."
```

---

### Task 2: The finder agent, its request and answer models, and `answer`

**Files:**
- Modify: `app/agent.py` (replace its contents)
- Modify: `app/main.py`. It imports `InquiryResponse`, `Nomination`, and the old `BookOption`, so remove `PLACEHOLDER_RESPONSE`, `InquiryRequest`, the placeholder `inquire` route, and those imports. Task 3 adds the new route.
- Modify: `tests/test_skeleton.py` (delete the `/inquire` test, keep the page test)
- Create: `tests/test_agent.py`

**Interfaces:**
- Consumes (Task 1): `drop_unusable_books`, `asks_for_newest`, `NEWEST_NOTE`, and the four limits.
- Produces, all in `app.agent`:
  - `FinderPath = Literal["find", "suggest"]`
  - `class Turn(BaseModel)`: `speaker: Literal["member", "finder"]`, `text: str`. The text is not blank after stripping. It is at most `MAX_MEMBER_LINE_CHARS` for a member and `MAX_FINDER_REPLY_CHARS` for the finder.
  - `class BookOption(BaseModel)`: `title: str`, `author: str`, `year: int | None`, `reason: str`
  - `class FinderRequest(BaseModel)`: `path: FinderPath`, `turns: list[Turn]`, `books: list[BookOption] = []` (at most `MAX_BOOKS`). It is valid only when the last turn is a member's and there are at most `MAX_MEMBER_LINES` member turns.
  - `class FinderAnswer(BaseModel)`: `reply: str`, `books: list[BookOption]` (`Field(max_length=MAX_BOOKS)`)
  - `INSTRUCTIONS: str`
  - `finder_agent: Agent[None, FinderAnswer]`, created with `output_type=FinderAnswer` and `instructions=INSTRUCTIONS` and **no model**
  - `gateway_model() -> OpenAIChatModel`
  - `prompt_for(request: FinderRequest) -> str`
  - `async def answer(request: FinderRequest, model: Model) -> FinderAnswer`
- All models use `ConfigDict(extra="forbid")`. `Nomination`, `InquiryResponse`, and `BookOption.summary` are removed.

- [ ] **Step 1: Write the failing tests**

In `tests/test_agent.py`, every test that runs the agent uses `with override_allow_model_requests(False):` and passes `TestModel(custom_output_args={...})` to `answer`. Helper: `member(text)` and `finder(text)` build `Turn`s.

```python
def test_prompt_names_the_path_the_conversation_in_order_and_the_current_books():
    request = FinderRequest(
        path="find",
        turns=[member("it's by Becky Chambers"), finder("Here are her best-known books."), member("it was about space travel")],
        books=[BookOption(title="A Psalm for the Wild-Built", author="Becky Chambers", year=2021, reason="r")],
    )
    prompt = prompt_for(request)
    assert "find" in prompt
    assert prompt.index("it's by Becky Chambers") < prompt.index("Here are her best-known books.") < prompt.index("it was about space travel")
    assert "A Psalm for the Wild-Built" in prompt and "Becky Chambers" in prompt and "2021" in prompt

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
```

`book(title)` returns a `BookOption` (or its dict) with author `"Author"`, year `None`, and reason `"r"`. `request_with(*turns)` builds a find request. Async tests run through `anyio`, which comes with FastAPI's Starlette: mark the module with `pytestmark = pytest.mark.anyio`, and add a module fixture `anyio_backend` that returns `"asyncio"`.

Validation tests (`pydantic.ValidationError`):

```python
@pytest.mark.parametrize("turns", [
    [],                                              # no member line
    [member("hi"), finder("Which book?")],           # last turn is the finder's
    [member("   ")],                                 # blank line
    [member("x" * 501)],                             # member line too long
    [member("hi"), finder("y" * 2001), member("ok")], # finder reply too long
    [member(f"line {n}") for n in range(31)],        # 31 member lines
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_agent.py -v`
Expected: FAIL with `ImportError: cannot import name 'FinderRequest' from 'app.agent'`.

- [ ] **Step 3: Implement `app/agent.py`**

- **`prompt_for`**: plain text in this order:
  - `Path: find` or `Path: suggest`
  - `Books shown now:`, then one line per book (`- Title, Author, Year`), or `(none)`
  - `Conversation, oldest first:`, then one `Member:` or `Finder:` line per turn
- **`gateway_model()`**: returns `OpenAIChatModel("claude-haiku-5.5", provider=OpenAIProvider(base_url=os.environ["LLM_API_GATEWAY"], api_key=os.environ["LLM_API_TOKEN"]))`. Call `load_dotenv()` inside it, not at import.
- **`answer`**:
  1. `result = await finder_agent.run(prompt_for(request), model=model)`.
  2. `books = drop_unusable_books(result.output.books)`.
  3. When `books` is not empty and `asks_for_newest(<the last member turn's text>)` is true, append a space and `NEWEST_NOTE` to the reply.
  4. Return `FinderAnswer(reply=..., books=books)`.
- **`app/main.py`**: remove the placeholder as listed under Files, and delete the `/inquire` test from `tests/test_skeleton.py`.
- **`INSTRUCTIONS`**: one string in plain sentences, saying everything under "The instructions say" in the spec (the "What the model does" section), with no additions:
  - who the member is and what the two paths mean;
  - real books only;
  - the current best list on every answer, kept, dropped, or added from the books shown;
  - a full author name may show best-known books, but a single vague clue gets a question;
  - one book when one clearly fits, up to three otherwise;
  - broad requests get a question;
  - the reply names no book that isn't on a card and doesn't think out loud;
  - no endings, twists, culprits, or deaths;
  - unrecognized books: say so, name none, and ask for the author;
  - newest by an author: the newest you know of;
  - "yes, that one": acknowledge it, point to Add a Book naming the book, don't say it was saved, and don't ask another question;
  - end with a nominate question when one book clearly fits.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_agent.py -v`
Expected: PASS.

- [ ] **Step 5: Run all checks**

Run: `uv run ruff check && uv run mypy && uv run pytest`
Expected: all pass. Step 3 removed the placeholder route, so the old `/inquire` test is already gone.

- [ ] **Step 6: Commit**

```bash
git add app/agent.py app/main.py tests/test_agent.py tests/test_skeleton.py
git commit -m "Add the finder agent and its models, and remove the placeholder route."
```

---

### Task 3: The `/inquire` route

**Files:**
- Modify: `app/main.py`
- Delete: `tests/test_skeleton.py`
- Create: `tests/test_routes.py`

**Interfaces:**
- Consumes (Task 2): `FinderRequest`, `FinderAnswer`, `answer`, `gateway_model`.
- Produces:
  - `app.main.get_model() -> Model`, a FastAPI dependency that returns `gateway_model()`
  - `POST /inquire` with a `FinderRequest` body. It answers 200 with a `FinderAnswer`, 422 for an invalid body, and 502 with `{"detail": "The book finder model is unavailable."}` when the agent raises `pydantic_ai.exceptions.AgentRunError`.
  - `GET /` is unchanged.

- [ ] **Step 1: Write the failing tests**

`tests/test_routes.py` sets `app.dependency_overrides[get_model]` in a fixture, cleans it up after each test, and wraps each test in `override_allow_model_requests(False)`.

```python
def test_page_loads():
    assert client.get("/").status_code == 200

def test_inquire_returns_the_reply_and_cleaned_books(use_model):
    use_model(TestModel(custom_output_args={"reply": "That's Dead Wake.", "books": [
        {"title": "Dead Wake", "author": "Erik Larson", "year": 2015, "reason": "r"},
        {"title": "dead wake", "author": "erik larson", "year": 2015, "reason": "r"}]}))
    response = client.post("/inquire", json={"path": "find", "turns": [{"speaker": "member", "text": "a ship sinks, the author is erik larson"}], "books": []})
    assert response.status_code == 200
    assert response.json() == {"reply": "That's Dead Wake.", "books": [{"title": "Dead Wake", "author": "Erik Larson", "year": 2015, "reason": "r"}]}

def test_inquire_rejects_a_request_ending_with_the_finder(use_model):
    response = client.post("/inquire", json={"path": "find", "turns": [{"speaker": "finder", "text": "Which book?"}]})
    assert response.status_code == 422

def test_inquire_answers_502_when_the_model_output_never_validates(use_model):
    use_model(TestModel(custom_output_args={"reply": "x", "books": "not a list"}))
    response = client.post("/inquire", json={"path": "find", "turns": [{"speaker": "member", "text": "hi"}]})
    assert response.status_code == 502
    assert response.json() == {"detail": "The book finder model is unavailable."}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_routes.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_model' from 'app.main'`.

- [ ] **Step 3: Implement the route in `app/main.py`**

`async def inquire(request: FinderRequest, model: Annotated[Model, Depends(get_model)]) -> FinderAnswer`. It awaits `answer(request, model)`, and on `AgentRunError` raises `HTTPException(status_code=502, detail="The book finder model is unavailable.")`. The module docstring stays "FastAPI routes and the page. No business rules here."

- [ ] **Step 4: Run all checks**

Run: `uv run ruff check && uv run mypy && uv run pytest`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py tests/test_skeleton.py
git commit -m "Answer /inquire with the finder agent, and 502 when the model is unavailable."
```

---

### Task 4: The chat page

**Files:**
- Modify: `app/page.html` (replace its contents)
- Modify: `tests/test_routes.py` (page tests)

**Interfaces:**
- Consumes (Task 3): `POST /inquire` with the request and answer shapes above.
- Produces: the page. No later task depends on it.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize("copy", [
    "Hi, I'm here to help you nominate a book. Do you have one in mind, or would you like help coming up with one?",
    "I have one in mind", "I need help coming up with one",
    "Great, I'd love to help you find it. Tell me any details you can recall.",
    "Great, I'll make suggestions. Tell me what kinds of books you like.",
    "Sorry, I couldn't reach the book finder just now. Please try again.",
    "This chat is getting long. Tap New search to start fresh.",
    "Likely books", "New search",
])
def test_page_contains_the_fixed_copy(copy):
    assert copy in html.unescape(client.get("/").text)

def test_page_no_longer_has_the_nomination_form():
    assert "nomination-title" not in client.get("/").text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_routes.py -v`
Expected: FAIL on the greeting and other new copy.

- [ ] **Step 3: Write `app/page.html`**

Follow the mockup's layout:

- **Layout:** a header with "Book finder" and the `+ New search` button; the chat thread; the **Likely books** area pinned above the input bar; the text box and **Send**.
- **State** in one script object: `path` (null until chosen), `turns` (a list of `{speaker, text}`), `books` (the current cards), `waiting` (bool).
- **Behavior:**
  - **Choosing:** sets `path`, fades the other button, disables both, adds the matching fixed follow-up bubble, and enables the text box.
  - **Send** (button or Enter):
    1. Ignore an empty box, or a send while `waiting`.
    2. Add the member bubble and turn.
    3. POST `{path, turns, books}`.
    4. On 200: add a finder bubble and turn with the reply, replace the cards with `books`, and highlight for about two seconds each card whose title and author were not on the previous list.
    5. On any other status, or a network error: add the error line as a finder bubble. It is not added to `turns`, and the member's line stays in `turns`.
    6. Disable Send while `waiting`.
  - **The limit:** when the member has 30 lines, add the limit line and disable the text box and Send.
  - **New search:** resets the state, the thread, and the cards, and shows the greeting and both buttons again.
  - **Safety:** every piece of model or member text goes in with `textContent`, never `innerHTML`.
  - **No cards:** when `books` is empty, the Likely books area is hidden.

- [ ] **Step 4: Run all checks**

Run: `uv run ruff check && uv run mypy && uv run pytest`
Expected: all pass.

- [ ] **Step 5: Check it in a browser**

Run `uv run fastapi dev app/main.py` with `.env` present.

1. Pick **I have one in mind**, then send "it's by Becky Chambers", "it was about space travel", and "the title had something about an angry planet". Expected: replies appear, and the cards narrow to *The Long Way to a Small, Angry Planet*.
2. Tap **New search**. Expected: the chat and cards clear.
3. Stop the gateway by unsetting `LLM_API_TOKEN` and restarting, then send a line. Expected: the error line appears and the member's line stays.

- [ ] **Step 6: Commit**

```bash
git add app/page.html tests/test_routes.py
git commit -m "Build the choose-then-chat page with the pinned likely books."
```

---

### Task 5: The evaluation script

**Files:**
- Create: `scripts/evaluate_finder.py`, `scripts/finder_cases.json`

**Interfaces:**
- Consumes (Task 2): `FinderRequest`, `Turn`, `BookOption`, `answer`, `gateway_model`, and `NEWEST_NOTE` from Task 1.
- Produces: a script run by hand, `uv run python scripts/evaluate_finder.py [case-id ...]`. It is not collected by pytest, because it has no `test_` name and lives outside `tests/`.

- [ ] **Step 1: Write `scripts/finder_cases.json`**

A list of case objects:

- **Required keys:** `id`, `path`, `lines` (member lines).
- **Optional keys:**
  - `one_at_a_time` (bool): send the lines as separate turns, carrying the finder replies and cards forward;
  - `prior_turns` and `prior_books`: start from an earlier conversation;
  - `expect_title`: lowercase, must be on the final cards;
  - `expect_no_books` (bool);
  - `expect_note` (bool);
  - `expect_reply_contains` (string).

When `one_at_a_time` is absent, all lines are sent as member turns in one request. The cases:

```json
[
 {"id":"1","path":"find","lines":["author's name was greg something, the title had bear in it, and it was biology science fiction"],"expect_title":"blood music"},
 {"id":"2","path":"suggest","lines":["a book with themes like Brave New World"]},
 {"id":"3-find","path":"find","lines":["a sci-fi book by Aldous Huxley"]},
 {"id":"3-suggest","path":"suggest","lines":["a sci-fi book by Aldous Huxley"]},
 {"id":"4","path":"find","lines":["a ship sinks, the author is erik larson"],"expect_title":"dead wake"},
 {"id":"6","path":"suggest","lines":["a book about space travel with mystery and aliens"]},
 {"id":"7","path":"find","lines":["the martian"],"expect_title":"the martian"},
 {"id":"8","path":"find","lines":["agatha something, murder on a train"],"expect_title":"murder on the orient express"},
 {"id":"x","path":"suggest","lines":["something like Brave New World"]},
 {"id":"a1-find","path":"find","lines":["Kazuo Ishiguro"]},
 {"id":"a1-suggest","path":"suggest","lines":["Kazuo Ishiguro"]},
 {"id":"a2","path":"suggest","lines":["dune or something like it"]},
 {"id":"t1","path":"find","lines":["Pachinko"],"expect_title":"pachinko"},
 {"id":"t2","path":"suggest","lines":["books along the lines of Station Eleven"]},
 {"id":"f1","path":"find","lines":["something like Brave New World","I mean the actual book"],"expect_title":"brave new world"},
 {"id":"f2","path":"find","lines":["a book like The Martian","no, I mean The Martian itself"],"expect_title":"the martian"},
 {"id":"f3","path":"suggest","lines":["the martian","actually, something similar to it"]},
 {"id":"k1","path":"suggest","lines":["Help me find a book, I really liked Perdido Street Station."]},
 {"id":"k2","path":"find","lines":["I read a book recently, it had something about station in it, and a number, I think."],"expect_title":"station eleven"},
 {"id":"k3","path":"suggest","lines":["What book should I nominate?"],"expect_no_books":true},
 {"id":"k4","path":"suggest","lines":["What's the best sci-fi book written in 2026?"]},
 {"id":"k5","path":"find","lines":["What about Dungeon Crawler Carl?"],"expect_title":"dungeon crawler carl"},
 {"id":"k6-find","path":"find","lines":["she fell in love with her enemy"]},
 {"id":"k6-suggest","path":"suggest","lines":["she fell in love with her enemy"]},
 {"id":"k7-find","path":"find","lines":["motley group of friends face adventures together and bond"]},
 {"id":"k7-suggest","path":"suggest","lines":["motley group of friends face adventures together and bond"]},
 {"id":"m1","path":"find","lines":["the third book in the Expanse series"],"expect_title":"abaddon's gate"},
 {"id":"m2","path":"find","lines":["Brandon Sanderson's newest one"],"expect_note":true},
 {"id":"m3-find","path":"find","lines":["Becky Chambers"]},
 {"id":"m3-suggest","path":"suggest","lines":["Becky Chambers"]},
 {"id":"m4","path":"suggest","lines":["Becky Chambers","something cozy by her"]},
 {"id":"m5","path":"suggest","lines":["dungeon crawler carl","no wait, other books like that"]},
 {"id":"m6","path":"find","lines":["the hunger gmes"],"expect_title":"the hunger games"},
 {"id":"m7","path":"suggest","lines":["a novel set in Hawaii"]},
 {"id":"m8","path":"find","lines":["the one Oprah picked about a woman living alone in the marsh"],"expect_title":"where the crawdads sing"},
 {"id":"m9","path":"find","lines":["hi"],"expect_no_books":true},
 {"id":"m10","path":"find","lines":["what's the weather today"],"expect_no_books":true},
 {"id":"o1","path":"find","lines":["thank you!"],"expect_no_books":true},
 {"id":"o2","path":"find","lines":["please"],"expect_no_books":true},
 {"id":"o3","path":"find","lines":["what's a good recipe for banana bread?"],"expect_no_books":true},
 {"id":"o4","path":"suggest","lines":["hi, I'm looking for a book about grief"]},
 {"id":"o5","path":"suggest","lines":["the martian","thanks! now something like that but funnier"]},
 {"id":"n1-find","path":"find","lines":["help me find a nomination"],"expect_no_books":true},
 {"id":"n1-suggest","path":"suggest","lines":["help me find a nomination"],"expect_no_books":true},
 {"id":"n2","path":"find","lines":["I want to nominate Brandon Sanderson's newest book"],"expect_note":true},
 {"id":"n3-find","path":"find","lines":["I want to nominate something by Becky Chambers"]},
 {"id":"n3-suggest","path":"suggest","lines":["I want to nominate something by Becky Chambers"]},
 {"id":"n4","path":"suggest","lines":["what should our club read next?"],"expect_no_books":true},
 {"id":"n5","path":"find","lines":["I want to nominate something by Becky Chambers","it's about space travel, and the main character is a woman"]},
 {"id":"n6","path":"find","lines":["I want to nominate something by Becky Chambers","what's her newest book?"],"expect_note":true},
 {"id":"n7","path":"suggest","lines":["a book like Brandon Sanderson's newest one"]},
 {"id":"made-up","path":"find","lines":["the new Becky Chambers book, The Lantern Orchard"],"expect_no_books":true},
 {"id":"greg-alone","path":"find","lines":["the author's name was greg something"],"expect_no_books":true},
 {"id":"becky-sequence","path":"find","one_at_a_time":true,"lines":["it's by Becky Chambers","it was about space travel","the title had something about an angry planet"],"expect_title":"the long way to a small, angry planet"},
 {"id":"yes","path":"find","prior_turns":[{"speaker":"member","text":"author's name was greg something, the title had bear in it, and it was biology science fiction"},{"speaker":"finder","text":"This sounds like Blood Music by Greg Bear. Would you like to nominate it?"}],"prior_books":[{"title":"Blood Music","author":"Greg Bear","year":1985,"reason":"Biology science fiction by Greg Bear."}],"lines":["yes, that one"],"expect_reply_contains":"Add a Book"}
]
```

- [ ] **Step 2: Write `scripts/evaluate_finder.py`**

- `main()` loads the cases. The arguments, if given, filter them by `id`.
- It runs each case with `answer(request, gateway_model())`, through `asyncio.run`, and prints one block per case: the id, the lines, the reply, and the cards as `title / author / year`.
- It checks each `expect_*` key that's present and prints `PASS` or `FAIL` with the reason.
- It ends with `N of M expectations met` and exits 0 either way, since this is a measurement, not a gate.
- `expect_title` matches when it's a substring of a lowercased card title.
- An exception in one case prints `ERROR` with the exception type and continues.
- Keep `main()` under the complexity limit by putting the request-building and the checks in their own small functions.

- [ ] **Step 3: Run it and keep the output for the pull request**

Run: `PYDANTIC_AI_NO_BANNER=1 uv run python scripts/evaluate_finder.py` (needs `.env` and network).
Expected: it prints every case and the summary line. Copy the summary and any `FAIL` lines into the pull request's Test plan. This is not a pass or fail gate.

- [ ] **Step 4: Run all checks**

Run: `uv run ruff check && uv run mypy && uv run pytest`
Expected: all pass. Ruff checks `scripts/`; pytest collects nothing from it.

- [ ] **Step 5: Commit**

```bash
git add scripts/evaluate_finder.py scripts/finder_cases.json
git commit -m "Add the hand-run finder evaluation script and its cases."
```

---

### Task 6: Record the decisions in `docs/proposal.md`

**Files:**
- Modify: `docs/proposal.md`, only in the sections below. Each edit states the decision, with no dated notes.

**Interfaces:** none.

- [ ] **Step 1: Edit the sections**

- **Intended user and problem**, the paragraph starting "Find means": replace "One box takes either kind of input. The model chooses find or suggest, and asks if the input could be either." with: "The member chooses which before typing: **I have one in mind** (find) or **I need help coming up with one** (suggest)."
- **Sample input set**, the "Shown books are…" line: "Shown books are named by the model from its own knowledge, then checked against Open Library before they are shown, so they are Open Library records only…". Keep the rest of the line.
- **Big-picture sketch**, item 1: "A chat. The member chooses find or suggest, then sends clues one line at a time; the model replies to each line and keeps up to three likely books pinned above the text box, updating them as clues arrive."
- **Up to three core features**, item 1: "An agent chat in which the model names up to three likely books from the member's clues, which Open Library then checks, or asks for more information."
- **LLM role**:
  - First call: input is the path, the conversation, and the books shown. Output is a reply and up to three likely books, with the guards from the design.
  - Second call: checks the named books in Open Library by title and author before they are shown. When the model names none, or the member says the book is newer, it searches Open Library with the member's words or the author's name. It does not fill the form from memory.
  - The third call is unchanged.
- **Outside version one**, the Later line: add "tabs for several searches at once."
- **Open questions**: add "The model's knowledge has a cutoff, so books newer than it, including an author's newest, need Open Library sorted by date or a web search. Which one, and whether a web search can go through the gateway, is open."

- [ ] **Step 2: Run all checks**

Run: `uv run ruff check && uv run mypy && uv run pytest`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add docs/proposal.md
git commit -m "Record the choose-then-chat decisions in the proposal."
```

The pull request Summary names these proposal sections:

- Intended user and problem
- Sample input set
- Big-picture sketch
- Up to three core features
- LLM role
- Outside version one
- Open questions

It also names the Layout section of `AGENTS.md`.
