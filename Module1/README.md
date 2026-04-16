# RegLens AI
 
**AI-Powered Regulatory Intelligence Platform for CDSCO**
 
Built for the **CDSCO-IndiaAI Health Innovation Acceleration Hackathon** - an end-to-end platform that streamlines regulatory document review using AI/ML across five specialized modules.
 
---
 
## Modules
 
| # | Module | What it does |
|---|--------|-------------|
| 1 | **PII/PHI Anonymisation** | Detects and redacts Aadhaar, PAN, names, phone numbers, addresses from regulatory documents using hybrid NLP (spaCy + Presidio) + regex. Supports reversible (token vault) and irreversible modes. |
| 2 | **Document Summarisation** | Extracts key points from lengthy CDSCO filings using offline extractive NLP (sumy). Supports text, PDF, DOCX, and audio files (Vosk speech-to-text). |
| 3 | **Completeness & Comparison** | Validates mandatory fields in SAE/GCP submissions and highlights field-level changes between document versions using semantic + structural diffing. |
| 4 | **SAE Classification** | Classifies Serious Adverse Event reports by severity (death/disability/hospitalisation/other) using XGBoost. Includes duplicate detection (MinHash + sentence-transformers) and priority scoring. |
| 5 | **Inspection Report Generator** | Parses raw field notes and unstructured inspection data into structured PDF/DOCX reports with severity-classified observations. |
 
---
 
## Architecture
 
```
                        http://localhost:3000
                    +---------------------------+
                    |   React + Vite Frontend   |
                    |   TypeScript + Tailwind   |
                    +------+--------+-----------+
                           |        |
              Vite proxy   |        |  Vite proxy
              /api/*       |        |  /api/m3/*
                           v        v
              +-----------+   +----------+
              | Port 8000 |   | Port 8003|
              | FastAPI   |   | FastAPI  |
              |           |   |          |
              | /       M1|   | Module 3 |
              | /m2     M2|   | Complete |
              | /m4     M4|   | Compare  |
              | /m5     M5|   |          |
              +-----------+   +----------+
```
 
All five modules are served from just **two backend processes**:
- **Port 8000** - Unified FastAPI server (M1 anonymisation + M2 summarisation + M4 classification + M5 inspection)
- **Port 8003** - Separate FastAPI server (M3 completeness & comparison)
 
---
 
## Tech Stack
 
| Layer | Technologies |
|-------|-------------|
| **Frontend** | React 19, TypeScript, Vite 6, Tailwind CSS 4, Lucide Icons, Motion |
| **Backend** | FastAPI, Flask (M5), Uvicorn, Pydantic |
| **NLP/ML** | spaCy, Presidio Analyzer, sentence-transformers, XGBoost, LightGBM, SHAP |
| **OCR** | EasyOCR, PyMuPDF |
| **Speech** | Vosk (offline, en-IN model) |
| **PDF/Doc** | pdfplumber, pdfminer, pypdf, python-docx, fpdf2, reportlab |
| **Data** | Pandas, NumPy, scikit-learn, NLTK, sumy |
| **Security** | cryptography (AES-256 vault), SQLAlchemy + aiosqlite |
 
---
 
## Prerequisites
 
- **Python 3.10+**
- **Node.js 18+**
- **pip** (comes with Python)
- **Windows 10/11** (start.bat is Windows-native)
 
No other system binaries required - OCR, speech recognition, and PDF processing are all pip-installable.
 
---
 
## Quick Start
 
```
cd Hackathon
start.bat
```
 
That's it. The script will:
 
1. Create a Python virtual environment
2. Install all Python dependencies (~100 packages)
3. Download spaCy language model and NLTK data
4. Download Vosk speech model (~36 MB) for audio transcription
5. Install frontend npm packages
6. Train the Module 4 classifier (if first run)
7. Launch 3 server windows (backend, Module 3, frontend)
8. Open http://localhost:3000 in your browser
 
