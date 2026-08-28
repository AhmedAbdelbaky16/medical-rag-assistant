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
#OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
#GENERATION_MODEL = "qwen2.5:7b"

# Phase 11: switched from local Ollama to DeepSeek's hosted API
# (OpenAI-compatible). Ollama needed more RAM/CPU than the VPS has;
# DeepSeek is cheap enough for this project's volume that hosting
# our own model isn't worth the resource cost.
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
GENERATION_MODEL = os.environ.get("GENERATION_MODEL", "deepseek-v4-flash")





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
# ~500 well-known drugs spanning a few categories, so eval questions later
# can cover different drug classes rather than all being near-duplicates.
DRUG_LIST = [
    # --- Original core set ---
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

    # --- Expanded set (Phase 11) ---
    # NSAIDs / additional pain
    "diclofenac", "meloxicam", "celecoxib", "indomethacin", "ketorolac",
    "piroxicam", "nabumetone", "etodolac", "sulindac", "tolmetin",
    "capsaicin",

    # Opioids
    "hydrocodone", "oxycodone", "morphine", "codeine", "fentanyl",
    "hydromorphone", "methadone", "buprenorphine", "tapentadol",
    "meperidine",

    # Antibiotics (extended)
    "penicillin", "ampicillin", "clindamycin", "erythromycin",
    "clarithromycin", "levofloxacin", "moxifloxacin", "ofloxacin",
    "trimethoprim-sulfamethoxazole", "nitrofurantoin", "metronidazole",
    "vancomycin", "linezolid", "tetracycline", "minocycline",
    "cefdinir", "cefuroxime", "ceftriaxone", "cefaclor", "meropenem",
    "piperacillin", "gentamicin", "tobramycin", "rifampin",
    "isoniazid", "ethambutol", "pyrazinamide", "dapsone",
    "fosfomycin", "daptomycin", "amikacin", "streptomycin",
    "kanamycin", "telavancin", "oritavancin", "dalbavancin",
    "tedizolid", "eravacycline", "omadacycline", "colistin",
    "polymyxin b", "chloramphenicol",

    # Antivirals
    "acyclovir", "valacyclovir", "famciclovir", "oseltamivir",
    "ribavirin", "entecavir", "tenofovir", "lamivudine", "zidovudine",
    "efavirenz", "sofosbuvir", "remdesivir", "ritonavir", "lopinavir",
    "baloxavir", "letermovir", "maribavir", "ganciclovir",
    "valganciclovir", "foscarnet", "cidofovir",

    # Antifungals
    "fluconazole", "itraconazole", "terbinafine", "nystatin",
    "clotrimazole", "ketoconazole", "voriconazole", "griseofulvin",
    "amphotericin b", "micafungin", "caspofungin", "posaconazole",
    "isavuconazole",

    # Cardiovascular (extended)
    "enalapril", "ramipril", "captopril", "benazepril", "valsartan",
    "olmesartan", "irbesartan", "candesartan", "telmisartan",
    "carvedilol", "atenolol", "propranolol", "bisoprolol",
    "labetalol", "nebivolol", "diltiazem", "verapamil", "nifedipine",
    "felodipine", "digoxin", "isosorbide mononitrate",
    "isosorbide dinitrate", "nitroglycerin", "hydralazine",
    "spironolactone", "eplerenone", "torsemide", "bumetanide",
    "chlorthalidone", "indapamide", "amiodarone", "sotalol",
    "flecainide", "propafenone", "dofetilide", "apixaban",
    "rivaroxaban", "dabigatran", "edoxaban", "heparin", "enoxaparin",
    "ticagrelor", "prasugrel", "dipyridamole", "cilostazol",
    "rosuvastatin", "pravastatin", "lovastatin", "fluvastatin",
    "pitavastatin", "ezetimibe", "fenofibrate", "gemfibrozil",
    "niacin", "colesevelam", "evolocumab", "alirocumab",
    "clonidine", "methyldopa", "doxazosin", "terazosin", "prazosin",
    "fondaparinux", "ranolazine", "ivabradine", "macitentan",
    "bosentan", "ambrisentan", "riociguat", "treprostinil",
    "epoprostenol", "iloprost", "nicardipine", "clevidipine",
    "milrinone", "dobutamine", "dopamine", "norepinephrine",
    "vasopressin", "esmolol",

    # Diabetes (extended)
    "glyburide", "glimepiride", "pioglitazone", "rosiglitazone",
    "sitagliptin", "saxagliptin", "linagliptin", "alogliptin",
    "empagliflozin", "canagliflozin", "dapagliflozin", "liraglutide",
    "semaglutide", "dulaglutide", "exenatide", "insulin lispro",
    "insulin aspart", "insulin detemir", "insulin degludec",
    "insulin nph", "acarbose", "repaglinide", "nateglinide",
    "pramlintide", "miglitol", "bromocriptine", "tirzepatide",

    # Mental health (extended)
    "paroxetine", "citalopram", "venlafaxine", "duloxetine",
    "desvenlafaxine", "mirtazapine", "amitriptyline", "nortriptyline",
    "imipramine", "doxepin", "clomipramine", "buspirone", "lorazepam",
    "diazepam", "clonazepam", "temazepam", "zolpidem", "eszopiclone",
    "zaleplon", "quetiapine", "risperidone", "olanzapine",
    "aripiprazole", "ziprasidone", "clozapine", "paliperidone",
    "lurasidone", "haloperidol", "chlorpromazine", "lithium",
    "valproic acid", "lamotrigine", "carbamazepine", "topiramate",
    "methylphenidate", "dextroamphetamine", "atomoxetine",
    "guanfacine", "disulfiram", "naltrexone", "naloxone",
    "varenicline", "fluvoxamine", "asenapine", "iloperidone",
    "pimavanserin", "modafinil", "armodafinil", "vortioxetine",
    "vilazodone", "brexpiprazole", "cariprazine",

    # Respiratory / allergy (extended)
    "salmeterol", "formoterol", "tiotropium", "ipratropium",
    "budesonide", "mometasone", "beclomethasone", "ciclesonide",
    "theophylline", "zafirlukast", "roflumilast", "benzonatate",
    "guaifenesin", "dextromethorphan", "diphenhydramine",
    "fexofenadine", "desloratadine", "hydroxyzine", "azelastine",
    "oxymetazoline", "pseudoephedrine", "phenylephrine",
    "chlorpheniramine", "brompheniramine", "clemastine",
    "dimenhydrinate", "terbutaline", "cromolyn", "pirbuterol",
    "levalbuterol", "umeclidinium", "glycopyrrolate", "indacaterol",
    "olodaterol", "revefenacin", "arformoterol", "aclidinium",
    "acetylcysteine", "dornase alfa",

    # GI (extended)
    "esomeprazole", "lansoprazole", "rabeprazole", "famotidine",
    "cimetidine", "sucralfate", "misoprostol", "bismuth subsalicylate",
    "loperamide", "docusate", "polyethylene glycol", "senna",
    "bisacodyl", "metoclopramide", "promethazine", "dicyclomine",
    "hyoscyamine", "mesalamine", "sulfasalazine", "infliximab",
    "adalimumab", "lactulose", "rifaximin", "ursodiol",
    "prochlorperazine", "meclizine", "scopolamine", "alosetron",
    "lubiprostone", "linaclotide", "plecanatide", "prucalopride",
    "vedolizumab", "certolizumab", "natalizumab",

    # Thyroid / hormonal / urology
    "liothyronine", "methimazole", "propylthiouracil",
    "medroxyprogesterone", "norethindrone", "estradiol",
    "conjugated estrogens", "levonorgestrel", "progesterone",
    "testosterone", "finasteride", "dutasteride", "tamsulosin",
    "sildenafil", "tadalafil", "vardenafil", "clomiphene",
    "raloxifene", "leuprolide", "oxybutynin", "tolterodine",
    "mirabegron", "solifenacin",

    # Bone / rheumatology / oncology
    "alendronate", "risedronate", "ibandronate", "zoledronic acid",
    "calcitonin", "denosumab", "methotrexate", "hydroxychloroquine",
    "leflunomide", "allopurinol", "febuxostat", "colchicine",
    "prednisolone", "dexamethasone", "hydrocortisone", "triamcinolone",
    "methylprednisolone", "tamoxifen", "letrozole", "anastrozole",
    "imatinib", "cisplatin", "carboplatin", "paclitaxel",
    "doxorubicin", "cyclophosphamide", "fluorouracil", "rituximab",
    "trastuzumab", "bevacizumab", "pembrolizumab", "nivolumab",
    "etanercept", "tocilizumab", "ustekinumab", "secukinumab",
    "filgrastim", "epoetin alfa", "darbepoetin alfa",

    # Neurology
    "phenytoin", "levetiracetam", "oxcarbazepine", "pregabalin",
    "sumatriptan", "rizatriptan", "donepezil", "memantine",
    "rivastigmine", "galantamine", "ropinirole", "pramipexole",
    "levodopa", "amantadine", "baclofen", "tizanidine",
    "cyclobenzaprine", "methocarbamol", "lacosamide", "zonisamide",
    "tiagabine", "vigabatrin", "edaravone", "riluzole",
    "tetrabenazine", "deutetrabenazine", "istradefylline",

    # Dermatology / ophthalmology / ENT
    "tretinoin", "adapalene", "benzoyl peroxide", "mupirocin",
    "permethrin", "isotretinoin", "minoxidil", "clobetasol",
    "betamethasone", "calcipotriene", "pimecrolimus", "tacrolimus",
    "crisaborole", "dupilumab", "latanoprost", "timolol",
    "brimonidine", "dorzolamide", "cyclosporine", "silver sulfadiazine",
    "bacitracin",

    # Anesthesia / critical care
    "lidocaine", "bupivacaine", "propofol", "ketamine", "midazolam",
    "etomidate", "succinylcholine", "rocuronium", "flumazenil",

    # Vitamins / electrolytes / supplements
    "vitamin d", "vitamin b12", "folic acid", "ferrous sulfate",
    "calcium carbonate", "multivitamin", "melatonin", "fish oil",
    "potassium chloride", "magnesium oxide", "zinc", "vitamin c",
    "biotin", "vitamin e", "vitamin a", "vitamin k",
    "sodium bicarbonate", "potassium citrate", "magnesium sulfate",
    "calcium gluconate", "ferrous gluconate", "sodium chloride",

    # Misc
    "epinephrine",
]

