-- Phase 3/4 — Database schema
--
-- Three tables:
--   drugs    — one row per drug (the structured facts)
--   sections — one row per section of a drug's label (the text content)
--   chunks   — one row per chunk: a section split into smaller,
--              embeddable pieces (Phase 4). No embedding column yet —
--              that gets added via ALTER TABLE in Phase 5, once we
--              actually generate embeddings. Adding it only when we
--              need it keeps each phase's schema change easy to follow.

-- Make sure pgvector is enabled (idempotent — safe to run every time)
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------
-- drugs: one row per drug label we've ingested
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS drugs (
    drug_id     SERIAL PRIMARY KEY,
    -- SERIAL = an auto-incrementing integer (1, 2, 3, ...).
    -- Postgres assigns this automatically on insert — we never set it
    -- ourselves. This is our PK: guaranteed unique, one per drug.

    drug_name   TEXT NOT NULL,
    -- NOT NULL means this column can never be left empty — every drug
    -- must have a name.

    setid       TEXT UNIQUE,
    -- DailyMed's own unique ID for this label. UNIQUE means Postgres
    -- will reject an insert that tries to add a duplicate setid —
    -- this stops us from accidentally loading the same drug twice.

    source_file TEXT,
    -- Which raw XML file this came from — handy for debugging later
    -- ("which drug produced this weird row?").

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    -- When this row was inserted. DEFAULT now() means we don't have to
    -- set this ourselves — Postgres fills it in automatically.
);

-- ---------------------------------------------------------------------
-- sections: one row per section of a drug's label
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sections (
    section_id     SERIAL PRIMARY KEY,

    drug_id        INTEGER NOT NULL REFERENCES drugs(drug_id) ON DELETE CASCADE,
    -- This is the FK. "REFERENCES drugs(drug_id)" tells Postgres:
    -- every value here must match a real drug_id in the drugs table —
    -- Postgres will reject an insert that points to a drug that
    -- doesn't exist. "ON DELETE CASCADE" means if a drug row is ever
    -- deleted, all its sections are automatically deleted too, instead
    -- of being left behind as orphaned rows pointing at nothing.

    section_title  TEXT NOT NULL,
    section_text   TEXT NOT NULL,

    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index: speeds up "give me all sections for drug X" lookups, which is
-- exactly the query pattern we'll use constantly once retrieval is
-- built (Phase 6). Without this index, Postgres scans the whole table
-- every time. With it, this becomes a fast lookup.
CREATE INDEX IF NOT EXISTS idx_sections_drug_id ON sections(drug_id);

-- ---------------------------------------------------------------------
-- chunks: one row per chunk (a section split into smaller pieces)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id     SERIAL PRIMARY KEY,

    section_id   INTEGER NOT NULL REFERENCES sections(section_id) ON DELETE CASCADE,

    drug_id      INTEGER NOT NULL REFERENCES drugs(drug_id) ON DELETE CASCADE,
    -- This duplicates information we could already get by joining
    -- through sections -> drugs. We store it directly anyway because
    -- Phase 6's hybrid retrieval will constantly filter chunks by
    -- drug_id ("only search ibuprofen's chunks") — having it right on
    -- this table avoids a join on every single retrieval query. This
    -- kind of deliberate duplication for read speed is called
    -- denormalization — a tradeoff of a bit of redundancy for faster
    -- reads, reasonable here since a chunk's drug never changes once
    -- created.

    chunk_index  INTEGER NOT NULL,
    -- Position of this chunk within its section (0, 1, 2, ...) — lets
    -- us reconstruct order, or show "chunk 2 of 5" in a UI later.

    chunk_text   TEXT NOT NULL,
    token_count  INTEGER NOT NULL,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chunks_section_id ON chunks(section_id);
CREATE INDEX IF NOT EXISTS idx_chunks_drug_id ON chunks(drug_id);
