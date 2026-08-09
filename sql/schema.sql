-- Phase 3 — Database schema
--
-- Two tables for now:
--   drugs    — one row per drug (the structured facts)
--   sections — one row per section of a drug's label (the text content)
--
-- A "chunks" table gets added in Phase 4/5, once we start splitting
-- sections into smaller pieces for embedding. We're not building it
-- yet because we don't need it yet — adding tables as each phase
-- actually needs them keeps the schema easy to follow.

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
