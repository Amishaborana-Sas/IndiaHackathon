"""
RegLens AI — Unified FastAPI service
=====================================
Single HTTP server for all 5 modules of the CDSCO-IndiaAI hackathon platform.

Module 1 — Anonymisation (fully implemented)
Module 2 — Summarisation (stub — plug in your backend logic)
Module 3 — Comparison (stub — plug in your backend logic)
Module 4 — Classification (stub — plug in your backend logic)
Module 5 — Inspection Report (stub — plug in your backend logic)

Endpoints
---------
GET  /health                 -> liveness probe + OCR engine info
POST /anonymise/text         -> anonymise raw text
POST /anonymise/batch        -> anonymise a list of strings
POST /anonymise/file         -> upload a PDF/DOCX/image, get anonymised text
POST /anonymise/files        -> batch upload multiple files
POST /anonymise/folder       -> batch with scan-detection summary
POST /vault/reveal           -> re-identify a token
GET  /vault/info             -> vault location and size
POST /summarise/text         -> summarise text (Module 2)
POST /summarise/file         -> summarise uploaded file (Module 2)
POST /compare/texts          -> compare two texts (Module 3)
POST /compare/files          -> compare two files (Module 3)
POST /classify/text          -> classify text (Module 4)
POST /classify/file          -> classify uploaded file (Module 4)
POST /inspect/text           -> generate inspection report from text (Module 5)
POST /inspect/file           -> generate inspection report from file (Module 5)
"""

from __future__ import annotations

import logging
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Literal

# Add ocr_module to path so we can use the shared OCR engine
_OCR_DIR = str(Path(__file__).resolve().parent.parent / "ocr_module")
if _OCR_DIR not in sys.path:
    sys.path.insert(0, _OCR_DIR)

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from anonymizer import anonymise, anonymise_batch
from ingestion import ingest, ingest_bytes, get_ocr_engine_name, preload_ocr
import ocr_config
from vault import TokenVault

logger = logging.getLogger(__name__)

app = FastAPI(
    title="CDSCO Anonymisation Service",
    description=(
        "AI-powered PII/PHI detection and two-step anonymisation for "
        "regulatory documents. Built for the CDSCO-IndiaAI hackathon.\n\n"
        "Supports images (PNG/JPG), scanned PDFs, DOCX, XLSX, CSV, JSON, "
        "HTML, and plain text. OCR powered by EasyOCR / PaddleOCR."
    ),
    version="0.3.0",
)

# CORS for frontend (localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# A single shared vault for the lifetime of the process.
_vault = TokenVault("vault.db")

# --------------------------------------------------------------------------- #
# Mode aliasing — user-facing names map to internal engine modes              #
# --------------------------------------------------------------------------- #
Mode = Literal[
    "pseudonymise", "generalise", "two_step", "mask",
    "de-identification", "irreversible-anonymisation",
    "reversible-anonymisation",
]

USER_MODE_MAP = {
    "de-identification": "generalise",           # Labels: [PERSON], [PHONE] — identifiers replace PII
    "irreversible-anonymisation": "mask",         # Asterisks: ****** — permanent irrecoverable masking
    "reversible-anonymisation": "pseudonymise",
    # Internal names pass through
    "pseudonymise": "pseudonymise",
    "generalise": "generalise",
    "two_step": "two_step",
    "mask": "mask",
}


def _resolve_mode(mode: str) -> str:
    return USER_MODE_MAP.get(mode, "two_step")


# --------------------------------------------------------------------------- #
# Request / response models                                                   #
# --------------------------------------------------------------------------- #
class TextRequest(BaseModel):
    text: str
    mode: Mode = "two_step"


class BatchRequest(BaseModel):
    texts: list[str]
    mode: Mode = "two_step"
    parallel: bool = False


class AnonymiseResponse(BaseModel):
    anonymised_text: str
    mode: str
    num_entities: int
    entities_by_type: dict[str, int]
    vault_size: int
    processing_time_ms: float = 0.0


class FileAnonymiseResponse(BaseModel):
    """Extended response for file uploads — includes extracted text + timing."""
    filename: str
    source_type: str
    is_scanned: bool
    extracted_text: str
    anonymised_text: str
    mode: str
    num_entities: int
    entities_by_type: dict[str, int]
    vault_size: int
    ocr_engine: str | None
    processing_time_ms: float
    handwritten_regions: int = 0
    total_pages: int = 0
    pages_scanned: int = 0
    pages_skipped: int = 0


class BatchResponse(BaseModel):
    results: list[AnonymiseResponse]
    total_entities: int


class BatchFileResponse(BaseModel):
    file_count: int
    results: list[FileAnonymiseResponse]
    total_time_ms: float


class FolderFileInfo(BaseModel):
    filename: str
    source_type: str
    is_scanned: bool
    handwritten_regions: int
    needs_ocr: bool


