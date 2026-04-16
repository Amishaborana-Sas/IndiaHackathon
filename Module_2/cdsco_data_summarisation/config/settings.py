"""
==============================================================================
config/settings.py — Central project configuration
==============================================================================
All tunable constants live here. Other modules import from this file only;
never hard-code paths or parameters elsewhere.
==============================================================================
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent.parent   # project root
CONFIG_DIR  = BASE_DIR / "config"
CORE_DIR    = BASE_DIR / "core"
OUTPUT_DIR  = BASE_DIR / "output"
DATA_DIR    = BASE_DIR / "data"
MODELS_DIR  = BASE_DIR / "models"
LOGS_DIR    = BASE_DIR / "logs"

# Vosk offline speech model directory (user must download and place here)
# Download from: https://alphacephei.com/vosk/models  (vosk-model-en-in-0.5 recommended)
# Auto-detect Vosk model folder (handles vosk_model/ AND vosk-model-en-in-0.5/)
def _find_vosk():
    import os
    from pathlib import Path as _P
    mdir = MODELS_DIR
    # 1. Exact name
    if (_P(mdir) / 'vosk_model' / 'am').exists():
        return _P(mdir) / 'vosk_model'
    # 2. Any vosk-* subfolder that has am/ inside
    for d in _P(mdir).iterdir():
        if d.is_dir() and d.name.startswith('vosk') and (d / 'am').exists():
            return d
    return _P(mdir) / 'vosk_model'  # fallback

VOSK_MODEL_PATH = _find_vosk()

# Logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE  = str(LOGS_DIR / "cdsco_tool.log")
LOG_LEVEL = "INFO"   # DEBUG | INFO | WARNING | ERROR

# ---------------------------------------------------------------------------
# Summarisation parameters
# ---------------------------------------------------------------------------
# Number of sentences in auto-generated summary
SUMMARY_SENTENCE_COUNT = 8

# Summarisation algorithm: "lsa" | "lexrank" | "luhn" | "text_rank"
# LSA  → best for structured regulatory/clinical text
# LexRank → graph-based, good for multi-document scenarios
SUMMARISATION_ALGORITHM = "lsa"

# SpaCy language model (must be installed offline)
# python -m spacy download en_core_web_sm
SPACY_MODEL = "en_core_web_sm"

# ---------------------------------------------------------------------------
# Speech-to-Text parameters (Vosk)
# ---------------------------------------------------------------------------
STT_SAMPLE_RATE   = 16000   # Hz — Vosk requires 16 kHz
STT_CHANNELS      = 1       # Mono
STT_CHUNK_SIZE    = 4096    # Bytes per audio chunk
STT_MAX_RECORD_SEC = 420    # Maximum recording duration (seconds)

# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
REPORT_AUTHOR        = "CDSCO Inspection Officer"
REPORT_ORGANISATION  = "Central Drugs Standard Control Organisation"
REPORT_FOOTER_TEXT   = (
    "CONFIDENTIAL - For Official Use Only | "
    "Prepared under CDSCO Schedule M / MDR 2017"
)
# Supported output formats: "pdf" | "docx" | "both"
DEFAULT_REPORT_FORMAT = "both"

# ---------------------------------------------------------------------------
# Input field definitions (used by UI and validators)
# These mirror the fields a CDSCO officer would fill during an inspection.
# ---------------------------------------------------------------------------
INSPECTION_FIELDS = {
    # Section A — Facility identification
    "firm_name":        {"label": "Firm / Manufacturer Name",        "required": True},
    "firm_address":     {"label": "Registered Address",              "required": True},
    "license_no":       {"label": "Drug Licence Number",             "required": True},
    "product_category": {"label": "Product Category",               "required": True,
                         "options": ["Allopathic Drug", "Biologics",
                                     "Medical Device", "Cosmetics",
                                     "Ayush", "Blood Product"]},
    # Section B — Inspection metadata
    "inspection_date":  {"label": "Date of Inspection (DD/MM/YYYY)", "required": True},
    "inspection_type":  {"label": "Inspection Type",                 "required": True,
                         "options": ["Routine", "Complaint-Based",
                                     "Follow-Up", "Pre-Approval",
                                     "Surveillance"]},
    "inspectors":       {"label": "Names of Inspecting Officers",    "required": True},
    # Section C — Data input
    "raw_text":         {"label": "Paste or dictate inspection notes","required": True},
    "observations":     {"label": "Key Observations / Deficiencies", "required": False},
    "capa":             {"label": "CAPA / Recommendations",          "required": False},
    # Section D — Classification (linked to Classification module)
    "deficiency_class": {"label": "Deficiency Classification",       "required": False,
                         "options": ["Critical", "Major", "Minor", "Observation"]},
}