-- migrate:up

-- One search conversation. It stores the member's request.
CREATE TABLE sessions (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    request text NOT NULL
);

-- One Open Library lookup in a session.
CREATE TABLE searches (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id integer NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    words_sent text NOT NULL,
    outcome text NOT NULL CHECK (
        outcome IN (
            'books came back',
            'nothing matched',
            'rate-limiting',
            'down'
        )
    )
);

CREATE INDEX searches_session_id_idx ON searches (session_id);

-- One book confirmed by Open Library.
CREATE TABLE works (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL,
    page_count integer CHECK (page_count >= 0),
    isbn text,
    open_library_description text
);

-- One author, one row for one Open Library spelling.
CREATE TABLE authors (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE
);

-- One author of one book.
CREATE TABLE authorships (
    author_id integer NOT NULL REFERENCES authors (id) ON DELETE CASCADE,
    work_id integer NOT NULL REFERENCES works (id) ON DELETE CASCADE,
    PRIMARY KEY (author_id, work_id)
);

CREATE INDEX authorships_work_id_idx ON authorships (work_id);

-- One session showed one book, picked or rejected.
CREATE TABLE offerings (
    session_id integer NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
    work_id integer NOT NULL REFERENCES works (id) ON DELETE CASCADE,
    choice text NOT NULL CHECK (choice IN ('picked', 'rejected')),
    PRIMARY KEY (session_id, work_id)
);

CREATE INDEX offerings_work_id_idx ON offerings (work_id);

-- One save of one book. The session is cleared if that session is deleted.
CREATE TABLE nominations (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    work_id integer NOT NULL REFERENCES works (id) ON DELETE CASCADE,
    session_id integer UNIQUE REFERENCES sessions (id) ON DELETE SET NULL,
    member_description text NOT NULL,
    post_succeeded boolean NOT NULL
);

CREATE INDEX nominations_work_id_idx ON nominations (work_id);

-- migrate:down