class FolderAnalysisResponse(BaseModel):
    file_count: int
    file_summary: list[FolderFileInfo]
    results: list[FileAnonymiseResponse]
    total_time_ms: float


class RevealRequest(BaseModel):
    token: str


# --------------------------------------------------------------------------- #
# Module 2 — Summarisation models                                             #
# --------------------------------------------------------------------------- #
class SummariseTextRequest(BaseModel):
    text: str
    length: str = "detailed"  # "brief" | "detailed"

class SummariseResponse(BaseModel):
    summary: str
    key_points: list[str]
    word_count: int
    processing_time_ms: float


# --------------------------------------------------------------------------- #
# Module 3 — Comparison models                                                #
# --------------------------------------------------------------------------- #
class CompareTextsRequest(BaseModel):
    text_a: str
    text_b: str

class DifferenceItem(BaseModel):
    section: str
    type: str  # "added" | "removed" | "changed"
    detail: str

class CompareResponse(BaseModel):
    differences: list[DifferenceItem]
    similarity_score: float
    missing_fields: list[str]
    processing_time_ms: float


# --------------------------------------------------------------------------- #
# Module 4 — Classification models                                            #
# --------------------------------------------------------------------------- #
class ClassifyTextRequest(BaseModel):
    text: str

class SubCategory(BaseModel):
    name: str
    confidence: float

class ClassifyResponse(BaseModel):
    category: str
    confidence: float
    sub_categories: list[SubCategory]
    processing_time_ms: float


# --------------------------------------------------------------------------- #
# Module 5 — Inspection Report models                                         #
# --------------------------------------------------------------------------- #
class InspectTextRequest(BaseModel):
    text: str

class Finding(BaseModel):
    id: str
    description: str
    severity: str  # "critical" | "major" | "minor" | "observation"
    area: str

class InspectResponse(BaseModel):
    report_text: str
    findings: list[Finding]
    severity_counts: dict[str, int]
    processing_time_ms: float


# --------------------------------------------------------------------------- #
# Endpoints                                                                   #
# --------------------------------------------------------------------------- #
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "ocr_engine": get_ocr_engine_name(),
        "ocr_languages": ocr_config.OCR_LANGUAGES,
        "gpu_enabled": ocr_config.USE_GPU,
    }


# --------------------------------------------------------------------------- #
# Scan Detection — Phase 1: quickly classify files as digital vs scanned      #
# --------------------------------------------------------------------------- #
@app.post("/scan-detect")
async def scan_detect(files: list[UploadFile] = File(...)):
    """
    Phase 1: For each uploaded file, quickly detect if it's a scanned
    document or has digital text. Does NOT run full OCR yet.
    Returns per-file scan info so the frontend can show progress.
    """
    try:
        from ocr_engine import OCREngine, _pdf_extract_digital_text, _detect_mime
    except ImportError:
        raise HTTPException(status_code=500, detail="OCR module not found")

    results = []
    for f in files:
        filename = f.filename or "unknown"
        contents = await f.read()
        mime = _detect_mime(contents, filename)
        ext = Path(filename).suffix.lower()

        info = {
            "filename": filename,
            "size_bytes": len(contents),
            "mime": mime,
            "is_pdf": mime == "application/pdf",
            "is_image": mime.startswith("image/"),
            "is_scanned": False,
            "page_count": 0,
            "digital_pages": 0,
            "scanned_pages": 0,
            "needs_ocr": False,
        }

        if mime == "application/pdf":
            try:
                import fitz
                doc = fitz.open(stream=contents, filetype="pdf")
                page_count = len(doc)
                info["page_count"] = page_count

                digital_texts = [page.get_text() for page in doc]
                doc.close()

                digital_count = 0
                scanned_count = 0
                for text in digital_texts:
                    if len(text.strip()) >= 80:
                        digital_count += 1
                    else:
                        scanned_count += 1

                info["digital_pages"] = digital_count
                info["scanned_pages"] = scanned_count
                info["is_scanned"] = scanned_count > 0
                info["needs_ocr"] = scanned_count > 0
            except Exception as e:
                logger.warning("Scan detect failed for %s: %s", filename, e)
                info["is_scanned"] = True
                info["needs_ocr"] = True
        elif mime.startswith("image/"):
            info["is_scanned"] = True
            info["needs_ocr"] = True
            info["page_count"] = 1
            info["scanned_pages"] = 1
        else:
            # Text/docx/csv - no OCR needed
            info["is_scanned"] = False
            info["needs_ocr"] = False

        results.append(info)

    total = len(results)
    scanned = sum(1 for r in results if r["is_scanned"])
    digital = total - scanned
    total_pages = sum(r["page_count"] for r in results)
    total_scanned_pages = sum(r["scanned_pages"] for r in results)

    return {
        "files": results,
        "summary": {
            "total_files": total,
            "scanned_files": scanned,
            "digital_files": digital,
            "total_pages": total_pages,
            "scanned_pages": total_scanned_pages,
            "digital_pages": total_pages - total_scanned_pages,
        }
    }