First run takes 5-10 minutes. Subsequent runs take ~15 seconds.
 
### Environment Variables (Optional)
 
Copy `Frontend/.env.example` to `Frontend/.env` and add your Gemini API key if you want AI-assisted features:
 
```
GEMINI_API_KEY=your_key_here
```
 
The platform works fully without it.
 
---
 
## Project Structure
 
```
Hackathon/
+-- start.bat                    # One-click setup + launch
+-- clean.bat                    # Clean for GitHub sharing
+-- requirements.txt             # Unified Python dependencies
+-- download_vosk.py             # Vosk model downloader
+-- pipeline.py                  # CLI orchestrator (interactive menu)
|
+-- Frontend/                    # React + Vite + TypeScript
|   +-- src/
|   |   +-- App.tsx              # Routing
|   |   +-- pages/
|   |   |   +-- Dashboard.tsx    # Module selection hub
|   |   |   +-- ModulePage.tsx   # Generic module UI (M2-M5)
|   |   |   +-- SAEPage.tsx      # Module 1 dedicated UI
|   |   +-- components/          # Shared UI components
|   |   +-- services/api.ts      # API client for all modules
|   |   +-- types.ts             # TypeScript interfaces
|   +-- package.json
|   +-- vite.config.ts           # Proxy config for backend routing
|   +-- .env.example
|
+-- Module1/                     # Anonymisation
|   +-- api.py                   # FastAPI (unified server, mounts M2/M4/M5)
|   +-- anonymizer.py            # Core anonymisation engine
|   +-- detection.py             # PII/PHI entity detection
|   +-- ingestion.py             # Multi-format file parser + OCR
|   +-- vault.py                 # Encrypted SQLite token vault
|   +-- sae_engine.py            # SAE-specific anonymisation
|   +-- metrics.py               # k-anonymity / l-diversity / t-closeness
|   +-- synthetic.py             # Indian CDSCO-style data generator
|   +-- evaluate.py              # P/R/F1 evaluation harness
|   +-- COMPLIANCE.md            # DPDP Act 2023 alignment
|
+-- Module_2/cdsco_data_summarisation/
|   +-- api.py                   # FastAPI summarisation service
|   +-- core/                    # Summarisation logic (sumy-based)
|   +-- config/                  # Settings
|   +-- utils/                   # File handlers
|
+-- Module3/backend/
|   +-- app.py                   # FastAPI (port 8003)
|   +-- routers/                 # Completeness, comparison, checklist, reports
|   +-- services/                # Business logic + ML
|   +-- data/checklists/         # GCP & SAE regulatory checklists
|
+-- Module4/
|   +-- api.py                   # FastAPI classification service
|   +-- pipeline.py              # Training & inference pipeline
|   +-- config.yaml              # ML configuration
|   +-- src/                     # Feature engineering
|   +-- data/raw/                # Training data (100+ SAE records)
|   +-- models/                  # Trained XGBoost classifier
|
+-- Module5/
    +-- app.py                   # Flask inspection report service
    +-- utils/                   # Extraction, parsing, report generation
    +-- templates/               # Jinja2 HTML report templates
```
 
---
 
## API Endpoints
 
### Port 8000 - Unified Backend
 
**Module 1 - Anonymisation**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check + OCR engine info |
| POST | `/anonymise/text` | Anonymise raw text |
| POST | `/anonymise/file` | Anonymise uploaded file (PDF/DOCX/image) |
| POST | `/anonymise/files` | Batch file anonymisation |
| POST | `/anonymise/folder` | Batch with scan-detection summary |
| POST | `/vault/reveal` | Re-identify a pseudonymised token |
| POST | `/scan-detect` | Classify files as scanned vs digital |
 
