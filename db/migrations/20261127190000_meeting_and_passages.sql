-- migrate:up

CREATE TABLE meeting (
    id integer PRIMARY KEY CHECK (id = 1),
    accepting_nominations boolean NOT NULL
);

INSERT INTO meeting (id, accepting_nominations) VALUES (1, true);

CREATE EXTENSION IF NOT EXISTS vector;

-- One stored description and its embedding. The hash covers the model, the text, and the place.
CREATE TABLE passages (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    work_id integer REFERENCES works (id) ON DELETE CASCADE,
    session_id integer REFERENCES sessions (id) ON DELETE CASCADE,
    source text NOT NULL CHECK (source IN ('open_library', 'member_saved', 'member_typed')),
    body text NOT NULL,
    content_hash text NOT NULL UNIQUE,
    embedding vector(1536) NOT NULL
);

CREATE INDEX passages_work_id_idx ON passages (work_id);
CREATE INDEX passages_session_id_idx ON passages (session_id);

-- migrate:down