@app.post("/anonymise/text", response_model=AnonymiseResponse)
def anonymise_text(req: TextRequest) -> AnonymiseResponse:
    t_start = time.perf_counter()
    internal_mode = _resolve_mode(req.mode)
    result = anonymise(req.text, mode=internal_mode)
    _persist_vault(result.vault)
    elapsed_ms = (time.perf_counter() - t_start) * 1000
    d = result.to_dict()
    return AnonymiseResponse(
        **d,
        processing_time_ms=round(elapsed_ms, 1),
    )


@app.post("/anonymise/batch", response_model=BatchResponse)
def anonymise_batch_endpoint(req: BatchRequest) -> BatchResponse:
    internal_mode = _resolve_mode(req.mode)
    results = anonymise_batch(req.texts, mode=internal_mode, parallel=req.parallel)
    total = 0
    responses: list[AnonymiseResponse] = []
    for r in results:
        _persist_vault(r.vault)
        total += len(r.spans)
        d = r.to_dict()
        responses.append(AnonymiseResponse(**d, processing_time_ms=0.0))
    return BatchResponse(results=responses, total_entities=total)


# Max text length to anonymise in one go (prevents OOM on huge docs)
_MAX_ANON_CHARS = 100_000


def _chunked_anonymise(text: str, mode: str):
    """Anonymise text in chunks to prevent memory issues on large documents."""
    if len(text) <= _MAX_ANON_CHARS:
        return anonymise(text, mode=mode)

    # Split into chunks at paragraph boundaries
    chunks = []
    pos = 0
    while pos < len(text):
        end = min(pos + _MAX_ANON_CHARS, len(text))
        if end < len(text):
            # Find paragraph break near chunk boundary
            break_pos = text.rfind("\n\n", pos + _MAX_ANON_CHARS // 2, end + 2000)
            if break_pos > pos:
                end = break_pos + 2
        chunks.append(text[pos:end])
        pos = end

    logger.info("Anonymising %d chars in %d chunks", len(text), len(chunks))

    # Anonymise each chunk
    all_text_parts = []
    all_spans = []
    vault = {}
    total_offset = 0
    for chunk in chunks:
        r = anonymise(chunk, mode=mode)
        all_text_parts.append(r.anonymised_text)
        vault.update(r.vault)
        for s in r.spans:
            s.start += total_offset
            s.end += total_offset
            all_spans.append(s)
        total_offset += len(chunk)

    # Build combined result
    from anonymizer import AnonymisationResult
    return AnonymisationResult(
        original_text=text,
        anonymised_text="".join(all_text_parts),
        spans=all_spans,
        vault=vault,
        mode=mode,
    )


@app.post("/anonymise/file", response_model=FileAnonymiseResponse)
async def anonymise_file(
    file: UploadFile = File(...),
    mode: Mode = "two_step",
) -> FileAnonymiseResponse:
    t_start = time.perf_counter()
    internal_mode = _resolve_mode(mode)

    filename = file.filename or "unknown"
    contents = await file.read()

    try:
        ingested = ingest_bytes(contents, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {e}")

    extracted_text = ingested["text"]
    result = _chunked_anonymise(extracted_text, mode=internal_mode)
    _persist_vault(result.vault)

    elapsed_ms = (time.perf_counter() - t_start) * 1000

    meta = ingested["metadata"]
    return FileAnonymiseResponse(
        filename=filename,
        source_type=ingested["source_type"],
        is_scanned=ingested["is_scanned"],
        extracted_text=extracted_text,
        anonymised_text=result.anonymised_text,
        mode=internal_mode,
        num_entities=len(result.spans),
        entities_by_type=result.to_dict()["entities_by_type"],
        vault_size=len(result.vault),
        ocr_engine=meta.get("ocr_engine"),
        processing_time_ms=round(elapsed_ms, 1),
        handwritten_regions=meta.get("handwritten_regions", 0),
        total_pages=meta.get("pages", 0),
        pages_scanned=meta.get("pages_scanned", 0),
        pages_skipped=meta.get("pages_skipped", 0),
    )


@app.post("/anonymise/files", response_model=BatchFileResponse)
async def anonymise_files(
    files: list[UploadFile] = File(...),
    mode: Mode = "two_step",
) -> BatchFileResponse:
    t_start = time.perf_counter()
    internal_mode = _resolve_mode(mode)

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    results: list[FileAnonymiseResponse] = []
    for f in files:
        t_file = time.perf_counter()
        filename = f.filename or "unknown"
        contents = await f.read()

        try:
            ingested = ingest_bytes(contents, filename)
        except Exception as e:
            logger.warning("Ingestion failed for %s: %s", filename, e)
            results.append(FileAnonymiseResponse(
                filename=filename,
                source_type="unknown",
                is_scanned=False,
                extracted_text="",
                anonymised_text="",
                mode=internal_mode,
                num_entities=0,
                entities_by_type={},
                vault_size=0,
                ocr_engine=None,
                processing_time_ms=round((time.perf_counter() - t_file) * 1000, 1),
                handwritten_regions=0,
            ))
            continue

        extracted_text = ingested["text"]
        result = anonymise(extracted_text, mode=internal_mode)
        _persist_vault(result.vault)

        results.append(FileAnonymiseResponse(
            filename=filename,
            source_type=ingested["source_type"],
            is_scanned=ingested["is_scanned"],
            extracted_text=extracted_text,
            anonymised_text=result.anonymised_text,
            mode=internal_mode,
            num_entities=len(result.spans),
            entities_by_type=result.to_dict()["entities_by_type"],
            vault_size=len(result.vault),
            ocr_engine=ingested["metadata"].get("ocr_engine"),
            processing_time_ms=round((time.perf_counter() - t_file) * 1000, 1),
            handwritten_regions=ingested["metadata"].get("handwritten_regions", 0),
        ))

    total_ms = (time.perf_counter() - t_start) * 1000
    return BatchFileResponse(
        file_count=len(results),
        results=results,
        total_time_ms=round(total_ms, 1),
    )


@app.post("/anonymise/folder", response_model=FolderAnalysisResponse)
async def anonymise_folder(
    files: list[UploadFile] = File(...),
    mode: Mode = "two_step",
) -> FolderAnalysisResponse:
    """
    Two-phase folder processing:
    Phase 1: Ingest all files, flag scanned/handwritten.
    Phase 2: Anonymize all, return summary + results.
    """
    t_start = time.perf_counter()
    internal_mode = _resolve_mode(mode)

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Phase 1: Ingest and analyze
    file_data: list[tuple[str, bytes, dict]] = []
    summaries: list[FolderFileInfo] = []
    for f in files:
        filename = f.filename or "unknown"
        contents = await f.read()
        try:
            ingested = ingest_bytes(contents, filename)
            file_data.append((filename, contents, ingested))
            summaries.append(FolderFileInfo(
                filename=filename,
                source_type=ingested["source_type"],
                is_scanned=ingested["is_scanned"],
                handwritten_regions=ingested["metadata"].get("handwritten_regions", 0),
                needs_ocr=ingested["is_scanned"],
            ))
        except Exception as e:
            logger.warning("Ingestion failed for %s: %s", filename, e)
            file_data.append((filename, contents, None))
            summaries.append(FolderFileInfo(
                filename=filename,
                source_type="unknown",
                is_scanned=False,
                handwritten_regions=0,
                needs_ocr=False,
            ))

    # Phase 2: Anonymize
    results: list[FileAnonymiseResponse] = []
    for (filename, contents, ingested), summary in zip(file_data, summaries):
        t_file = time.perf_counter()
        if ingested is None:
            results.append(FileAnonymiseResponse(
                filename=filename,
                source_type="unknown",
                is_scanned=False,
                extracted_text="",
                anonymised_text="",
                mode=internal_mode,
                num_entities=0,
                entities_by_type={},
                vault_size=0,
                ocr_engine=None,
                processing_time_ms=0.0,
                handwritten_regions=0,
            ))
            continue

        extracted_text = ingested["text"]
        result = anonymise(extracted_text, mode=internal_mode)
        _persist_vault(result.vault)

        results.append(FileAnonymiseResponse(
            filename=filename,
            source_type=ingested["source_type"],
            is_scanned=ingested["is_scanned"],
            extracted_text=extracted_text,
            anonymised_text=result.anonymised_text,
            mode=internal_mode,
            num_entities=len(result.spans),
            entities_by_type=result.to_dict()["entities_by_type"],
            vault_size=len(result.vault),
            ocr_engine=ingested["metadata"].get("ocr_engine"),
            processing_time_ms=round((time.perf_counter() - t_file) * 1000, 1),
            handwritten_regions=ingested["metadata"].get("handwritten_regions", 0),
        ))

    total_ms = (time.perf_counter() - t_start) * 1000
    return FolderAnalysisResponse(
        file_count=len(results),
        file_summary=summaries,
        results=results,
        total_time_ms=round(total_ms, 1),
    )


@app.post("/vault/reveal")
def vault_reveal(req: RevealRequest) -> dict:
    """In production this MUST be behind authn/authz with audit logging."""
    original = _vault.reveal(req.token)
    if original is None:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"token": req.token, "original": original}


@app.get("/vault/info")
def vault_info() -> dict:
    """Return vault location and size for the frontend display."""
    db_path = Path(_vault.db_path).resolve()
    return {
        "location": str(db_path),
        "size": len(_vault),
        "exists": db_path.exists(),
    }


# =========================================================================== #
# MODULE 2 — Summarisation                                                    #
# =========================================================================== #
@app.post("/summarise/text", response_model=SummariseResponse)
def summarise_text(req: SummariseTextRequest) -> SummariseResponse:
    """Summarise raw text. STUB — replace with your backend logic."""
    raise HTTPException(
        status_code=501,
        detail="Module 2 (Summarisation) backend not yet connected. "
               "Plug your summarisation logic into api.py → summarise_text()."
    )


@app.post("/summarise/file", response_model=SummariseResponse)
async def summarise_file(
    file: UploadFile = File(...),
    length: str = "detailed",
) -> SummariseResponse:
    """Summarise an uploaded file. STUB — replace with your backend logic."""
    raise HTTPException(
        status_code=501,
        detail="Module 2 (Summarisation) backend not yet connected. "
               "Plug your summarisation logic into api.py → summarise_file()."
    )


# =========================================================================== #
# MODULE 3 — Comparison                                                       #
# =========================================================================== #
@app.post("/compare/texts", response_model=CompareResponse)
def compare_texts(req: CompareTextsRequest) -> CompareResponse:
    """Compare two texts. STUB — replace with your backend logic."""
    raise HTTPException(
        status_code=501,
        detail="Module 3 (Comparison) backend not yet connected. "
               "Plug your comparison logic into api.py → compare_texts()."
    )


@app.post("/compare/files", response_model=CompareResponse)
async def compare_files(
    files: list[UploadFile] = File(...),
) -> CompareResponse:
    """Compare two uploaded files. STUB — replace with your backend logic."""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Upload exactly 2 files to compare")
    raise HTTPException(
        status_code=501,
        detail="Module 3 (Comparison) backend not yet connected. "
               "Plug your comparison logic into api.py → compare_files()."
    )


# =========================================================================== #
# MODULE 4 — Classification                                                   #
# =========================================================================== #
@app.post("/classify/text", response_model=ClassifyResponse)
def classify_text(req: ClassifyTextRequest) -> ClassifyResponse:
    """Classify text. STUB — replace with your backend logic."""
    raise HTTPException(
        status_code=501,
        detail="Module 4 (Classification) backend not yet connected. "
               "Plug your classification logic into api.py → classify_text()."
    )


@app.post("/classify/file", response_model=ClassifyResponse)
async def classify_file(
    file: UploadFile = File(...),
) -> ClassifyResponse:
    """Classify an uploaded file. STUB — replace with your backend logic."""
    raise HTTPException(
        status_code=501,
        detail="Module 4 (Classification) backend not yet connected. "
               "Plug your classification logic into api.py → classify_file()."
    )


# =========================================================================== #
# MODULE 5 — Inspection Report                                                #
# =========================================================================== #
@app.post("/inspect/text", response_model=InspectResponse)
def inspect_text(req: InspectTextRequest) -> InspectResponse:
    """Generate inspection report from text. STUB — replace with your backend logic."""
    raise HTTPException(
        status_code=501,
        detail="Module 5 (Inspection) backend not yet connected. "
               "Plug your inspection logic into api.py → inspect_text()."
    )


@app.post("/inspect/file", response_model=InspectResponse)
async def inspect_file(
    file: UploadFile = File(...),
) -> InspectResponse:
    """Generate inspection report from file. STUB — replace with your backend logic."""
    raise HTTPException(
        status_code=501,
        detail="Module 5 (Inspection) backend not yet connected. "
               "Plug your inspection logic into api.py → inspect_file()."
    )


# --------------------------------------------------------------------------- #
# Startup: pre-load OCR model so first request is fast                        #
# --------------------------------------------------------------------------- #
@app.on_event("startup")
async def startup():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-24s | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Preload NER engine (spaCy + Presidio) to avoid 50s delay on first request
    logger.info("Preloading NER engine...")
    try:
        from detection import ner_available
        is_ready = ner_available()
        logger.info("NER engine ready: %s", is_ready)
    except Exception as e:
        logger.warning("NER preload failed: %s", e)
    preload_ocr()


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _persist_vault(vault: dict[str, str]) -> None:
    if not vault:
        return
    _vault.store_many(
        (tok, orig, _entity_from_token(tok)) for tok, orig in vault.items()
    )


def _entity_from_token(token: str) -> str:
    """Token format is `<ENTITY_hex>`; pull the entity name back out."""
    inner = token.strip("<>")
    return inner.rsplit("_", 1)[0] if "_" in inner else "UNKNOWN"


# =========================================================================== #
# SAE ENGINE — Dedicated SAE Report Anonymization & De-Identification         #
# =========================================================================== #
from sae_engine import (
    process_sae_report,
    traceback_report,
    check_file_duplicate,
    get_file_tracker,
    get_mapping_store,
    get_output_store,
    anonymize_sae,
)


class SAETextRequest(BaseModel):
    text: str
    mode: str = "irreversible"  # "irreversible" or "reversible"
    filename: str = "unknown"


class SAETracebackRequest(BaseModel):
    file_id: str
    anonymized_text: str


class SAEDuplicateTextRequest(BaseModel):
    text: str


class SAEResponse(BaseModel):
    processed_text: str
    mode: str
    num_entities: int
    entities_by_type: dict[str, int]
    entities: list[dict]
    file_id: str
    file_hash: str
    timestamp: str
    mapping_size: int
    tracking: dict
    mapping_stored: bool = False
    mapping_file_id: str = ""
    encrypted_mapping: dict[str, str] = {}
    processing_time_ms: float = 0.0


@app.post("/sae/anonymize")
def sae_anonymize(req: SAETextRequest):
    """SAE Report: Irreversible Anonymization or Reversible De-identification.

    mode='irreversible' -> asterisks (************), no recovery
    mode='reversible'   -> tokens like [ID-PER-8f3a9c], traceable
    """
    t_start = time.perf_counter()
    sae_mode = "irreversible" if req.mode == "irreversible" else "reversible"
    result = process_sae_report(
        text=req.text,
        mode=sae_mode,
        filename=req.filename,
    )
    elapsed = (time.perf_counter() - t_start) * 1000
    result["processing_time_ms"] = round(elapsed, 1)
    return result


@app.post("/sae/file")
async def sae_anonymize_file(
    file: UploadFile = File(...),
    mode: str = "irreversible",
):
    """SAE Report: Upload a file for anonymization."""
    t_start = time.perf_counter()
    filename = file.filename or "unknown"
    contents = await file.read()

    # Extract text from file
    try:
        ingested = ingest_bytes(contents, filename)
        text = ingested["text"]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File ingestion failed: {e}")

    sae_mode = "irreversible" if mode == "irreversible" else "reversible"
    result = process_sae_report(
        text=text,
        mode=sae_mode,
        filename=filename,
        file_content=contents,
    )
    elapsed = (time.perf_counter() - t_start) * 1000
    result["processing_time_ms"] = round(elapsed, 1)
    result["filename"] = filename
    result["source_type"] = ingested.get("source_type", "unknown")
    result["is_scanned"] = ingested.get("is_scanned", False)
    result["extracted_text"] = text
    return result


@app.post("/sae/traceback")
def sae_traceback(req: SAETracebackRequest):
    """SAE Report: Reconstruct original text from file_id + anonymized text.

    Machine-only operation. Requires the encryption key to be available.
    """
    result = traceback_report(req.file_id, req.anonymized_text)
    return result


@app.post("/sae/check-duplicate")
async def sae_check_duplicate_file(file: UploadFile = File(...)):
    """SAE Report: Check if a file has been processed before (SHA256 hash)."""
    contents = await file.read()
    result = check_file_duplicate(contents)
    result["filename"] = file.filename or "unknown"
    return result


@app.post("/sae/check-duplicate-text")
def sae_check_duplicate_text(req: SAEDuplicateTextRequest):
    """SAE Report: Check if text content has been processed before."""
    result = check_file_duplicate(req.text.encode("utf-8"))
    return result


@app.get("/sae/files")
def sae_list_files():
    """List all tracked SAE files."""
    tracker = get_file_tracker()
    return {"files": tracker.get_all_files()}


@app.get("/sae/mappings")
def sae_list_mappings():
    """List all stored de-identification mappings."""
    store = get_mapping_store()
    return {"mappings": store.list_files()}


@app.get("/sae/mapping/{file_id}")
def sae_get_mapping(file_id: str):
    """Get the encrypted mapping for a specific file.

    Returns encrypted values — decryption happens server-side only.
    """
    store = get_mapping_store()
    encrypted = store.retrieve(file_id)
    if not encrypted:
        raise HTTPException(status_code=404, detail=f"No mapping for file_id: {file_id}")
    return {
        "file_id": file_id,
        "mapping_count": len(encrypted),
        "note": "Values are encrypted. Use /sae/traceback to reconstruct.",
    }


@app.get("/sae/outputs")
def sae_list_outputs():
    """List all stored SAE processing outputs."""
    store = get_output_store()
    return {"outputs": store.list_outputs()}


@app.get("/sae/outputs/{file_id}")
def sae_get_outputs(file_id: str):
    """Get outputs for a specific file_id."""
    store = get_output_store()
    results = store.get_by_file_id(file_id)
    if not results:
        raise HTTPException(status_code=404, detail=f"No outputs for file_id: {file_id}")
    return {"file_id": file_id, "outputs": results}


class TokenLookupRequest(BaseModel):
    file_id: str
    token: str


@app.post("/sae/lookup-token")
def sae_lookup_token(req: TokenLookupRequest):
    """Decrypt a single token from the mapping store. Returns the original value."""
    store = get_mapping_store()
    encrypted = store.retrieve(req.file_id)
    if not encrypted:
        raise HTTPException(status_code=404, detail=f"No mapping for file_id: {req.file_id}")
    if req.token not in encrypted:
        return {"found": False, "token": req.token, "file_id": req.file_id}
    from sae_engine import _fernet
    try:
        original = _fernet.decrypt(encrypted[req.token].encode()).decode()
    except Exception:
        original = "[DECRYPT_FAILED]"
    return {"found": True, "token": req.token, "original_value": original, "file_id": req.file_id}


# =========================================================================== #
# MOUNT SUB-MODULES — all modules on single port 8000                        #
# =========================================================================== #

def _try_mount_module2():
    """Mount Module 2 (Summarisation) at /m2/."""
    try:
        import importlib.util
        m2_dir = str(Path(__file__).resolve().parent.parent / "Module_2" / "cdsco_data_summarisation")
        if m2_dir not in sys.path:
            sys.path.insert(0, m2_dir)
        spec = importlib.util.spec_from_file_location("m2_api", Path(m2_dir) / "api.py")
        m2_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m2_mod)
        app.mount("/m2", m2_mod.app)
        logger.info("Module 2 (Summarisation) mounted at /m2")
    except Exception as e:
        logger.warning("Module 2 not available: %s", e)


