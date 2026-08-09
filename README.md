# Medical RAG Assistant — Build Log

A step-by-step RAG (Retrieval-Augmented Generation) project answering
questions about FDA drug labels, built from scratch to learn the full
pipeline: data ingestion → SQL → embeddings → hybrid retrieval →
generation → evaluation → deployment.

**Repo:** https://github.com/AhmedAbdelbaky16/medical-rag-assistant

**⚠️ Educational project only.** This is not medical advice and should
never be used for real clinical decisions.

## Clone this repo

```bash
git clone https://github.com/AhmedAbdelbaky16/medical-rag-assistant.git
cd medical-rag-assistant
```

## Status
- [x] Phase 0 — Project setup
- [x] Phase 1 — Data ingestion & cleaning
- [x] Phase 2 — Database setup (Docker + Postgres)
- [x] Phase 3 — SQL schema & structured data
- [x] Phase 4 — Tokenization & chunking
- [ ] Phase 5 — Embeddings
- [ ] Phase 6 — Hybrid retrieval
- [ ] Phase 7 — Generation
- [ ] Phase 8 — Backend API
- [ ] Phase 9 — Frontend
- [ ] Phase 10 — Docker Compose
- [ ] Phase 11 — Evaluation
- [ ] Phase 12 — Fine-tuning (optional)
- [ ] Phase 13 — Packaging & deploy

## Phase 0/1 — Setup instructions (run these on your own machine)

This project calls the public DailyMed API, which isn't reachable from
the sandbox this was built in — so run these steps locally:

```bash
# 1. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download the drug labels (~40 drugs, a few MB total)
cd src
python3 download_labels.py

# 4. Parse and clean them into structured JSON
python3 parse_labels.py
```

After step 3, check `data/raw/` — you should see one `.xml` file per
drug. After step 4, check `data/processed/` — one clean `.json` file
per drug, each broken into labeled sections
(e.g. `WARNINGS`, `DOSAGE AND ADMINISTRATION`).

## Project structure

