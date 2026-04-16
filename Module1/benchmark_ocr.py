"""
OCR Benchmark — EasyOCR vs PaddleOCR
=====================================
Compare accuracy and speed of both engines on the same image.

Usage:
    python benchmark_ocr.py --image scan.png --runs 3
    python benchmark_ocr.py --image scan.png --ground-truth reference.txt

Outputs a side-by-side report of speed and (optionally) character accuracy.
"""

from __future__ import annotations

import argparse
import logging
import time
from difflib import SequenceMatcher
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger(__name__)


def _run_engine(engine_name: str, image, runs: int) -> dict | None:
    """Run OCR `runs` times and collect timing + output."""
    from ingestion import _get_ocr_reader, _ocr_engine_name

    try:
        reader = _get_ocr_reader(engine_name)
    except Exception as e:
        logger.warning("Could not load %s: %s", engine_name, e)
        return None

    times = []
    text = ""
    for i in range(runs):
        t0 = time.perf_counter()

        if engine_name == "easyocr":
            results = reader.readtext(image, detail=0, paragraph=True)
            text = "\n".join(results)
        elif engine_name in ("paddleocr", "paddle"):
            results = reader.ocr(image, cls=True)
            lines = []
            if results and results[0]:
                for line in results[0]:
                    if line and len(line) >= 2:
                        txt = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                        lines.append(txt)
            text = "\n".join(lines)

        elapsed = (time.perf_counter() - t0) * 1000
        times.append(elapsed)
        logger.info("  %s run %d: %.0f ms, %d chars", engine_name, i + 1, elapsed, len(text))

    return {
        "engine": engine_name,
        "text": text,
        "char_count": len(text),
        "avg_ms": round(sum(times) / len(times), 1),
        "min_ms": round(min(times), 1),
        "max_ms": round(max(times), 1),
        "runs": runs,
    }


def _accuracy(extracted: str, reference: str) -> float:
    """Character-level similarity ratio (0.0 to 1.0)."""
    return SequenceMatcher(None, extracted.lower(), reference.lower()).ratio()


def benchmark(image_path: str, runs: int = 3, ground_truth_path: str | None = None):
    """Run both engines and print comparison."""
    from ingestion import _preprocess_image
    import cv2

    logger.info("Preprocessing: %s", image_path)
    img = cv2.imread(image_path)
    if img is None:
        logger.error("Failed to read image: %s", image_path)
        return
    processed = _preprocess_image(img)

    reference = None
    if ground_truth_path:
        reference = Path(ground_truth_path).read_text(encoding="utf-8").strip()

    results = []

    # EasyOCR
    logger.info("── EasyOCR ──")
    r = _run_engine("easyocr", processed, runs)
    if r:
        results.append(r)

    # PaddleOCR
    logger.info("── PaddleOCR ──")
    r = _run_engine("paddleocr", processed, runs)
    if r:
        results.append(r)

    # ── Report ──
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Image: {image_path}")
    print(f"Runs per engine: {runs}")
    print("-" * 60)

    for r in results:
        print(f"\n  Engine:     {r['engine']}")
        print(f"  Avg time:   {r['avg_ms']} ms")
        print(f"  Min / Max:  {r['min_ms']} / {r['max_ms']} ms")
        print(f"  Chars out:  {r['char_count']}")
        if reference:
            acc = _accuracy(r["text"], reference) * 100
            print(f"  Accuracy:   {acc:.1f}%")

    if len(results) == 2:
        faster = results[0] if results[0]["avg_ms"] < results[1]["avg_ms"] else results[1]
        slower = results[1] if faster is results[0] else results[0]
        speedup = slower["avg_ms"] / faster["avg_ms"] if faster["avg_ms"] > 0 else 0
        print(f"\n  -> {faster['engine']} is {speedup:.1f}x faster than {slower['engine']}")

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EasyOCR vs PaddleOCR benchmark")
    parser.add_argument("--image", required=True, help="Path to test image")
    parser.add_argument("--runs", type=int, default=3, help="Runs per engine (default: 3)")
    parser.add_argument("--ground-truth", default=None, help="Reference text file for accuracy")
    args = parser.parse_args()

    benchmark(args.image, args.runs, args.ground_truth)
