"""
Project-wide configuration.

Keeping this in one place means every script (download, parse, etc.)
reads the same drug list and the same paths — no magic strings scattered
around the codebase.
"""

from pathlib import Path
import os

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
#
# Phase 10: OLLAMA_BASE_URL is now overridable via env var. Running
# locally (no Docker), it defaults to localhost as before. Running
# inside the api container (Phase 10's docker-compose.yml), it's set
# to http://host.docker.internal:11434 instead, since "localhost"
# inside a container means the container itself, not your host
# machine where Ollama actually runs.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
GENERATION_MODEL = "qwen2.5:7b"

# --- Frontend (Phase 9) --------------------------------------------------
# Where the Streamlit app finds the FastAPI backend from Phase 8.
# Same env-var pattern as above — inside the frontend container,
# docker-compose.yml sets this to http://api:8000 (Docker's internal
# DNS resolves the "api" service name automatically).
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

# --- Database --------------------------------------------------------
# Same env-var pattern again. Running locally, defaults match
# docker-compose.yml's exposed port so nothing changes from before.
# Inside the api container, DB_HOST is set to "db" (the service name)
# since "localhost" would otherwise mean the api container itself.
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", "medical_rag"),
    "user": os.environ.get("DB_USER", "raguser"),
    "password": os.environ.get("DB_PASSWORD", "ragpassword"),
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
