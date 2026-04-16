"""
OCR Configuration
=================
Single place to tune OCR engine, preprocessing, and performance settings.
Change OCR_ENGINE to switch between EasyOCR and PaddleOCR with zero code edits.

Performance note: For hackathon demos, DPI=150 and lighter preprocessing
gives ~4x speedup with acceptable quality. Use DPI=300 for production.
"""

from __future__ import annotations

import os

# ─────────────────────────────────────────────
# OCR Engine Selection
# ─────────────────────────────────────────────
# Options: "easyocr" | "paddleocr"
# Override via environment: OCR_ENGINE=paddleocr
OCR_ENGINE: str = os.getenv("OCR_ENGINE", "easyocr")

# Languages (EasyOCR uses ISO codes like ["en", "hi"])
OCR_LANGUAGES: list[str] = ["en"]

# GPU acceleration (set True if CUDA is available)
USE_GPU: bool = os.getenv("OCR_GPU", "false").lower() == "true"

# ─────────────────────────────────────────────
# Image Preprocessing (OpenCV)
# ─────────────────────────────────────────────
# Lighter preprocessing = faster OCR with acceptable quality
ENABLE_GRAYSCALE: bool = True
ENABLE_DENOISE: bool = False     # Disabled for speed — denoise is slow
ENABLE_THRESHOLD: bool = False   # Disabled for speed — can hurt OCR on clean scans
ENABLE_DESKEW: bool = False      # Disabled for speed — rarely needed

# Adaptive threshold parameters (only used if ENABLE_THRESHOLD=True)
THRESHOLD_BLOCK_SIZE: int = 15
THRESHOLD_CONSTANT: int = 8

# Denoising strength (only used if ENABLE_DENOISE=True)
DENOISE_STRENGTH: int = 10

# ─────────────────────────────────────────────
# Scanned PDF
# ─────────────────────────────────────────────
# DPI 150 = ~4x faster than 300, still readable for OCR
PDF_DPI: int = int(os.getenv("PDF_DPI", "150"))

# Windows: set POPPLER_PATH=C:\poppler\Library\bin
PDF_POPPLER_PATH: str | None = os.getenv(
    "POPPLER_PATH",
    r"C:\poppler-install\poppler-24.08.0\Library\bin"
)

# ─────────────────────────────────────────────
# Performance
# ─────────────────────────────────────────────
MAX_IMAGE_DIMENSION: int = 2048   # Smaller = faster OCR (was 4096)
BATCH_MAX_WORKERS: int = 4

# Maximum pages to OCR in a single PDF (0 = no limit, process all)
MAX_OCR_PAGES: int = int(os.getenv("MAX_OCR_PAGES", "0"))
