"""
Project-wide configuration.

Keeping this in one place means every script (download, parse, etc.)
reads the same drug list and the same paths — no magic strings scattered
around the codebase.
"""

from pathlib import Path

# --- Paths -------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# --- DailyMed API --------------------------------------------------------
DAILYMED_BASE_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2"

# --- Chunking (Phase 4) --------------------------------------------------
# Tokenizer matches the embedding model we'll use in Phase 5, so token
# counts here are accurate for what actually matters later.
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

CHUNK_TARGET_TOKENS = 300
CHUNK_MAX_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 50

# --- Generation (Phase 7) --------------------------------------------------
# Ollama must be running locally (ollama serve, or the desktop app) with
# this model already pulled. qwen2:0.5b is much faster for quick testing
# while building the pipeline; swap to qwen2.5:7b for real answer quality.
OLLAMA_BASE_URL = "http://localhost:11434"
GENERATION_MODEL = "qwen2.5:7b"

# --- Database --------------------------------------------------------
# These match docker-compose.yml. Local dev only — fine to keep as
# plain values for now since this only ever runs against your own
# local container. If this project ever talked to a real/shared
# database, these would move into a .env file kept out of git instead.
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "medical_rag",
    "user": "raguser",
    "password": "ragpassword",
}

# --- Curated drug list ---------------------------------------------------
# ~40 well-known drugs spanning a few categories, so eval questions later
# can cover different drug classes rather than all being near-duplicates.
DRUG_LIST = [
    # Common OTC pain / fever
    "ibuprofen", "acetaminophen", "aspirin", "naproxen",
    # Antibiotics
    "amoxicillin", "azithromycin", "ciprofloxacin", "doxycycline",
    "cephalexin",
    # Cardiovascular
    "lisinopril", "atorvastatin", "amlodipine", "metoprolol",
    "losartan", "clopidogrel", "warfarin",
    # Diabetes
    "metformin", "insulin glargine", "glipizide",
    # Mental health
    "sertraline", "fluoxetine", "escitalopram", "bupropion",
    "alprazolam", "trazodone",
    # Respiratory / allergy
    "albuterol", "montelukast", "cetirizine", "loratadine",
    "fluticasone",
    # GI
    "omeprazole", "pantoprazole", "ondansetron",
    # Thyroid / hormonal
    "levothyroxine",
    # Pain / other
    "gabapentin", "tramadol", "prednisone",
    # Statins / misc chronic
    "simvastatin", "furosemide", "hydrochlorothiazide",
]