import importlib.util as _ilu
from starlette.middleware.wsgi import WSGIMiddleware


def _load_module(name: str, filepath: str):
    """Load a Python module from a specific file path."""
    spec = _ilu.spec_from_file_location(name, filepath)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BASE = Path(__file__).resolve().parent.parent

# ── Module 2 mount ────────────────────────────────────────────
try:
    _m2_dir = str(_BASE / "Module_2" / "cdsco_data_summarisation")
    if _m2_dir not in sys.path:
        sys.path.insert(0, _m2_dir)
    _m2 = _load_module("m2_api", str(_BASE / "Module_2" / "cdsco_data_summarisation" / "api.py"))
    app.mount("/m2", _m2.app)
    logger.info("Mounted Module 2 at /m2")
except Exception as e:
    logger.warning("Module 2: %s", e)

# ── Module 3: runs on separate port 8003 (config namespace conflict) ──
logger.info("Module 3 available on port 8003 (separate process)")

# ── Module 4 (SAE Classification) ────────────────────────────
try:
    _m4_dir = str(_BASE / "Module4")
    if _m4_dir not in sys.path:
        sys.path.insert(0, _m4_dir)
    _m4 = _load_module("m4_api", str(_BASE / "Module4" / "api.py"))
    app.mount("/m4", _m4.app)
    logger.info("Mounted Module 4 (SAE Classification) at /m4")