**SAE Engine (Module 1)**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sae/anonymize` | Irreversible/reversible SAE anonymisation |
| POST | `/sae/file` | Upload file for SAE anonymisation |
| POST | `/sae/traceback` | Reconstruct original from tokens |
| POST | `/sae/check-duplicate` | Duplicate file detection (SHA256) |
 
**Module 2 - Summarisation** (mounted at `/m2`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/m2/summarise/text` | Summarise text input |
| POST | `/m2/summarise/file` | Summarise uploaded file (incl. audio) |
 
**Module 4 - Classification** (mounted at `/m4`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/m4/classify` | Classify single SAE record |
| POST | `/m4/classify/pdf` | Classify uploaded PDF |
| POST | `/m4/classify/batch` | Batch classification |
| POST | `/m4/deduplicate` | Duplicate detection (MinHash + semantic) |
| POST | `/m4/prioritise` | Priority scoring for review |
| POST | `/m4/pipeline` | Full classify + deduplicate + prioritise |
 
**Module 5 - Inspection** (mounted at `/m5`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/m5/upload` | Upload inspection document |
| POST | `/m5/inspect-text` | Generate report from pasted text |
| GET | `/m5/reports` | List generated reports |
| GET | `/m5/reports/{filename}` | Download report (PDF/DOCX) |
 
### Port 8003 - Module 3
 
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/completeness/completeness/sae` | SAE completeness assessment |
| POST | `/api/v1/comparison/comparison/structured` | Structured document comparison |
 
Swagger UI available at http://localhost:8000/docs and http://localhost:8003/docs
 
---
 
## Supported File Formats
 
**Input:** PDF, DOCX, DOC, XLSX, XLS, CSV, JSON, HTML, TXT, PNG, JPG, JPEG, TIFF, MP3, WAV, WebM
 
**Output:** TXT, CSV, JSON, PDF, DOCX
 
Scanned documents and images are processed via EasyOCR. Audio files use Vosk offline speech-to-text (en-IN model).
 
---
 
## Evaluation
 
Module 1 includes a built-in evaluation harness with synthetic Indian CDSCO-style data:
 
```bash
cd Module1
python evaluate.py              # 200 synthetic samples
python evaluate.py --n 1000     # larger sample
python evaluate.py --save report.json
```
 
Sample results:
```
Entity               Prec    Recall    F1
AADHAAR              1.000   0.990     0.995
PAN                  1.000   1.000     1.000
EMAIL_ADDRESS        1.000   1.000     1.000
IN_PHONE             1.000   1.000     1.000
PERSON               0.968   0.910     0.938
MICRO                0.995   0.988     0.992
```
 
---
 
## Regulatory Compliance
 
Module 1 is designed to align with:
- **DPDP Act 2023** (Digital Personal Data Protection) - Section 2(b) de-identification
- **NDHM** (National Digital Health Mission) data standards
- **ICMR** (Indian Council of Medical Research) bioethics guidelines
- **CDSCO** regulatory document requirements
 
See [Module1/COMPLIANCE.md](Module1/COMPLIANCE.md) for the full compliance framework.
 
---
 
## Clean for Sharing
 
Before uploading to GitHub or sharing the project:
 
```
clean.bat
```
 
This removes: `venv`, `node_modules`, `__pycache__`, generated reports, uploads, logs, Vosk model (~36 MB), vault databases, and temp files.
 
It **keeps**: all source code, trained ML models, training data, and configuration.
 
After cloning, just run `start.bat` to restore everything.
 
---
 
## Graceful Degradation
 
The platform is designed to work even when optional components are unavailable:
 
| Missing Component | Impact |
|-------------------|--------|
| Vosk model | Audio summarisation unavailable; text/file processing works |
| PyAudio | Live-mic recording unavailable; file upload works |
| Gemini API key | AI-assisted features disabled; all core modules work |
| pdfkit/wkhtmltopdf | Module 3 PDF export falls back to HTML |
| spaCy model | Regex-only PII detection (loses free-text PERSON/LOCATION) |
 
---
 
## License
 
This project was developed for the CDSCO-IndiaAI Health Innovation Acceleration Hackathon.
