# Choose, then chat with the model

## Intent

A book club member opens the finder either remembering a book they want to nominate or wanting help coming up with one. Today `POST /inquire` returns a fixed placeholder and no model is involved. This change carries what the member types from the page to a real model and back, as a chat: the member says which kind of help they want, describes the book or the kind of book over one or more lines, and the model names the likely books.

It is the first step of `docs/proposal.md`'s finder. Checking the books in Open Library, the summary, and the nomination form come in later changes.

## Goals

- The member chooses between two paths before typing, so no model has to guess which they want.
- The member can add clues one line at a time, as they remember them, and gets a reply to each line, so it feels like talking to an agent.
- The model decides, on each line, whether to ask one more question or name books, reading every line so far.
- The model names at most three likely books, from its own knowledge, each with title, author, year, and a one-line reason. It names one book when one clearly fits.

## Non-goals

- No Open Library lookup, no summary, no nomination form, no save. The page drops the placeholder nomination area until those changes add it back.
- No **Nominate this** button and no save method: with no form and no database, either would do nothing or pretend to save.
- No tabs: **New search** clears the one conversation.
- No database. The server keeps nothing between requests.
- No web search.

## Anti-goals

These would make it a failure even if it works:

- A book the model invented, or named with the wrong author, reaches the nomination. In this change the cards show the model's books unchecked, with no notice, since the member cares about the book, not where it came from. The next change checks each named book against Open Library before it is shown, and only Open Library records ever reach the nomination form.
- A reply gives away an ending, a twist, a culprit, or a death.

## Constraints

- `AGENTS.md`: routes in `app/main.py` with no business rules; the agent and its output models in `app/agent.py`; business rules in plain Python with no FastAPI and no model client.
- Tests never call a real model. They use `TestModel` with `override_allow_model_requests(False)`.
- The gateway URL and key come from `LLM_API_GATEWAY` and `LLM_API_TOKEN`.
- `ruff` (including `max-complexity = 10`), `mypy`, and `pytest` pass. No check is weakened.
- 7.4 asks for a feature that connects the page to the model and needs no retrieval or database.

## The flow

The mockup is `2026-11-01-choose-then-chat-mockup.html`, beside this design; open it in a browser. The "fixed" and "model" tags on its bubbles belong to the mockup, not the page. Gray bubbles are fixed text, purple bubbles are written by the model, and blue bubbles are the member.

1. **Greeting** (fixed): "Hi, I'm here to help you nominate a book. Do you have one in mind, or would you like help coming up with one?" with two buttons: **I have one in mind** and **I need help coming up with one**. The text box and **Send** are disabled until the member picks one.
2. **Follow-up** (fixed), which also confirms the choice:
   - I have one in mind (path `find`): "Great, I'd love to help you find it. Tell me any details you can recall."
   - I need help coming up with one (path `suggest`): "Great, I'll make suggestions. Tell me what kinds of books you like."
3. **Send**: each line the member sends goes to the model with the path, the whole conversation so far, and the books currently shown. The model answers with a reply in the chat and its current list of likely books, zero to three:
   - **Likely books** is one area pinned above the text box. Each answer replaces its cards in place, so the model can keep, add, or drop books as clues arrive. Cards that just changed are highlighted briefly. An empty list clears the area.
   - The reply says what changed and why, and usually asks one short question that would narrow it down most. When one book clearly fits, the reply asks whether the member would like to nominate it.
   - Example from the mockup: "it's by Becky Chambers" shows three of her best-known books; "it was about space travel" drops the one that is not; "the title had something about an angry planet" leaves one card, *The Long Way to a Small, Angry Planet*.

   A "yes, that one" gets the acknowledgment described below and leaves the cards as they are.
4. **New search** (top right, a + with the words "New search") clears the chat and the Likely books area and shows the greeting again.

## What the model does

The model is `claude-haiku-5.5` through the course gateway: `OpenAIChatModel` with `OpenAIProvider(base_url=LLM_API_GATEWAY, api_key=LLM_API_TOKEN)`.

The instructions say:

- The member is choosing a book to nominate for the club. Path `find` means they have one particular book in mind and are describing it from memory. Path `suggest` means they want help coming up with one.
- Name only real, published books with the author's real name. Leave out any book you are not confident exists.
- Return the current best list on every answer, starting from the books already shown: keep the ones that still fit, drop the ones the new clue rules out, and add better ones. Name books once the clues point to them with reasonable confidence. A full author name is enough for that author's best-known books; a single vague clue, such as an author's first name, gets a question and no books.
- For `find`, name one book when one clearly fits, and up to three only when several are about equally likely. For `suggest`, name up to three.
- A request too broad to choose from, such as "what should our club read next?", gets one question about what they like instead of books.
- The reply names no book that is not on a card, and does not think out loud ("wait", "no, let me be precise").
- No endings, twists, culprits, or deaths.
- When the member names or describes a book you do not recognize, say so and name no book, along the lines of "I don't recognize that one. It may be newer than what I know. Do you remember the author, or anything else about it?" Do not invent a close-sounding title.
- For "newest" or "latest" by an author, name the newest you know of.
- When the member says yes to a book ("yes, that one"), acknowledge it and say that nominating straight from the finder is coming soon, and that for now they can add it with the club app's Add a Book form, naming the book. Do not ask another narrowing question, and do not say it was saved.

Every answer has the same shape: `reply` and `books`, the current list of zero to three `BookOption`s, each with `title`, `author`, `year` (or none), and `reason`. The list replaces the cards on the page; it is not added to them.

## Rules in plain Python

These run on every answer with books, before the page sees it:

- Drop a book with an empty title or author, and drop a repeat of a book already in the list (same title and author, ignoring case, spaces, and a leading "The" or "A").
- When the member's lines ask for the newest, latest, or most recent book, add a fixed note to the reply: "This is the newest I know of. My book knowledge stops at a cutoff, so there may be a newer one."

These are a second responsibility next to the existing nomination rule in `app/rules.py`, so `app/rules.py` splits into `app/rules/nomination.py` (the existing `save_is_rejected`) and `app/rules/books.py`, and the Layout section of `AGENTS.md` changes with it.

## When something fails

- The model call fails, or its output does not validate after Pydantic AI's retries: the route answers with an error status, and the page shows a fixed line in the chat: "Sorry, I couldn't reach the book finder just now. Please try again." The conversation stays, so the member can send again.
- An empty line cannot be sent: the page disables Send on an empty box, and the server rejects an empty line.

## Proposal sections this change edits

Per the Spec rule in `AGENTS.md`, `docs/proposal.md` changes in the sections these decisions belong to:

- **Intended user and problem**: the member chooses find or suggest with the two buttons, and the model no longer chooses.
- **Sample input set**: shown books are named by the model, then checked against Open Library before they are shown, so they are still Open Library records only.
- **Big-picture sketch**: area 1 is the choose-then-chat page: the model asks questions until it can name books, then shows up to three.
- **Up to three core features**: feature 1 is the chat, where the model names likely books and Open Library checks them before they are shown.
- **LLM role**: the first call is this chat, with the guards above; it names likely books instead of choosing find or suggest and writing searches. The second call checks the named books in Open Library by title and author before they are shown. When the model names no book, or the member says the book is newer, the second call searches Open Library with the member's words or the author's name instead. It still does not fill the form from memory.
- **Outside version one**, the Later line: tabs.
- **Open questions**: the model's knowledge has a cutoff, so newer books, including an author's newest, need Open Library sorted by date or a web search. Which one, and whether a web search goes through the gateway, is open.

## Approaches considered

1. **A router model picks find or suggest, then a second model answers.** Tried first.
   - An embedding router (`text-embedding-3-small`, as in ICS 601 lesson 4.0) got 2 of 8 example inputs right: find requests are names and plot fragments, not intent words.
   - A small chat model as router (`gemini-3.5-flash-lite`, about $0.00016 a call) reached 45 of 45 on the original set and 81 of 87 on a fresh set, after several rounds of instruction changes, each of which moved some errors elsewhere.
   - It needed an ask line, an off-topic line, and a way to tell when the member was done adding clues.
   - Dropped: choosing up front is clearer than a model's guess and removes all three.
