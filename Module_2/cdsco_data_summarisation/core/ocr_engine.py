"""
ocr_engine.py
=============
100% Local OCR Engine — powered by EasyOCR (deep learning).

NO APIs. NO Tesseract. NO Poppler. NO internet required after install.
All inference runs on-device (CPU or GPU).

Supports:
  - JPEG / PNG / WEBP / GIF / BMP / TIFF images
  - PDF files  (rendered via PyMuPDF — pure pip, no poppler binary)
  - Scanned documents
  - Screenshots
  - Handwritten notes
  - Multi-language documents (80+ languages)

Install:
    pip install easyocr pymupdf pillow numpy

Usage (standalone):
    from ocr_engine import OCREngine
    engine = OCREngine(languages=["en"])
    result = engine.run("scan.pdf")
    print(result["full_text"])

CLI:
    python ocr_engine.py scan.pdf
    python ocr_engine.py photo.jpg --languages en hi --json
"""

import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Union, BinaryIO, List

import numpy as np

# ── EasyOCR ───────────────────────────────────────────────────────────────────
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("[OCR] WARNING: easyocr not found. Run: pip install easyocr", file=sys.stderr)

# ── PyMuPDF (PDF rendering — NOT poppler) ────────────────────────────────────
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ── Pillow ────────────────────────────────────────────────────────────────────
try:
    from PIL import Image as PILImage, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
