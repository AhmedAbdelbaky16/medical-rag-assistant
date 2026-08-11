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
- [x] Phase 9 — Frontend
- [x] Phase 10 — Docker Compose (full stack)
- [x] Phase 11 — Evaluation
- [ ] Phase 12 — Fine-tuning (optional)
- [ ] Phase 13 — Packaging & deploy

## Phase 0/1 — Setup instructions (run these on your own machine)

This project calls the public DailyMed API, which isn't reachable from
a sandboxed dev environment — run these steps locally:

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Download the drug labels (~40 drugs, a few MB total)
cd src
python download_labels.py

# 4. Parse and clean them into structured JSON
python parse_labels.py
```

After step 3, check `data/raw/` — one `.xml` file per drug. After step
4, check `data/processed/` — one clean `.json` file per drug, each
broken into labeled sections (e.g. `WARNINGS`, `DOSAGE AND
ADMINISTRATION`).

## Project structure

```
rag-medical-assistant/
├── data/
│   ├── raw/            # raw SPL XML labels from DailyMed
│   └── processed/      # cleaned, section-parsed JSON
├── sql/
│   └── schema.sql        # drugs + sections + chunks table definitions
├── src/
│   ├── config.py           # paths, drug list, API/DB/chunking/generation/frontend config
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
│   ├── api.py                # Phase 8: FastAPI backend — same pipeline, over HTTP
│   └── frontend.py            # Phase 9: Streamlit chat UI, calls the API over HTTP
├── notebooks/            # scratch/exploration (not part of the pipeline)
├── docker-compose.yml
├── Dockerfile              # Phase 10: image used for both api and frontend services
├── .dockerignore
├── requirements.txt
└── README.md
```

`src/` also contains Phase 11's evaluation files:
`eval_metrics.py` (scoring logic), `eval_set.py` (25 questions),
`evaluate_retrieval.py`, `evaluate_generation.py` — see below.

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

Two core tables: `drugs` (one row per drug) and `sections` (one row
per label section, linked to its drug via a foreign key). See
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

## Phase 9 — Frontend

A Streamlit chat interface, calling the FastAPI backend (Phase 8) over
plain HTTP — same as any other client would — rather than importing
the pipeline directly. Keeps frontend and backend genuinely decoupled.

```bash
python -m streamlit run frontend.py
```
(Use `python -m streamlit` rather than the bare `streamlit` command if
Windows can't find it on PATH, same issue as `uvicorn` in Phase 8.)

Requires Postgres, the API, and Ollama all running. Shows the answer,
a faithfulness badge, and an expandable source list with cited/not-
cited markers and distance scores — so the reasoning behind an answer
is visible, not just the final text.

## Phase 10 — Docker Compose (full stack)

Bundles Postgres, the API, and the frontend into one command instead
of three separate terminals:

```bash
docker compose up -d --build
```

Then open **http://localhost:8501** for the chat UI, or
**http://localhost:8000/docs** for the API directly.

Ollama stays **outside** Docker, running normally on your host machine
— containerizing it would add GPU/model-management complexity this
project doesn't need, and it's already working fine as-is. The `api`
container reaches it via `host.docker.internal`, Docker's built-in DNS
name for "the machine running Docker" (works out of the box with
Docker Desktop on Windows/Mac).

**What changed to make this work:** `config.py`'s database, Ollama,
and API URLs are now read from environment variables, falling back to
the original `localhost` values when none are set — so running the
scripts directly (`python ask.py`, etc.) still works exactly as
before, unchanged. Inside Docker, `docker-compose.yml` sets:
- `DB_HOST=db` for the api service (Postgres's service name, not `localhost`)
- `OLLAMA_BASE_URL=http://host.docker.internal:11434` for the api service
- `API_BASE_URL=http://api:8000` for the frontend service (the api service's name)

The `db` service also gained a real health check (`pg_isready`)
instead of relying on `depends_on`'s default behavior, which only
waits for a container to *start*, not for Postgres to actually be
ready to accept connections — a race condition that works most of the
time locally and then fails unpredictably. `api` now waits for `db`
to report genuinely healthy before starting.

**Note:** the `api`/`frontend` containers only run the *serving*
layer (Phases 5-9's API and UI) — the one-time data pipeline scripts
(download, parse, chunk, embed) still run directly on your machine
against the same Postgres container, exactly as in every earlier
phase. The existing data survives this change untouched, since the
Postgres volume name didn't change.

## Phase 11 — Evaluation

Turns the informal "this seems to work" observations from earlier
phases into real, measured numbers, using a hand-built set of 25
questions spanning dosage, contraindications, warnings, pregnancy,
side effects, drug interactions, and overdose across multiple drugs.

```bash
python evaluate_retrieval.py     # fast — embedding + DB only, no LLM
python evaluate_generation.py    # slow — 2 LLM calls per question
```

### Results (25 questions)

| Metric | Score |
|---|---|
| Recall@1 | 0.280 |
| Recall@3 | 0.400 |
| Recall@5 | 0.560 |
| MRR | 0.363 |
| Faithfulness pass rate | 0.960 (24/25) |

**Retrieval quantifies the Phase 6 limitation** we'd only seen
anecdotally before: the correct section is the *top* result just 28%
of the time, but appears *somewhere in the top 5* 56% of the time.
That gap is the "hybrid retrieval fixes which drug, not which
section" problem, now backed by numbers across 25 questions instead
of one example.

**An important distinction the eval makes visible:** faithfulness
measures whether the answer matches what was *retrieved* — not
whether what was retrieved was actually *correct*. A high faithfulness
score and mediocre retrieval can coexist; they're answering different
questions, which is why both get measured separately rather than
collapsing into one "accuracy" number.

**The one faithfulness failure, worth a closer look:** asking about an
acetaminophen overdose, retrieval failed to find the real "Overdose"
section (consistent with the 28% recall@1 rate). The generation model
correctly flagged `sufficient_context: false` rather than confidently
answering — but still added a generic "seek medical help right away"
line that wasn't actually grounded in anything retrieved, a subtle
violation of the "use only the provided sources" instruction. The
faithfulness check caught it. This is arguably a *good* result: two
independent safety layers (the model's own context-sufficiency flag,
and the separate faithfulness pass) both worked as intended, catching
an ungrounded claim before a person would ever see it — even though
the root cause (a retrieval miss) wasn't prevented.

Full per-question results are saved to `eval_results_retrieval.json`
and `eval_results_generation.json` — committed to the repo as evidence
rather than regenerated data, unlike `data/raw`/`data/processed`.

## Design notes

- **Why the API instead of the bulk zip downloads?** DailyMed's full
  archives are multi-GB and contain thousands of unrelated labels. For
  a scoped portfolio project, pulling ~40 specific drugs by name via
  the API keeps the dataset small, relevant, and reproducible.
- **Why parse by `<section>` instead of treating the label as one blob?**
  SPL XML already tags content by section (INDICATIONS, WARNINGS,
  DOSAGE, etc.). Preserving that structure now means later phases can
  filter and chunk by section — this is what makes hybrid retrieval
  possible later instead of bolting it on afterward.
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
- **Why `pg8000` instead of `psycopg2`?** `psycopg2-binary` has no
  prebuilt wheel for newer Python versions and needs a C compiler to
  build from source. `pg8000` is a pure-Python driver, so it installs
  instantly with no extra tooling.
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
  only need tokenization for chunking, not the actual embedding model
  itself — `tokenizers` avoids pulling in `transformers` and
  eventually `torch` before they're actually needed.
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
- **Why Streamlit calling the API over HTTP, instead of importing the
  pipeline functions directly into the frontend?** Keeps the two
  genuinely decoupled — the frontend has no idea how answers get
  generated, it just calls an endpoint. This also means the same
  backend could serve other clients (a mobile app, another UI) without
  any changes.
- **Why does Ollama stay outside Docker while everything else gets
  containerized?** It's already installed and working directly on the
  host machine — containerizing it would mean solving GPU/model
  volume-mounting problems for no real benefit at this project's
  scale. `host.docker.internal` lets the containerized API reach it
  without needing to move it.
- **Why one shared Dockerfile/image for both `api` and `frontend`
  instead of two separate ones?** Same dependencies either way — a
  single image kept simple and easy to reason about was prioritized
  over a marginally smaller frontend image. A larger project serving
  real traffic might split them to reduce image size and attack
  surface per service.
- **Why add a real health check (`pg_isready`) instead of relying on
  `depends_on`?** Plain `depends_on` only waits for a container to
  *start*, not for Postgres to actually be ready to accept
  connections — a race condition that can work locally most of the
  time and then fail unpredictably. A real readiness check removes
  the guesswork.
- **Why environment-variable config with `localhost` fallbacks,
  instead of hardcoding Docker-specific values?** Running the pipeline
  scripts directly (outside Docker) is still the normal workflow for
  data ingestion/chunking/embedding — those never run inside a
  container. Env vars let the exact same `config.py` serve both
  contexts correctly, rather than needing a separate config file per
  environment.
- **Why keyword-based section matching in the eval set instead of
  exact section titles?** Real FDA labels phrase the same kind of
  section differently across drugs (numbered vs. unnumbered,
  "Directions" vs. "2.2 Recommended Dosage for..."). Matching on a
  keyword like "dosage" or "direction" finds the right section
  regardless of a given label's exact wording, rather than requiring
  the eval set to know every drug's specific title in advance.
- **Why measure retrieval and generation separately instead of one
  combined "accuracy" score?** They answer different questions — did
  retrieval find the right chunk, and did generation stay faithful to
  whatever it received. Collapsing them into one number would hide
  exactly the kind of case found in testing (a faithful answer built
  on a retrieval miss), which is the more actionable failure mode to
  understand and fix.
- **Why commit the eval result JSON files to the repo?** They're
  evidence, not pipeline data — unlike `data/raw`/`data/processed`
  (regenerable from the DailyMed API), a specific eval run's numbers
  are themselves the artifact worth keeping, and let anyone reviewing
  the repo see the actual measured results without rerunning
  anything.