2. **Choose up front, Search button only.** No model call until Search. Simplest, but it feels like a form, not a chat.
3. **A small model chats and a larger model names books.** The small model gathers clues and hands them over when the member taps Search. Same experience as 4, with two models to instruct and test and a hand-off where clues can get lost. The only saving is cost, a fraction of a cent per line at book-club volume.
4. **Choose up front, then one model chats and decides when to name books.** Chosen: it feels like talking to an agent, collects clues over several lines, and is one agent to test.

Within approach 4, a separate Search button (Send for clues, Search to show books) was designed first. It let the member say when they were done, which mattered when a hand-off between two models was planned. With one model reading every line, a guess shown early costs nothing: the member keeps typing and the next answer updates. So one Send button, and the model decides. Cards were first drawn as new messages in the chat after each answer; they became one pinned Likely books area that updates in place, so the member watches the guesses narrow instead of scrolling through old ones.

Two more choices within approach 4 were tried first:

- **What the model returns.** Planned Open Library searches were mocked first. The member would see search terms instead of books. The model is good at fuzzy memory ("greg something, bear" is *Blood Music* by Greg Bear), and Open Library is good at exact lookups, so the model names likely books now and Open Library checks them later.
- **Which model.** `claude-haiku-5.5` and `gemini-3.5-flash-lite` both ran on the proposal's rows and on every example from the router trials.
  - Both named the expected book in nearly every clear find case.
  - Flash-lite guessed more often and got more right, but it gave real titles wrong authors (*The Cruel Prince* by "Romeo Dallaire") and listed three books where one fit.
  - Haiku asked for more when unsure, and its mistakes were invented titles or non-books, which an Open Library lookup will not find.
  - Haiku costs about $0.00022 for an answer with books, against $0.00048.
  - Chosen: Haiku, with the guards above.

## Calls made in this design

These were not settled in the conversation:

- The page holds the conversation and the current cards, and sends all of it on every Send. Each member line and each model reply is sent with who said it, and the current cards are sent as their titles, authors, and years, so "not that one" or "the Ishiguro one" makes sense to the model. The fixed greeting and follow-up lines are not sent; the path is.
- One route, `POST /inquire`, takes the path and the conversation, and returns a reply and zero to three books. The placeholder response and the `Nomination` model are removed, and `BookOption` loses `summary` (the summary change adds it back) and gains `year`.
- Limits: at most 30 member lines in a conversation, each at most 500 characters, and each model reply sent back at most 2,000 characters. The server rejects more. The model's replies do not count toward the 30. When the member reaches 30 lines, the page shows a fixed line, "This chat is getting long. Tap New search to start fresh.", and disables Send.
- An evaluation script, run by hand and kept out of `pytest`, calls the real model on every trial example plus:
  - "the new Becky Chambers book, *The Lantern Orchard*", a made-up title, which should get no book;
  - "Brandon Sanderson's newest one" and "what's her newest book?", which should get the newest-book note;
  - a reply with *Blood Music* followed by "yes, that one", which should be acknowledged with Add a Book, not another question;
  - "the author's name was greg something" alone, which should get a question, not a guess;
  - the Becky Chambers sequence from the mockup, run one line at a time with the cards carried forward, which should narrow to *The Long Way to a Small, Angry Planet*.

  For each case it prints the books and the reply, and scores find cases on whether the expected title is named. It lives in `scripts/` and reads the cases from a file beside it, copied from the trial scripts, which are not committed. A case with several lines sends them all as member lines in one request, as the trials did, so runs stay comparable. Cases the router trial labeled "ask" run on both paths.

## Left to the builder

- The page's markup, styling, and script, following the mockup. Colors and spacing can change later.
- The exact wording of the model's instructions, as long as it says everything above.
- The error status code.
- How the tests exercise the page: at least that the page serves the greeting, both buttons, and the fixed follow-up lines.
