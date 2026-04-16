# CDSCO-IndiaAI Health Innovation Acceleration Hackathon

End-to-end AI pipeline for streamlining CDSCO's regulatory review workflow.

```
                ┌─────────────────────────┐
  Any input ───▶│  pipeline.py (root)     │
  PDF / DOCX    │  - interactive menu     │
  XLSX / CSV    │  - orchestrates modules │
  JSON / HTML   │  - chains JSON outputs  │
  scanned img   │  - prompts between      │
  raw text      │    each module          │
                └────────────┬────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ Module 1 │──▶│ Module 2 │──▶│ Module 3 │ ─▶ ...
        │  Anon.   │   │ Summary  │   │ Complete │
        └──────────┘   └──────────┘   └──────────┘
         (working)       (planned)      (planned)
```

## Quickstart (30 seconds, zero installs)

```bash
cd Hackathon
python pipeline.py
```

Pick option **10 (Paste raw text)**, paste something with names/IDs,
type `END` on its own line, pick mode **1**, and you'll see every
identifier detected and replaced plus a JSON artifact in `Module1/outputs/`.

## Full install (for PDF / image / DOCX / Excel / free-text NER)

```bash
cd Module1
pip install -r requirements.txt
python -m spacy download en_core_web_lg
```

Plus these system binaries for OCR:

- **Poppler** — required for scanned PDF → image conversion
  - Linux: `sudo apt install poppler-utils`
  - macOS: `brew install poppler`
  - Windows: https://github.com/oschwartz10612/poppler-windows/releases

OCR itself is done by EasyOCR (default) or PaddleOCR — both pip-installable,
no system binary. Tesseract is **not** used.

## Running

### Interactive pipeline (binary choice)
```bash
python pipeline.py
```

You will be asked to pick one of two processes:

1. **De-identification** — identifiers are replaced with asterisks
   (`**********`). Format is preserved where useful (email domain stays,
   PAN suffix stays) but **no vault entry is created**, so the output is
   not traceable back to the Data Principal. Aligned with DPDP Act 2023
   §2(b). Use this for internal clinician / reviewer access.

2. **Irreversible anonymisation** — identifiers are replaced with
   category labels (`[PERSON]`, `[PHONE]`, `INDIA`, `YYYY-XX-XX`). The
   original values are irrecoverable and the text shape is destroyed.
   Use this for anything that leaves the organisation (research data
   release, public datasets, third-party sharing).

See `Module1/COMPLIANCE.md` for the full framework alignment and the list
of things the module deliberately does **not** do.

### Direct file (non-interactive)
```bash
python pipeline.py path/to/file.pdf                    # auto-detect type
python pipeline.py path/to/file.pdf --mode mask        # de-identification
python pipeline.py path/to/file.pdf --mode generalise  # irreversible anon.
python pipeline.py "raw text here" --inline --mode mask
python pipeline.py file.pdf --auto                     # no prompts
```

Advanced modes still available via `--mode`:
```bash
python pipeline.py file.pdf --mode pseudonymise   # reversible HMAC tokens
python pipeline.py file.pdf --mode two_step       # link-critical fields kept reversible
```

### REST API
```bash
cd Module1
uvicorn api:app --reload --port 8000
# then open http://localhost:8000/docs
```

Endpoints: `POST /anonymise/text`, `POST /anonymise/batch`, `POST /anonymise/file`, `POST /vault/reveal`, `GET /health`.

## Validation & evaluation (for the hackathon project report)

Every hackathon submission needs numbers. Run the built-in evaluator
against synthetic Indian CDSCO-style data — **no downloads required**.

```bash
cd Module1

# Quick: 200 synthetic samples, default seed
python evaluate.py

# Larger sample
python evaluate.py --n 1000 --seed 7

# Save full report for the PDF submission
python evaluate.py --n 500 --save report.json

# Evaluate against your own labelled JSONL file
python evaluate.py --dataset my_test_set.jsonl
```

You'll get entity-level Precision / Recall / F1 per type plus micro/macro
averages — the exact shape the FUNSD-style rubric expects:

```
  Entity                TP    FP    FN      Prec    Recall        F1
  AADHAAR              198     0     2     1.000     0.990     0.995
  CDSCO_FILE           200     0     0     1.000     1.000     1.000
  DATE_TIME            198     0     2     1.000     0.990     0.995
  DRUG_ID              200     0     0     1.000     1.000     1.000
  EMAIL_ADDRESS        200     0     0     1.000     1.000     1.000
  IN_PHONE             200     0     0     1.000     1.000     1.000
  PAN                  200     0     0     1.000     1.000     1.000
  PERSON               182     6    18     0.968     0.910     0.938
  ...
  MICRO                                     0.995     0.988     0.992
  MACRO                                     0.995     0.987     0.991
```

To inspect the synthetic data generator itself:

```bash
python synthetic.py          # prints 3 sample narratives with spans
```

## Custom test-set format (JSONL)

One JSON object per line:

```json
{"text": "Rajesh Kumar (Aadhaar 1234 5678 9012) admitted.", "spans": [
  {"start": 0,  "end": 12, "entity": "PERSON"},
  {"start": 22, "end": 36, "entity": "AADHAAR"}
]}
```

## Repo layout

```
Hackathon/
├── pipeline.py                  ← interactive orchestrator (START HERE)
├── README.md                    ← this file
├── Module1/
│   ├── ingestion.py             ← format dispatch + OCR (all lazy imports)
│   ├── detection.py             ← regex + optional Presidio NER, with
│   │                              preprocessing for PDF layout artifacts
│   ├── anonymizer.py            ← two-step pseudonymise + generalise,
│   │                              plus anonymise_batch() for bulk jobs
│   ├── vault.py                 ← encrypted SQLite token vault
│   ├── metrics.py               ← k-anonymity / l-diversity / t-closeness
│   ├── synthetic.py             ← Indian CDSCO-style data generator
│   ├── evaluate.py              ← P/R/F1 detection harness
│   ├── module1.py               ← orchestrator + stable JSON schema
│   ├── api.py                   ← FastAPI service (text/batch/file)
│   ├── COMPLIANCE.md            ← DPDP/NDHM/ICMR/CDSCO alignment notes
│   ├── requirements.txt         ← full deps
│   ├── requirements-minimal.txt ← zero-install guidance
│   └── outputs/                 ← JSON artifacts (auto-created)
└── Module2/                     ← (empty, planned)
```

## What was fixed in the last round

- **Broken imports in `api.py`** — absolute `Hackathon.Module1.X` paths
  rewritten to relative imports.
- **`api.py` file endpoint passed a dict to `anonymise()`** — fixed to
  extract `ingested["text"]` first.
- **"K A T U R E" single-letter-name artifact** (seen when testing on a
  real resume) — added `_collapse_spaced_letters()` preprocessing in
  `detection.py` so letter-spaced headings get rejoined before NER.
- **Sequential replacement was building a 150k-char list for big docs** —
  switched to slice-based reverse build in `anonymizer.py`.
- **Added `anonymise_batch(texts, parallel=True)`** — process-pool
  parallelism for bulk workloads.
- **Added `/anonymise/batch` API endpoint**.
- **Added `synthetic.py`** — Faker-free Indian CDSCO-style data generator
  with ground-truth spans.
- **Added `evaluate.py`** — strict entity-level P/R/F1 scoring, runs on
  synthetic data or custom JSONL.

## Graceful degradation

- No pandas → still works, just loses k-anonymity metrics.
- No Presidio/spaCy → still works via regex; loses free-text PERSON/LOCATION.
- No Tesseract/Poppler → works for digital PDFs + all text formats;
  scanned documents fail with a friendly install hint.
- Missing python-docx/openpyxl → other formats still work.

## Module 1 → Module 2 contract

```json
{
  "module": "module1_anonymisation",
  "version": "0.1",
  "timestamp": "...",
  "input":  { "source", "source_type", "is_scanned", "metadata" },
  "output": {
    "anonymised_text", "mode", "num_entities_detected",
    "entities_by_type", "spans", "structured_anonymised", "vault_size"
  },
  "compliance": { "two_step_applied", "k_anonymity", "quasi_identifiers" }
}
```

Later modules read only this JSON.
