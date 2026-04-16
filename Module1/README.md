# Module 1 — AI-Powered Anonymisation Tool

CDSCO-IndiaAI Health Innovation Acceleration Hackathon.

This module detects PII / PHI in regulatory documents and offers two
user-facing options: **de-identification** (asterisk masking, non-
traceable) and **irreversible anonymisation** (category-label
generalisation). Advanced modes (HMAC pseudonymisation, two-step) are
available via the API and `--mode` flag. Built to align with the DPDP
Act 2023, NDHM HDM Policy, ICMR ethical guidelines, and CDSCO standards
— see `COMPLIANCE.md` for what that does and does not mean.

## Pipeline

```
File (PDF / DOCX / image / CSV / JSON / TXT)
        │
        ▼
   ingestion.py        ← OpenCV preprocessing + EasyOCR / PaddleOCR
        │
        ▼
   detection.py        ← Hybrid: Presidio NER + Indian regex patterns
        │                (Aadhaar, PAN, IN phone, MRN, IND-, CDSCO/, IFSC,
        │                 passport, plus PERSON/LOCATION/DATE/etc.)
        ▼
   anonymizer.py       ← Two-step:
        │                 Step 1 — HMAC-SHA256 pseudonymisation
        │                 Step 2 — generalisation / suppression
        ▼
   vault.py            ← Encrypted SQLite token vault (Fernet)
        │
        ▼
   api.py              ← FastAPI: /anonymise/text, /anonymise/file, /vault/reveal
        │
        ▼
   metrics.py          ← k-anonymity, l-diversity, t-closeness reporting
```

## Files

| File | Purpose |
|---|---|
| `ingestion.py` | PDF/image/DOCX/JSON ingestion. OpenCV denoise + Otsu + deskew before Tesseract. PDF text-layer fast path with OCR fallback for scans. |
| `detection.py` | Builds a Presidio analyzer with English NER plus custom Indian regex recognisers. Returns `Span` objects with overlap resolution. |
| `anonymizer.py` | Three modes — `pseudonymise`, `generalise`, `two_step` (default). HMAC-based deterministic tokens; coarsens dates, locations, etc. |
| `vault.py` | Encrypted token store. Fernet over SQLite. Key loaded from `ANON_VAULT_KEY` env var or auto-generated `vault.key` file. |
| `metrics.py` | Pandas-based k-anonymity / l-diversity / t-closeness for structured datasets — these are the exact metrics in the hackathon rubric. |
| `api.py` | FastAPI service exposing the pipeline over HTTP. |
| `requirements.txt` | Python dependencies. |

## Setup

```bash
# 1. Python deps
pip install -r requirements.txt
python -m spacy download en_core_web_lg

# 2. System deps
#    - Tesseract OCR  (Windows: install from UB-Mannheim build)
#    - Poppler        (needed by pdf2image; Windows: download poppler-windows)

# 3. Set secrets (optional but recommended)
set ANON_HMAC_SECRET=your-rotating-hmac-key
set ANON_VAULT_KEY=base64-fernet-key
```

If Tesseract is not on `PATH`, uncomment and edit the
`pytesseract.pytesseract.tesseract_cmd` line at the top of `ingestion.py`.

## Try it

```bash
# Quick smoke tests
python detection.py
python anonymizer.py
python metrics.py
python vault.py

# Run the API
uvicorn api:app --reload --port 8000

# Then in another terminal
curl -X POST http://localhost:8000/anonymise/text ^
  -H "Content-Type: application/json" ^
  -d "{\"text\": \"Rajesh Kumar, Aadhaar 1234 5678 9012, +91-9876543210\"}"
```

## What maps to which hackathon requirement

| Requirement (problem statement / rubric) | Where it lives |
|---|---|
| Hybrid rule-based + NLP detection | `detection.py` (Presidio NER + regex) |
| Structured **and** unstructured data | `ingestion.py` handles JSON/CSV; `detection.py` works on flattened text |
| Two-step process: pseudonymisation + irreversible anonymisation | `anonymizer.py` `two_step` mode |
| Secure tokens for pseudonymisation | HMAC-SHA256 in `anonymizer.py`, persisted via `vault.py` |
| Compliance with DPDP / NDHM / ICMR / CDSCO | Indian-specific recognisers in `detection.py`, audit-ready vault in `vault.py` |
| Web/API-based tool | `api.py` (FastAPI) |
| k-anonymity / l-diversity / t-closeness benchmarks | `metrics.py` |

## Next steps

1. Add a clinical-domain NER model (e.g. `Bio_ClinicalBERT` or `en_core_med7_lg`) alongside `en_core_web_lg` for higher PHI recall on medical narratives.
2. Evaluate detection on the **i2b2 / n2c2 de-identification** dataset and report entity-level F1.
3. Build a synthetic CDSCO submission generator (Faker + Indian locale) to expand training data for Stage 2.
4. Wire `metrics.py` into a CSV ingestion path so structured anonymisation runs end-to-end.
