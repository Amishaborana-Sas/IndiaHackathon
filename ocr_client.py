"""
Shared OCR Client — calls the centralized OCR microservice
============================================================
All modules use this single client to send files to the OCR server
running on port 8001. This ensures:
  - One EasyOCR model in memory (saves ~500MB+ RAM)
  - Consistent OCR quality and preprocessing across all modules
  - Single point to configure languages, DPI, enhancement

Usage:
    from ocr_client import ocr_extract_text, ocr_extract_file

    # From file path
    text = ocr_extract_file("scan.pdf")

    # From bytes
    text = ocr_extract_bytes(raw_bytes, "scan.pdf")
"""

import os
import logging
import requests
from pathlib import Path

logger = logging.getLogger("ocr_client")

OCR_SERVER_URL = os.environ.get("OCR_SERVER_URL", "http://localhost:8001")

# Timeout: 5 minutes for large multi-page PDFs
OCR_TIMEOUT = int(os.environ.get("OCR_TIMEOUT", "300"))


def ocr_extract_file(file_path: str, languages: str = "en", dpi: int = 200, enhance: bool = True) -> dict:
    """
    Send a file to the OCR server and get extracted text back.

    Parameters
    ----------
    file_path  : path to the file (PDF, image, etc.)
    languages  : comma-separated language codes (default: "en")
    dpi        : PDF rendering DPI (default: 200)
    enhance    : apply image enhancement (default: True)

    Returns
    -------
    dict with keys:
        full_text    : str — complete extracted text
        pages        : list[str] — per-page text
        page_count   : int
        source_type  : str — "image" | "pdf_digital" | "pdf_scanned" | "pdf_mixed"
        elapsed_sec  : float
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        return _call_ocr(f, p.name, languages, dpi, enhance)


def ocr_extract_bytes(data: bytes, filename: str = "upload", languages: str = "en",
                      dpi: int = 200, enhance: bool = True) -> dict:
    """
    Send raw bytes to the OCR server.

    Parameters
    ----------
    data      : raw file bytes
    filename  : original filename (used for format detection)
    languages : comma-separated language codes
    dpi       : PDF rendering DPI
    enhance   : apply image enhancement

    Returns
    -------
    dict (same shape as ocr_extract_file)
    """
    import io
    f = io.BytesIO(data)
    f.name = filename
    return _call_ocr(f, filename, languages, dpi, enhance)


def _call_ocr(file_obj, filename: str, languages: str, dpi: int, enhance: bool) -> dict:
    """Internal: POST file to OCR server."""
    url = f"{OCR_SERVER_URL}/api/ocr"
    try:
        resp = requests.post(
            url,
            files={"file": (filename, file_obj)},
            data={
                "languages": languages,
                "dpi": str(dpi),
                "enhance": "true" if enhance else "false",
                "structured": "false",
            },
            timeout=OCR_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            raise RuntimeError(data.get("error", "OCR server returned failure"))

        result = data["result"]
        logger.info(
            "OCR complete: %s → %d chars, %d pages, type=%s, %.1fs",
            filename,
            len(result.get("full_text", "")),
            result.get("page_count", 0),
            result.get("source_type", "?"),
            result.get("elapsed_sec", 0),
        )
        return result

    except requests.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to OCR server at {OCR_SERVER_URL}.\n"
            "Make sure the OCR server is running (python ocr_module/server.py)."
        )
    except requests.Timeout:
        raise RuntimeError(
            f"OCR request timed out after {OCR_TIMEOUT}s. "
            "The file may be too large or the server is overloaded."
        )


def ocr_health() -> dict:
    """Check if OCR server is healthy."""
    try:
        resp = requests.get(f"{OCR_SERVER_URL}/api/health", timeout=5)
        return resp.json()
    except Exception:
        return {"status": "unavailable", "error": f"Cannot reach {OCR_SERVER_URL}"}


def ocr_extract_text(file_path: str, **kwargs) -> str:
    """Convenience: extract just the text string from a file."""
    result = ocr_extract_file(file_path, **kwargs)
    return result.get("full_text", "")


def ocr_extract_text_from_bytes(data: bytes, filename: str = "upload", **kwargs) -> str:
    """Convenience: extract just the text string from bytes."""
    result = ocr_extract_bytes(data, filename, **kwargs)
    return result.get("full_text", "")