```
rag-medical-assistant/
├── data/
│   ├── raw/            # raw SPL XML labels from DailyMed
│   └── processed/      # cleaned, section-parsed JSON
├── sql/
│   └── schema.sql        # drugs + sections + chunks table definitions
├── src/
│   ├── config.py           # paths, drug list, API config, DB config, chunking config
│   ├── download_labels.py  # Phase 1a: pull labels from DailyMed
│   ├── parse_labels.py     # Phase 1b: clean + section-parse XML
│   ├── load_to_db.py       # Phase 3: apply schema + load JSON into Postgres
│   ├── chunking.py         # Phase 4: core chunking algorithm (unit-testable)
│   └── chunk_and_load.py   # Phase 4: tokenize + chunk all sections, write to DB
├── notebooks/            # scratch/exploration (not part of the pipeline)
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Phase 2 — Database setup

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(with WSL2 backend on Windows) installed and running.

```bash
docker compose up -d
```

This starts a PostgreSQL 16 container with the `pgvector` extension
pre-installed, on `localhost:5432`. Credentials (local dev only, not
used anywhere public) are set in `docker-compose.yml`.

Verify it's running:
```bash
docker ps
docker exec -it medical-rag-db psql -U raguser -d medical_rag -c "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname FROM pg_extension;"
```
You should see `vector` and `plpgsql` listed.

To stop the database:
```bash
docker compose down
```
(Data persists in a Docker volume — `docker compose down` does not
delete it. `docker compose down -v` would, if you ever want a clean
slate.)

## Phase 3 — SQL schema & structured data

Two tables: `drugs` (one row per drug) and `sections` (one row per
label section, linked to its drug via a foreign key). See
`sql/schema.sql` for the full definitions and inline comments
explaining each design choice.

Load all parsed JSON into the database:
```bash
cd src
python load_to_db.py
```

This applies the schema (safe to re-run) and loads every file in
`data/processed/`. Re-running is idempotent — existing drugs are
updated rather than duplicated, and each drug's sections are fully
replaced from the current JSON rather than appended to.

Verify:
```bash
docker exec -it medical-rag-db psql -U raguser -d medical_rag -c "SELECT COUNT(*) FROM drugs;"
docker exec -it medical-rag-db psql -U raguser -d medical_rag -c "SELECT COUNT(*) FROM sections;"
```

**Browsing the data:** either `psql` directly via the `docker exec`
commands above, or a GUI client like [DBeaver](https://dbeaver.io/)
(free) connecting to `localhost:5432`, database `medical_rag`, using
the credentials in `docker-compose.yml`.

## Phase 4 — Tokenization & chunking

Sections vary a lot in length — some are a sentence or two, others
(like drug interaction or pharmacokinetics sections) run to thousands
of words. Chunking splits long sections into smaller, focused pieces
before embedding, since one embedding for a huge section would be a
vague "average" of many unrelated ideas.

Strategy (see `src/chunking.py` for the full logic and inline
explanation):
- A section that already fits within the max chunk size stays as one
  chunk, untouched.
- Longer sections are split at sentence boundaries, packed greedily up
  to a target size, with the tail of each chunk overlapping into the
  next one for continuity.
- A rare edge case — a single "sentence" that's already too long on
  its own (this happens with flattened data tables that have almost
  no real sentence breaks) — falls back to splitting by words instead.

Token counts use the real tokenizer from the embedding model we'll use
in Phase 5 (`BAAI/bge-small-en-v1.5`), so chunk sizes are accurate to
what actually matters downstream.

```bash
python chunk_and_load.py
```

First run downloads the tokenizer files from Hugging Face (small,
one-time, cached afterward).

Verify:
```bash
docker exec -it medical-rag-db psql -U raguser -d medical_rag -c "SELECT COUNT(*) FROM chunks;"
```

## Design notes

- **Why the API instead of the bulk zip downloads?** DailyMed's full
  archives are multi-GB and contain thousands of unrelated labels. For
  a scoped portfolio project, pulling ~40 specific drugs by name via
  the API keeps the dataset small, relevant, and reproducible.
- **Why parse by `<section>` instead of treating the label as one blob?**
  SPL XML already tags content by section (INDICATIONS, WARNINGS,
  DOSAGE, etc.). Preserving that structure now means Phase 3 (SQL) and
  Phase 4 (chunking) can filter and chunk by section — this is what
  makes hybrid retrieval possible later instead of bolting it on
  afterward.
- **Empty sections are dropped**, not stored — no point embedding or
  indexing sections with no content.
- **Why `pgvector/pgvector` instead of separate SQL + vector databases?**
  One database doing both jobs (structured filtering *and* vector
  similarity search) keeps hybrid retrieval simple — a single SQL query
  can filter by drug/section and rank by embedding distance in one
  step, instead of coordinating two separate systems.
- **Why Docker Compose instead of a bare `docker run`?** Reproducible,
  version-controlled, and it's where later services (backend,
  frontend) get added in Phase 10 so the whole stack starts together.
- **Why two tables (`drugs`, `sections`) instead of one flat table?**
  A drug's name would otherwise repeat across every one of its
  sections — wasted storage, and a typo fix would need updating many
  rows instead of one. Splitting into a one-to-many relationship
  (drug → many sections) linked by a foreign key avoids that.
- **Why `pg8000` instead of `psycopg2`?** Same Python 3.14 wheel-build
  issue as `lxml` in Phase 1 — `psycopg2-binary` has no prebuilt wheel
  yet for this Python version and needs a C compiler to build from
  source. `pg8000` is a pure-Python driver, so it installs instantly
  with no extra tooling.
- **Why does `load_to_db.py` delete + reinsert a drug's sections on
  every run, instead of diffing?** Sections are fully derived from the
  JSON with no user edits to preserve, so a full replace is simpler
  and safer than trying to reconcile partial changes.
- **Why token-based chunk sizing instead of character-based?**
  Embedding models see tokens, not characters, and token-to-character
  ratio varies with word length — medical text especially, given long
  words like "hyperchloremic." Measuring with the actual tokenizer
  means chunk sizes are accurate to what the model actually sees.
- **Why section-aware chunking instead of fixed-size chunking across
  the whole label?** Sections aren't uniform length — a fixed chunk
  size either pointlessly splits short, already-coherent sections or
  barely dents long ones. Respecting section boundaries first, and
  only splitting further when a section is actually too long, avoids
  both problems.
- **Why overlap between chunks?** Cutting a long section at a hard
  boundary can strand a sentence like "the risk factors listed above"
  without its antecedent. Carrying the last portion of one chunk into
  the start of the next preserves that continuity.
- **Why `tokenizers` instead of the full `transformers` library?** We
  only need tokenization in Phase 4, not the actual embedding model
  yet (that's Phase 5) — `tokenizers` avoids pulling in `transformers`
  and eventually `torch` before they're actually needed.
