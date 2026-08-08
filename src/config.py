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