except Exception as e:
    logger.warning("Module 4: %s", e)

# ── Module 5 (native FastAPI routes — no WSGI) ───────────────
try:
    _m5_dir = str(_BASE / "Module5")
    if _m5_dir not in sys.path:
        sys.path.insert(0, _m5_dir)

    # Import M5 utils at module level
    _m5_extractor = _load_module("m5_extractor", str(_BASE / "Module5" / "utils" / "extractor.py"))
    _m5_parser = _load_module("m5_parser", str(_BASE / "Module5" / "utils" / "parser.py"))
    _m5_report = _load_module("m5_report", str(_BASE / "Module5" / "utils" / "report_generator.py"))

    from fastapi import Form as _Form
    from fastapi.responses import FileResponse as _FileResp
    from typing import Optional as _Opt
    import tempfile as _m5_tmp
    from datetime import datetime as _m5_dt

    _M5_REPORTS_DIR = _BASE / "Module5" / "reports"
    _M5_REPORTS_DIR.mkdir(exist_ok=True)
    _M5_UPLOADS_DIR = _BASE / "Module5" / "uploads"
    _M5_UPLOADS_DIR.mkdir(exist_ok=True)

    @app.get("/m5/health")
    def m5_health():
        return {"status": "healthy", "module": "Module 5 - Inspection Report Generator"}

    @app.post("/m5/upload")
    async def m5_upload(
        file: UploadFile = File(...),
        firm_name: _Opt[str] = _Form(None),
        license_number: _Opt[str] = _Form(None),
        inspection_date: _Opt[str] = _Form(None),
        state: _Opt[str] = _Form(None),
        manual_notes: _Opt[str] = _Form(None),
    ):
        ext = Path(file.filename or "unknown.txt").suffix.lower()
        # Save uploaded file with safe filename
        ts = _m5_dt.now().strftime("%Y%m%d_%H%M%S")
        import re as _m5_re
        safe_fn = _m5_re.sub(r'[^\w\-.]', '_', file.filename or "unknown.txt")
        saved_name = f"{ts}_{safe_fn}"
        saved_path = str(_M5_UPLOADS_DIR / saved_name)
        with open(saved_path, "wb") as f:
            f.write(await file.read())

        try:
            raw_text = _m5_extractor.extract_text(saved_path)

            # Append manual notes if provided
            if manual_notes and manual_notes.strip():
                raw_text = f"{raw_text}\n\nMANUAL INSPECTION NOTES:\n{manual_notes}"

            parsed_data = _m5_parser.parse_inspection_text(raw_text)

            # Apply field overrides
            for field_name, field_val in [
                ("firm_name", firm_name),
                ("license_number", license_number),
                ("inspection_date", inspection_date),
                ("state", state),
            ]:
                if field_val and field_val.strip():
                    parsed_data[field_name] = field_val.strip()

            # Generate PDF + DOCX reports
            base_name = Path(file.filename or "report").stem
            result = _m5_report.generate_report(parsed_data, str(_M5_REPORTS_DIR), base_name)

            return {
                "success": True,
                "raw_text": raw_text[:3000],
                "doc_type": parsed_data.get("document_type", "unknown"),
                "form_ref": parsed_data.get("form_reference", ""),
                "parsed_data": {k: v for k, v in parsed_data.items() if k not in ("observations", "checklist_sections")},
                "observations": parsed_data.get("observations", {}),
                "sections": list(parsed_data.get("checklist_sections", {}).keys()),
                "reports": result,
                "message": "Report generated successfully",
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/m5/reports")
    def m5_list_reports():
        """List all generated reports."""
        reports = []
        for f in sorted(_M5_REPORTS_DIR.iterdir(), reverse=True):
            if f.suffix in {".pdf", ".docx"}:
                reports.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": _m5_dt.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M"),
                    "type": f.suffix.lstrip(".").upper(),
                })
        return {"files": reports, "count": len(reports)}

    @app.get("/m5/reports/{filename}")
    def m5_download_report(filename: str):
        """Download a generated report file."""
        file_path = _M5_REPORTS_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        media = "application/pdf" if file_path.suffix == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return _FileResp(str(file_path), filename=filename, media_type=media)

    @app.get("/m5/preview/{filename}")
    def m5_preview_report(filename: str):
        """Preview a PDF report in browser."""
        file_path = _M5_REPORTS_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Report not found")
        return _FileResp(str(file_path), media_type="application/pdf")

    @app.post("/m5/manual")
    def m5_manual_entry(body: dict = {}):
        """Generate inspection report from manual observations (no file upload)."""
        from pydantic import BaseModel as _BM
        obs_raw = body.get("observations_raw", "")
        cl = _m5_parser.classify_severity(obs_raw)
        body["observations"] = {
            "critical": cl["critical"], "major": cl["major"],
            "minor": cl["minor"], "raw": obs_raw,
        }
        body.setdefault("document_type", "drug_manufacturing")
        body["total_observations"] = sum(len(cl[k]) for k in ["critical", "major", "minor"])
        if cl["critical"]:
            body["overall_rating"] = "Critical — Immediate Action Required"
        elif cl["major"]:
            body["overall_rating"] = "Major — Action Required"
        elif cl["minor"]:
            body["overall_rating"] = "Minor — Advisory"
        else:
            body["overall_rating"] = "Satisfactory"
        body["report_generated_on"] = _m5_dt.now().strftime("%d/%m/%Y %H:%M")
        result = _m5_report.generate_report(body, str(_M5_REPORTS_DIR), body.get("firm_name", "manual"))
        return {"success": True, "reports": result, "parsed_data": body,
                "observations": body["observations"],
                "doc_type": body["document_type"],
                "sections": [], "raw_text": obs_raw[:3000],
                "message": "Report generated from manual entry"}

    @app.post("/m5/inspect-text")
    def m5_inspect_text(body: dict = {}):
        """Generate inspection report from pasted text (no file upload)."""
        raw_text = body.get("text", "").strip()
        if not raw_text:
            raise HTTPException(status_code=400, detail="No text provided")

        parsed_data = _m5_parser.parse_inspection_text(raw_text)

        # Apply field overrides from request body
        for field_name in ["firm_name", "license_number", "inspection_date", "state"]:
            val = body.get(field_name, "").strip() if body.get(field_name) else ""
            if val:
                parsed_data[field_name] = val

        # Append manual notes
        manual_notes = body.get("manual_notes", "").strip() if body.get("manual_notes") else ""
        if manual_notes:
            raw_text += f"\n\nMANUAL INSPECTION NOTES:\n{manual_notes}"
            parsed_data = _m5_parser.parse_inspection_text(raw_text)

        base_name = parsed_data.get("firm_name", "text_report") or "text_report"
        result = _m5_report.generate_report(parsed_data, str(_M5_REPORTS_DIR), base_name)

        return {
            "success": True,
            "raw_text": raw_text[:3000],
            "doc_type": parsed_data.get("document_type", "unknown"),
            "form_ref": parsed_data.get("form_reference", ""),
            "parsed_data": {k: v for k, v in parsed_data.items()
                           if k not in ("observations", "checklist_sections")},
            "observations": parsed_data.get("observations", {}),
            "sections": list(parsed_data.get("checklist_sections", {}).keys()),
            "reports": result,
            "message": "Report generated from text",
        }

    logger.info("Mounted Module 5 at /m5/*")
except Exception as e:
    logger.warning("Module 5: %s", e)

# Run with:  uvicorn api:app --reload --port 8000
