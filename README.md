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
- [x] Phase 5 — Embeddings
- [x] Phase 6 — Hybrid retrieval
- [x] Phase 7 — Generation
- [x] Phase 8 — Backend API
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
│   ├── chunk_and_load.py   # Phase 4: tokenize + chunk all sections, write to DB
│   ├── embed_and_load.py   # Phase 5: generate + store embeddings via pgvector
│   ├── retrieval.py        # Phase 6: drug detection + hybrid (SQL + vector) search
│   ├── test_search.py      # manual test: pure vector search
│   ├── compare_search.py   # Phase 6: pure vector vs. hybrid search, side by side
│   ├── generate.py         # Phase 7: context building, prompting, faithfulness check
│   ├── ask.py               # Phase 7: end-to-end CLI — question in, cited answer out
│   └── api.py                # Phase 8: FastAPI backend — same pipeline, over HTTP
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

## Phase 5 — Embeddings

Generates a vector embedding for every chunk and stores it via
`pgvector`, enabling similarity search — "find chunks whose meaning is
closest to this question," not just keyword matching.

Uses [`fastembed`](https://github.com/qdrant/fastembed) to run
`bge-small-en-v1.5` through ONNX Runtime rather than the more common
`sentence-transformers` + PyTorch route — same model, same 384-dimension
output, but a much lighter install (no PyTorch download/setup needed).

```bash
python embed_and_load.py
```

First run downloads the ONNX model files (~130MB, one-time, cached
afterward). Only embeds chunks that don't already have one, so it's
safe to re-run after adding more drugs later. Builds the `pgvector`
similarity index (`ivfflat`) at the end, once real embeddings exist to
index — building it earlier would produce a low-quality index, since
`ivfflat` clusters based on a sample of whatever data exists at
creation time.

Verify:
```bash
docker exec -it medical-rag-db psql -U raguser -d medical_rag -c "SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL;"
```

## Phase 6 — Hybrid retrieval

**The problem, found for real during Phase 5 testing:** pure vector
search across all 40 drugs can rank an unrelated drug's chunk above
the actually-relevant one, if it happens to mention the right word in
passing — e.g. asking about ibuprofen's max dose pulled back
Metformin's drug-interaction table, because that table mentions
"ibuprofen" in a comparison, and Naproxen (a different NSAID)
outranked Ibuprofen entirely.

**The fix:** if the question names a known drug, filter to that
drug's chunks with SQL *before* ranking by vector distance — vector
search then only has to compete within the right drug's own content,
instead of across everything.

```bash
python compare_search.py "what is the max daily dose of ibuprofen?"
```
prints pure vector search and hybrid search results side by side, so
the fix is directly visible.

**Known limitation (intentionally not fixed here):** hybrid retrieval
only fixes *which drug* gets searched — it doesn't fix *which section
within that drug* ranks best, which is still plain vector similarity
and is imperfect. In testing, an "Active ingredient" listing
outranked the actual "Directions" (dosage) section for a dosage
question, once correctly filtered to the right drug. Addressing this
would mean adding a reranker or tuning based on evaluation results —
tracked for Phase 11/12, not solved here.

## Phase 7 — Generation

Turns retrieved chunks into an actual answer, grounded in that
context, with citations back to specific sources — instead of handing
the person a list of raw chunks to read themselves.

Runs locally via [Ollama](https://ollama.com/), no API key or cost.
Generation uses `qwen2.5:7b`; requires Ollama running
(`ollama serve`, or the desktop app) with that model pulled.

```bash
python ask.py "what is the max daily dose of ibuprofen?"
```

Two model calls happen per question:
1. **Generation** — answers using only the provided context, returns
   structured JSON (`answer`, `cited_sources`, `sufficient_context`),
   parsed defensively since local models occasionally produce
   malformed JSON even when asked not to.
2. **Faithfulness check** — a second call asking "is this answer
   actually supported by the sources?", to catch hallucination before
   the person sees it.

**A real finding worth keeping:** the faithfulness check originally
used a much smaller/faster model (`qwen2:0.5b`) on the assumption that
judging support is simpler than generating an answer. Testing showed
otherwise — the 0.5b model misread its own source text (turning
"4 to 6 hours" into a garbled "two-fourths hours" in its explanation)
and incorrectly flagged a genuinely correct, well-cited answer as
unsupported. Switched to using the same capable model for both steps.
Faithfulness checking is its own reasoning task, not a rubber stamp —
an underpowered model can fail at it even when the actual answer is
fine.

Context sent to the model is capped at ~1500 words, keeping the
highest-relevance sources and dropping lower-ranked ones if the full
set would exceed that — approximated by word count rather than exact
tokenization, since the exact qwen tokenizer isn't needed for a rough
budget check.

## Phase 8 — Backend API

Wraps the same pipeline (Phases 5-7) as a real HTTP service via
FastAPI, instead of a CLI script — the difference between "a pipeline
I run in a terminal" and "an application."

```bash
python -m uvicorn api:app --reload
```
(Use `python -m uvicorn` rather than the bare `uvicorn` command if
Windows can't find it on PATH — pip sometimes installs scripts to a
folder that isn't there by default.)

Endpoints:
- `POST /ask` — the real endpoint. Body: `{"question": "...", "top_k": 5, "check_faithfulness": true}`
- `GET /health` — checks DB connectivity and reports how many chunks have embeddings
- `GET /docs` — interactive API docs (auto-generated from the Pydantic models), can run real requests from the browser

The embedding model loads once at startup, not per-request — reloading
it every time would be slow and pointless since it never changes.
Ollama being unreachable (e.g. forgot to run `ollama serve`) returns a
clean `503` with a clear message, not a raw stack trace.

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
- **Why `fastembed` instead of `sentence-transformers`?** Both can run
  `bge-small` and produce identical-shape output, but
  `sentence-transformers` depends on PyTorch (100+ MB, GPU/CPU
  detection overhead). `fastembed` runs the same model through ONNX
  Runtime — much lighter, and CPU inference is all a laptop-scale
  project like this needs.
- **Why build the `ivfflat` similarity index in the embedding script
  instead of `schema.sql`?** `ivfflat` clusters its index based on
  whatever data exists at the moment `CREATE INDEX` runs. Since
  `schema.sql` runs early (Phase 3, before chunks or embeddings
  exist), building the index there would index effectively nothing —
  Postgres itself warns about this. Building it after real embeddings
  exist gives a meaningfully better index.
- **Why detect the drug by checking known names against the question
  text, instead of something more sophisticated (NER model, LLM
  extraction)?** The full drug list is small and already known ahead
  of time (it's `config.DRUG_LIST`) — simple substring matching is
  reliable, fast, needs no extra model, and is easy to debug when it
  gets something wrong. A more general system with an open-ended set
  of entities would need a different approach.
- **Why check longest drug names first?** To avoid a shorter name
  matching inside a longer one accidentally (e.g. a hypothetical
  "insulin" matching before the more specific "insulin glargine" —
  not currently a conflict in this drug list, but a real failure mode
  worth guarding against generally).
- **Why Ollama instead of a hosted API (Claude, OpenAI)?** Free, fully
  local, no API key or per-request cost — a deliberate choice for this
  project, and it demonstrates working with self-hosted inference
  rather than just wrapping someone else's API.
- **Why a second "faithfulness check" model call instead of trusting
  the generation model's own citations?** A model can cite a source
  and still say something that source doesn't actually support —
  citing isn't the same as being correct. A separate pass, asking
  specifically "is this supported?", catches that category of error
  the first call wouldn't self-report.
- **Why word-count budgeting instead of exact token counting for the
  generation context?** The generation model (qwen) has a different
  tokenizer than the embedding model, and loading a second exact
  tokenizer just for a rough context-size guardrail wasn't worth the
  added complexity — word count is a close enough proxy for this
  purpose.
- **Why load the embedding model once at startup instead of per-request?**
  It never changes between questions, so reloading it every request
  would just be wasted latency for no benefit.
- **Why a new database connection per request instead of a connection
  pool?** Simple and matches every other script in this project. Fine
  at this project's scale (a portfolio demo, not real concurrent
  traffic) — a production API would use a connection pool instead.
