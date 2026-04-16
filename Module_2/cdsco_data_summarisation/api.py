"""
Module 2 — FastAPI HTTP wrapper for the summarisation engine
=============================================================
Exposes the offline extractive summarisation (sumy-based) as REST endpoints
so the RegLens AI frontend can call it over HTTP.

Endpoints
---------
POST /summarise/text   -> summarise raw text
POST /summarise/file   -> summarise an uploaded file (PDF, DOCX, TXT, image)
GET  /health           -> liveness check

Run with:  python -m uvicorn api:app --reload --port 8002
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import time
import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

# Bootstrap logging
from config.settings import LOG_LEVEL, OUTPUT_DIR, DATA_DIR
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("cdsco.api")

# Ensure dirs
for _d in (OUTPUT_DIR, DATA_DIR):
    Path(_d).mkdir(parents=True, exist_ok=True)

# Import core modules
from core.preprocessor import TextPreprocessor
from core.summariser import DataSummariser
from core.report_generator import auto_algo
from utils.file_handler import load_any_file

app = FastAPI(
    title="CDSCO Module 2 — Data Summarisation",
    version="1.0.0",
    description="Offline extractive summarisation for CDSCO regulatory documents.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                   "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pre-load the preprocessor (lightweight)
_preprocessor = TextPreprocessor()


# --------------------------------------------------------------------------- #
# Request / response models
# --------------------------------------------------------------------------- #
class SummariseTextRequest(BaseModel):
    text: str
    doc_type: str = "SUGAM / Inspection Data"
    sentence_count: int = 8


class SummariseResponse(BaseModel):
    summary: str
    key_points: list[str]
    word_count: int
    sentence_count: int
    algorithm: str
    doc_type: str
    processing_time_ms: float
    sections: dict[str, str] = {}


# --------------------------------------------------------------------------- #
# Shared summarisation logic
# --------------------------------------------------------------------------- #
def _run_summarisation(raw_text: str, doc_type: str, sentence_count: int) -> dict:
    t_start = time.perf_counter()

    if not raw_text or len(raw_text.split()) < 10:
        raise HTTPException(status_code=400, detail="Text too short — need at least 10 words.")

    algo = auto_algo(doc_type)
    clean = _preprocessor.process(raw_text)
    sections = _preprocessor.extract_sections(clean)

    summariser = DataSummariser(algorithm=algo, sentence_count=sentence_count)
    result = summariser.summarise(clean, sentence_count)
    section_summaries = summariser.summarise_sections(sections, sentence_count=3)

    elapsed_ms = (time.perf_counter() - t_start) * 1000

    # Build section summary strings
    sec_map = {}
    for sec_name, sec_result in section_summaries.items():
        if sec_result.summary:
            sec_map[sec_name] = sec_result.summary

    return {
        "summary": result.summary,
        "key_points": [s.lstrip("• ").strip() for s in result.key_points],
        "word_count": result.word_count,
        "sentence_count": result.sentence_count,
        "algorithm": algo,
        "doc_type": doc_type,
        "processing_time_ms": round(elapsed_ms, 1),
        "sections": sec_map,
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.post("/summarise/text", response_model=SummariseResponse)
def summarise_text(req: SummariseTextRequest) -> SummariseResponse:
    data = _run_summarisation(req.text, req.doc_type, req.sentence_count)
    return SummariseResponse(**data)


AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wma", ".webm"}


def _find_ffmpeg() -> str:
    """Find ffmpeg binary: system PATH → imageio-ffmpeg → raise."""
    import shutil
    # 1. System PATH
    path = shutil.which("ffmpeg")
    if path:
        return path
    # 2. imageio-ffmpeg (pip package that bundles a static ffmpeg binary)
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        path = get_ffmpeg_exe()
        if path:
            return path
    except ImportError:
        pass
    raise FileNotFoundError("ffmpeg not found")


def _convert_to_wav(file_path: str) -> str:
    """Convert any audio file to 16kHz mono WAV for Vosk. Returns temp WAV path."""
    import subprocess
    import tempfile as _tf

    wav_path = _tf.mktemp(suffix=".wav")

    # Try ffmpeg (system or imageio-ffmpeg bundled)
    try:
        ffmpeg_bin = _find_ffmpeg()
        subprocess.run(
            [ffmpeg_bin, "-y", "-i", file_path,
             "-ar", "16000", "-ac", "1", "-sample_fmt", "s16", wav_path],
            capture_output=True, timeout=120, check=True,
        )
        return wav_path
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as e:
        logger.warning("ffmpeg conversion failed: %s", e.stderr[:200] if e.stderr else e)

    # Try pydub (uses ffmpeg under the hood but can auto-discover it)
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        audio.export(wav_path, format="wav")
        return wav_path
    except Exception:
        pass

    raise FileNotFoundError(
        "Cannot convert audio to WAV. Install one of:\n"
        "  pip install imageio-ffmpeg   (recommended, bundles ffmpeg)\n"
        "  pip install pydub            (needs ffmpeg on PATH)\n"
        "  winget install ffmpeg        (system install)"
    )


def _transcribe_audio(file_path: str) -> str:
    """Transcribe audio file using Vosk (offline STT). Falls back to a message if unavailable."""
    try:
        from core.speech_to_text import SpeechToTextEngine
        stt = SpeechToTextEngine()
        if not stt.is_ready:
            raise RuntimeError("Vosk model not loaded")
        # Convert to WAV if needed
        ext = Path(file_path).suffix.lower()
        if ext != ".wav":
            wav_path = _convert_to_wav(file_path)
            try:
                transcript = stt.transcribe_file(wav_path)
            finally:
                Path(wav_path).unlink(missing_ok=True)
        else:
            transcript = stt.transcribe_file(file_path)
        return transcript or ""
    except ImportError:
        raise HTTPException(status_code=400, detail="Speech-to-text (Vosk) not available. Install: pip install vosk pyaudio")
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Audio transcription failed: {e}")


@app.post("/summarise/file", response_model=SummariseResponse)
async def summarise_file(
    file: UploadFile = File(...),
    doc_type: str = Form("SUGAM / Inspection Data"),
    sentence_count: int = Form(8),
) -> SummariseResponse:
    ext = Path(file.filename or "unknown.txt").suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # Handle audio files — transcribe first, then summarise
        if ext in AUDIO_EXTS:
            raw_text = _transcribe_audio(tmp_path)
            if not raw_text or len(raw_text.strip()) < 20:
                raise HTTPException(status_code=400, detail="Audio transcription returned too little text. Ensure the audio has clear speech.")
            # Auto-select Meeting Transcript type for audio
            effective_type = "Meeting Transcript / Audio"
        else:
            raw_text = load_any_file(tmp_path)
            effective_type = doc_type

        if not raw_text or len(raw_text.strip()) < 20:
            raise HTTPException(status_code=400, detail="Could not extract enough text from file.")
        data = _run_summarisation(raw_text, effective_type, sentence_count)
        return SummariseResponse(**data)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "module": "Module 2 — Data Summarisation",
        "algorithms": ["lsa", "lexrank", "luhn", "text_rank"],
    }
