"""
==============================================================================
CDSCO DATA SUMMARISATION TOOL — main.py
==============================================================================
Project      : CDSCO Hackathon — Data Summarisation Module
Compliance   : CDSCO Schedule M (GMP), DPDP Act 2023, ICMR Biomedical
               Research Ethics Guidelines 2017
Python       : 3.10+
Offline      : Fully offline — no API calls
==============================================================================

Entry point. Launches the Tkinter GUI. All core summarisation, speech-to-text,
and report generation are wired through this file.

Usage
-----
    python main.py

Dependencies (see requirements.txt for exact versions):
    sumy, spacy, vosk, pyaudio, fpdf2, python-docx, tkinter (stdlib)
==============================================================================
"""

import sys
import os
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on PYTHONPATH so sibling packages resolve correctly
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Bootstrap logging BEFORE importing any project module so all sub-loggers
# inherit this configuration automatically.
# ---------------------------------------------------------------------------
from config.settings import (
    LOG_LEVEL,
    LOG_FILE,
    OUTPUT_DIR,
    DATA_DIR,
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
    ],
)

logger = logging.getLogger("cdsco.main")

# ---------------------------------------------------------------------------
# Ensure required runtime directories exist
# ---------------------------------------------------------------------------
for _dir in (OUTPUT_DIR, DATA_DIR):
    Path(_dir).mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Launch the Tkinter UI
# ---------------------------------------------------------------------------
def main() -> None:
    """
    Application entry point.

    Imports are deferred to this function so that any ImportError surfaces
    with a clear traceback rather than an opaque crash at module level.
    """
    logger.info("=" * 60)
    logger.info("CDSCO Data Summarisation Tool — starting up")
    logger.info("=" * 60)

    try:
        from ui.app import CDSCOApp
    except ImportError as exc:
        logger.critical(
            "Failed to import UI module. "
            "Ensure all dependencies are installed: pip install -r requirements.txt\n"
            f"Error: {exc}"
        )
        sys.exit(1)

    try:
        app = CDSCOApp()
        app.run()
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Unhandled exception in main loop: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()