#  MIME / FORMAT DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def _detect_mime(data: bytes, filename: str = "") -> str:
    sig = data[:12]
    if sig[:4] == b"%PDF":
        return "application/pdf"
    if sig[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if sig[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if sig[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if sig[:4] == b"RIFF" and sig[8:12] == b"WEBP":
        return "image/webp"
    if sig[:2] == b"BM":
        return "image/bmp"
    if sig[:4] in (b"II\x2a\x00", b"MM\x00\x2a"):
        return "image/tiff"
    ext = Path(filename).suffix.lower()
    return {
        ".pdf":  "application/pdf",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif":  "image/gif",
        ".webp": "image/webp",
        ".bmp":  "image/bmp",
        ".tiff": "image/tiff",
        ".tif":  "image/tiff",
    }.get(ext, "application/octet-stream")


# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE PREPROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def _preprocess_image(img_bytes: bytes, enhance: bool = True, is_scanned: bool = False) -> np.ndarray:
    """
    Convert raw image bytes -> numpy RGB array.
    Applies stronger enhancement pipeline for scanned/photographed documents.
    """
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow required: pip install pillow")

    img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")

    if enhance:
        w, h = img.size

        # Scanned pages need more aggressive upscaling for OCR accuracy
        min_dim = 1200 if is_scanned else 800
        if w < min_dim or h < min_dim:
            scale = max(min_dim / w, min_dim / h, 1.0)
            img = img.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)

        if is_scanned:
            # For scanned docs: denoise -> sharpen -> contrast
            img = img.filter(ImageFilter.MedianFilter(size=3))
            img = ImageEnhance.Sharpness(img).enhance(2.0)
            img = ImageEnhance.Contrast(img).enhance(1.5)
            img = ImageEnhance.Brightness(img).enhance(1.1)
        else:
            img = ImageEnhance.Sharpness(img).enhance(1.5)
            img = ImageEnhance.Contrast(img).enhance(1.2)

    return np.array(img)


def _img_bytes_to_pil(data: bytes) -> "PILImage.Image":
    return PILImage.open(io.BytesIO(data)).convert("RGB")


# ══════════════════════════════════════════════════════════════════════════════
#  PDF RENDERING  (PyMuPDF — no poppler binary needed)
# ══════════════════════════════════════════════════════════════════════════════

def _pdf_render_pages(pdf_bytes: bytes, dpi: int = 150) -> list:
    """Render each PDF page to PNG bytes using PyMuPDF."""
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError(
            "PyMuPDF required for PDF support.\n"
            "Install: pip install pymupdf\n"
            "(Pure pip — no poppler binary needed.)"
        )
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pages = []
    for page in doc:
        pix = page.get_pixmap(matrix=mat, alpha=False)
        pages.append(pix.tobytes("png"))
    doc.close()
    return pages


def _pdf_extract_digital_text(pdf_bytes: bytes) -> list:
    """Extract selectable text from digital (non-scanned) PDFs."""
    if not PYMUPDF_AVAILABLE:
        return []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts = [page.get_text() for page in doc]
    doc.close()
    return texts


# ══════════════════════════════════════════════════════════════════════════════
#  READER SINGLETON (EasyOCR model loads once, reused for all requests)
# ══════════════════════════════════════════════════════════════════════════════

_reader_cache: dict = {}

def _get_reader(languages: list, gpu: bool = False) -> "easyocr.Reader":
    key = tuple(sorted(languages)) + (gpu,)
    if key not in _reader_cache:
        if not EASYOCR_AVAILABLE:
            raise RuntimeError("easyocr not installed. Run: pip install easyocr")
        _reader_cache[key] = easyocr.Reader(languages, gpu=gpu, verbose=False)
    return _reader_cache[key]


# ══════════════════════════════════════════════════════════════════════════════
#  POST-PROCESSING HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _results_to_text(results: list, paragraph: bool = True) -> str:
    """
    Convert EasyOCR result list -> clean text string.
    Groups detections into visual lines by vertical overlap, then sorts
    each line left-to-right. This correctly handles tables, multi-column
    layouts, and mixed content (headers + body text).
    EasyOCR returns: [(bbox, text, confidence), ...]
    """
    if not results:
        return "[NO TEXT DETECTED]"

    def get_top(r):
        return float(min(p[1] for p in r[0]))

    def get_bottom(r):
        return float(max(p[1] for p in r[0]))

    def get_left(r):
        return float(min(p[0] for p in r[0]))

    def get_height(r):
        return get_bottom(r) - get_top(r)

    if not paragraph:
        sorted_r = sorted(results, key=lambda r: (get_top(r), get_left(r)))
        return "\n".join(r[1] for r in sorted_r)

    # ── Group into visual rows ────────────────────────────────────────────────
    # Strategy: for each detection, find existing row it overlaps vertically.
    # Overlap threshold = 50% of the shorter item's height.
    rows = []  # list of lists of detections

    for det in sorted(results, key=get_top):
        det_top    = get_top(det)
        det_bottom = get_bottom(det)
        det_h      = max(get_height(det), 8)
        placed = False

        for row in rows:
            # Use the row's average vertical span
            row_top    = min(get_top(d) for d in row)
            row_bottom = max(get_bottom(d) for d in row)
            row_h      = max(row_bottom - row_top, 8)

            # Check vertical overlap
            overlap = min(det_bottom, row_bottom) - max(det_top, row_top)
            threshold = min(det_h, row_h) * 0.4  # 40% overlap = same row

            if overlap >= threshold:
                row.append(det)
                placed = True
                break

        if not placed:
            rows.append([det])

    # ── Sort each row left-to-right, then join ────────────────────────────────
    lines = []
    for row in rows:
        row_sorted = sorted(row, key=get_left)
        line_text = "  ".join(r[1] for r in row_sorted)
        lines.append(line_text)

    return "\n".join(lines)


def _to_py(obj):
    """
    Recursively convert NumPy scalars/arrays to plain Python types.
    Fixes: 'Object of type int32 is not JSON serializable'
    EasyOCR bboxes contain np.int32 points — this sanitizes them.
    """
    if isinstance(obj, dict):
        return {k: _to_py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_py(i) for i in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _results_to_structured(results: list) -> dict:
    """Build structured metadata from EasyOCR results."""
    if not results:
        return {
            "raw_text": "[NO TEXT DETECTED]",
            "confidence": "low",
            "word_count": 0,
            "char_count": 0,
            "detections": []
        }

    text = _results_to_text(results)
    confidences = [float(r[2]) for r in results]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0

    return {
        "raw_text": text,
        "confidence": "high" if avg_conf > 0.85 else "medium" if avg_conf > 0.6 else "low",
        "avg_confidence_score": round(avg_conf, 4),
        "word_count": len(text.split()),
        "char_count": len(text),
        "detection_count": len(results),
        "detections": [
            {
                "text": str(r[1]),
                "confidence": round(float(r[2]), 4),
                "bbox": [[int(pt[0]), int(pt[1])] for pt in r[0]]
            }
            for r in results
        ]
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class OCREngine:
    """
    100% Local OCR Engine powered by EasyOCR.

    Parameters
    ----------
    languages : list[str]
        EasyOCR language codes. Default ["en"].
        Examples: ["en", "hi"], ["en", "ta"], ["ch_sim", "en"]
        Full list: https://www.jaided.ai/easyocr/
    gpu : bool
        Use GPU if available (faster). Default False (CPU).
    dpi : int
        Resolution for PDF page rendering. Default 150.
    enhance : bool
        Apply image enhancement before OCR (helps scanned docs). Default True.
    structured : bool
        If True, include detailed metadata in results. Default False.
    paragraph : bool
        Reconstruct paragraph/line structure. Default True.
    """

    def __init__(
        self,
        languages: List[str] = None,
        gpu: bool = False,
        dpi: int = 150,
        enhance: bool = True,
        structured: bool = False,
        paragraph: bool = True,
    ):
        self.languages = languages or ["en"]
        self.gpu = gpu
        self.dpi = dpi
        self.enhance = enhance
        self.structured = structured
        self.paragraph = paragraph
        self._reader = None  # lazy load

    def _get_reader(self):
        if self._reader is None:
            self._reader = _get_reader(self.languages, self.gpu)
        return self._reader

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, source: Union[str, bytes, BinaryIO], filename: str = "") -> dict:
        """
        Main OCR method. Accepts file path, bytes, or file-like object.

        Returns dict:
            full_text   : str         — complete extracted text
            pages       : list[str]   — per-page text
            page_count  : int
            source_type : str         — "image" | "pdf_digital" | "pdf_scanned"
            filename    : str
            metadata    : dict        — if structured=True
            elapsed_sec : float       — processing time
        """
        t0 = time.time()
        raw, fname = self._load(source, filename)
        mime = _detect_mime(raw, fname)

        if mime == "application/pdf":
            result = self._run_pdf(raw, fname)
        else:
            result = self._run_image(raw, mime, fname)

        result["elapsed_sec"] = round(time.time() - t0, 2)
        return result

    def run_bytes(self, data: bytes, mime: str) -> dict:
        """OCR pre-loaded bytes with known MIME."""
        if mime == "application/pdf":
            return self._run_pdf(data, "file.pdf")
        return self._run_image(data, mime, "file")

    def run_numpy(self, img_array: np.ndarray) -> dict:
        """OCR a numpy array (H×W×3 RGB)."""
        t0 = time.time()
        results = self._get_reader().readtext(img_array)
        text = _results_to_text(results, self.paragraph)
        out = {
            "full_text": text,
            "pages": [text],
            "page_count": 1,
            "source_type": "numpy_array",
            "filename": "",
            "elapsed_sec": round(time.time() - t0, 2),
        }
        if self.structured:
            out["metadata"] = _results_to_structured(results)
        return out

    # ── Loaders ───────────────────────────────────────────────────────────────

    def _load(self, source, filename):
        if isinstance(source, (str, Path)):
            p = Path(source)
            return p.read_bytes(), p.name
        if isinstance(source, bytes):
            return source, filename
        return source.read(), filename or getattr(source, "name", "")

    # ── Image pipeline ────────────────────────────────────────────────────────

    def _run_image(self, data: bytes, mime: str, fname: str) -> dict:
        img_array = _preprocess_image(data, enhance=self.enhance)
        results = self._get_reader().readtext(img_array)
        text = _results_to_text(results, self.paragraph)

        out = {
            "full_text": text,
            "pages": [text],
            "page_count": 1,
            "source_type": "image",
            "filename": fname,
        }
        if self.structured:
            out["metadata"] = _results_to_structured(results)
        return out

    # ── PDF pipeline ──────────────────────────────────────────────────────────

    def _run_pdf(self, data: bytes, fname: str) -> dict:
        """
        Hybrid per-page PDF processing:
        - Each page is evaluated individually.
        - If a page has sufficient selectable text  → use digital text (fast, perfect).
        - If a page is blank or image-only (scanned) → render it and run EasyOCR on it.
        This correctly handles mixed PDFs where some pages are typed and some are scanned.
        """
        # Extract digital text for all pages at once
        digital_texts = _pdf_extract_digital_text(data)

        # Render all pages to images (needed for scanned pages)
        # Use higher DPI for better OCR quality on scanned content
        render_dpi = max(self.dpi, 200)
        page_images = _pdf_render_pages(data, dpi=render_dpi)

        page_texts = []
        all_metadata = []
        source_types = []

        for i, img_bytes in enumerate(page_images):
            digital = digital_texts[i].strip() if i < len(digital_texts) else ""

            # A page is considered "digital" if it has more than 80 characters
            # of selectable text (threshold avoids treating artifact-only pages as digital)
            MIN_DIGITAL_CHARS = 80

            if len(digital) >= MIN_DIGITAL_CHARS:
                # Digital page — use extracted text directly
                page_texts.append(digital)
                source_types.append("digital")
                if self.structured:
                    all_metadata.append({
                        "raw_text": digital,
                        "confidence": "high",
                        "avg_confidence_score": 1.0,
                        "source": "digital_extraction",
                        "word_count": len(digital.split()),
                        "char_count": len(digital),
                        "detections": []
                    })
            else:
                # Scanned / image page — run EasyOCR
                img_array = _preprocess_image(img_bytes, enhance=self.enhance, is_scanned=True)
                results = self._get_reader().readtext(img_array)
                text = _results_to_text(results, self.paragraph)

                # If OCR returned nothing but digital had some text, use digital as fallback
                if (not text or text == "[NO TEXT DETECTED]") and digital:
                    text = digital

                page_texts.append(text)
                source_types.append("ocr")
                if self.structured:
                    all_metadata.append(_results_to_structured(results))

        full = "\n\n--- Page Break ---\n\n".join(page_texts)

        # Determine overall source type
        has_ocr     = "ocr" in source_types
        has_digital = "digital" in source_types
        if has_ocr and has_digital:
            overall_type = "pdf_mixed"
        elif has_ocr:
            overall_type = "pdf_scanned"
        else:
            overall_type = "pdf_digital"

        out = {
            "full_text": full,
            "pages": page_texts,
            "page_count": len(page_texts),
            "source_type": overall_type,
            "page_source_types": source_types,
            "filename": fname,
        }
        if self.structured:
            out["metadata"] = {"pages": all_metadata}
        return out

    # ── Utilities ─────────────────────────────────────────────────────────────

    def get_bounding_boxes(self, source: Union[str, bytes, BinaryIO], filename: str = "") -> list:
        """
        Return raw EasyOCR detections with bounding boxes and confidence scores.
        Each item: {"text": str, "bbox": [[x,y],...], "confidence": float}
        """
        raw, fname = self._load(source, filename)
        mime = _detect_mime(raw, fname)
        if mime == "application/pdf":
            raise NotImplementedError("Bounding boxes only available for images.")
        img_array = _preprocess_image(raw, enhance=self.enhance)
        results = self._get_reader().readtext(img_array)
        return [{"text": str(r[1]), "bbox": [[int(pt[0]), int(pt[1])] for pt in r[0]], "confidence": round(float(r[2]), 4)} for r in results]

    @staticmethod
    def supported_languages() -> list:
        """Return list of EasyOCR language codes."""
        return [
            "en", "hi", "ta", "te", "kn", "ml", "bn", "mr", "gu", "pa",
            "ur", "ch_sim", "ch_tra", "ja", "ko", "ar", "fr", "de", "es",
            "it", "pt", "ru", "tr", "vi", "th", "pl", "nl", "sv", "cs",
        ]


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Local OCR Engine — EasyOCR powered, no API, no Tesseract"
    )
    parser.add_argument("file", help="Image or PDF path")
    parser.add_argument("--languages", nargs="+", default=["en"],
                        help="Language codes (default: en)")
    parser.add_argument("--gpu", action="store_true", help="Use GPU")
    parser.add_argument("--dpi", type=int, default=150, help="PDF render DPI")
    parser.add_argument("--no-enhance", action="store_true",
                        help="Skip image enhancement")
    parser.add_argument("--structured", action="store_true",
                        help="Include structured metadata")
    parser.add_argument("--json", action="store_true",
                        help="Output full result as JSON")
    args = parser.parse_args()

    print(f"[OCR] Loading model for languages: {args.languages}", file=sys.stderr)
    engine = OCREngine(
        languages=args.languages,
        gpu=args.gpu,
        dpi=args.dpi,
        enhance=not args.no_enhance,
        structured=args.structured,
    )

    print(f"[OCR] Processing: {args.file}", file=sys.stderr)
    result = engine.run(args.file)
    print(f"[OCR] Done in {result.get('elapsed_sec', '?')}s", file=sys.stderr)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(result["full_text"])