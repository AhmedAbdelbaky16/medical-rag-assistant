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
- [ ] Phase 2 — Database setup (Docker + Postgres)
- [ ] Phase 3 — SQL schema & structured data
- [ ] Phase 4 — Tokenization & chunking
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
├── src/
│   ├── config.py        # paths, drug list, API config
│   ├── download_labels.py  # Phase 1a: pull labels from DailyMed
│   └── parse_labels.py     # Phase 1b: clean + section-parse XML
├── notebooks/            # scratch/exploration (not part of the pipeline)
├── requirements.txt
└── README.md
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