# --- Brand name -> generic name mapping (Phase 11) ------------------------
# Real visitors search brand names far more than generics. This maps
# common brand names to the generic name as it appears in DRUG_LIST, so
# "Advil" correctly filters to the ibuprofen entry instead of falling
# back to general NSAID-class information. Not exhaustive - covers the
# most commonly-searched consumer brands; easy to extend over time.
BRAND_TO_GENERIC = {
    "advil": "ibuprofen", "motrin": "ibuprofen",
    "tylenol": "acetaminophen",
    "aleve": "naproxen",
    "zoloft": "sertraline",
    "prozac": "fluoxetine",
    "lexapro": "escitalopram",
    "celexa": "citalopram",
    "paxil": "paroxetine",
    "wellbutrin": "bupropion",
    "cymbalta": "duloxetine",
    "effexor": "venlafaxine",
    "xanax": "alprazolam",
    "valium": "diazepam",
    "ativan": "lorazepam",
    "klonopin": "clonazepam",
    "ambien": "zolpidem",
    "lipitor": "atorvastatin",
    "crestor": "rosuvastatin",
    "zocor": "simvastatin",
    "glucophage": "metformin",
    "synthroid": "levothyroxine",
    "nexium": "esomeprazole",
    "prilosec": "omeprazole",
    "benadryl": "diphenhydramine",
    "claritin": "loratadine",
    "zyrtec": "cetirizine",
    "flonase": "fluticasone",
    "ventolin": "albuterol", "proair": "albuterol",
    "singulair": "montelukast",
    "lasix": "furosemide",
    "norvasc": "amlodipine",
    "zestril": "lisinopril", "prinivil": "lisinopril",
    "coumadin": "warfarin",
    "plavix": "clopidogrel",
    "amoxil": "amoxicillin",
    "zithromax": "azithromycin",
    "cipro": "ciprofloxacin",
    "neurontin": "gabapentin",
    "abilify": "aripiprazole",
    "seroquel": "quetiapine",
    "risperdal": "risperidone",
    "ritalin": "methylphenidate",
    "viagra": "sildenafil",
    "cialis": "tadalafil",
    "ozempic": "semaglutide",
    "trulicity": "dulaglutide",
    "jardiance": "empagliflozin",
}