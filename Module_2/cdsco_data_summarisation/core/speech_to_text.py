"""
==============================================================================
core/speech_to_text.py — Offline Speech-to-Text (Vosk)
==============================================================================
Converts spoken CDSCO officer dictation into text entirely offline using
the Vosk speech recognition library.

Why Vosk?
---------
  • Runs 100 % offline on CPU — no cloud service required
  • Supports Indian English (model: vosk-model-en-in-0.5, ~36 MB)
  • Python 3.10 compatible
  • MIT licensed

Model download (one-time, offline after):
    https://alphacephei.com/vosk/models → vosk-model-en-in-0.5.zip
    Extract to: models/vosk_model/

Dependencies:
    vosk==0.3.45   pyaudio==0.2.14
==============================================================================
"""

import json
import logging
import queue
import threading
import wave
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("cdsco.stt")


class SpeechToTextEngine:
    """
    Offline Speech-to-Text using Vosk.

    Modes
    -----
    1. live_transcribe()   — microphone → real-time transcription
    2. transcribe_file()   — .wav file  → transcription

    Usage
    -----
        engine = SpeechToTextEngine(model_path="models/vosk-model-en-in-0.5")
        text   = engine.live_transcribe(duration_seconds=30)
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        """
        Parameters
        ----------
        model_path : str or Path
            Directory containing extracted Vosk model files.
            Defaults to config.settings.VOSK_MODEL_PATH.
        """
        from config.settings import VOSK_MODEL_PATH, STT_SAMPLE_RATE, STT_CHUNK_SIZE

        self._model_path  = Path(model_path or VOSK_MODEL_PATH)
        self._sample_rate = STT_SAMPLE_RATE
        self._chunk_size  = STT_CHUNK_SIZE
        self._model       = None
        self._rec         = None

        self._transcript_queue: queue.Queue[str] = queue.Queue()
        self._recording       : bool             = False

        self._load_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def live_transcribe(
        self,
        duration_seconds: int = 60,
        on_partial: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Record from the default microphone and return the full transcript.

        Parameters
        ----------
        duration_seconds : int
            Maximum recording time. Recording stops early if silence is
            detected for more than 2 consecutive seconds.
        on_partial : callable(str) | None
            Optional callback invoked with each partial result so the UI
            can display live transcription feedback.

        Returns
        -------
        str  — final transcript (empty string on error)
        """
        try:
            import pyaudio  # noqa: PLC0415
        except ImportError:
            logger.error(
                "pyaudio not installed. Run: pip install pyaudio==0.2.14"
            )
            return ""

        if self._model is None:
            logger.error("Vosk model not loaded; cannot transcribe")
            return ""

        from vosk import KaldiRecognizer  # noqa: PLC0415

        recogniser    = KaldiRecognizer(self._model, self._sample_rate)
        audio_iface   = pyaudio.PyAudio()
        stream        = audio_iface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._sample_rate,
            input=True,
            frames_per_buffer=self._chunk_size,
        )

        full_text   : list[str] = []
        partial_text: str       = ""
        frames_read : int       = 0
        max_frames  : int       = int(self._sample_rate / self._chunk_size * duration_seconds)
        silence_frames: int     = 0
        silence_limit : int     = int(self._sample_rate / self._chunk_size * 2)

        logger.info("Recording started (max %ds)", duration_seconds)
        self._recording = True

        try:
            while frames_read < max_frames and self._recording:
                data = stream.read(self._chunk_size, exception_on_overflow=False)
                frames_read += 1

                if recogniser.AcceptWaveform(data):
                    result = json.loads(recogniser.Result())
                    text   = result.get("text", "").strip()
                    if text:
                        full_text.append(text)
                        silence_frames = 0
                    else:
                        silence_frames += 1
                else:
                    partial = json.loads(recogniser.PartialResult())
                    p_text  = partial.get("partial", "")
                    if p_text != partial_text:
                        partial_text = p_text
                        if on_partial:
                            on_partial(partial_text)

                if silence_frames >= silence_limit:
                    logger.debug("Silence detected; stopping early")
                    break

        finally:
            stream.stop_stream()
            stream.close()
            audio_iface.terminate()
            self._recording = False

        # Flush final result
        final = json.loads(recogniser.FinalResult())
        if final.get("text"):
            full_text.append(final["text"].strip())

        transcript = " ".join(full_text).strip()
        logger.info("Recording complete. Transcript length: %d chars", len(transcript))
        return transcript

    def stop_recording(self) -> None:
        """Signal the live_transcribe loop to stop before the duration expires."""
        self._recording = False
        logger.debug("Stop signal sent to recording loop")

    def transcribe_file(self, wav_path: str) -> str:
        """
        Transcribe a .wav audio file (must be 16kHz mono PCM).

        Parameters
        ----------
        wav_path : str — path to the .wav file

        Returns
        -------
        str — full transcript
        """
        if self._model is None:
            logger.error("Vosk model not loaded; cannot transcribe file")
            return ""

        from vosk import KaldiRecognizer  # noqa: PLC0415

        wav_file = Path(wav_path)
        if not wav_file.exists():
            logger.error("WAV file not found: %s", wav_path)
            return ""

        results: list[str] = []

        with wave.open(str(wav_file), "rb") as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                logger.warning(
                    "WAV file is not mono 16-bit PCM. "
                    "Convert with: ffmpeg -i input.wav -ar 16000 -ac 1 output.wav"
                )

            rec = KaldiRecognizer(self._model, wf.getframerate())
            while True:
                data = wf.readframes(4000)
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    if res.get("text"):
                        results.append(res["text"])

            final = json.loads(rec.FinalResult())
            if final.get("text"):
                results.append(final["text"])

        transcript = " ".join(results).strip()
        logger.info("File transcription complete: %d chars", len(transcript))
        return transcript

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        """Load the Vosk model from disk. Logs a clear error if missing."""
        # Check for actual model content (am/ subfolder = valid Vosk model)
        if not self._model_path.exists() or not (self._model_path / "am").exists():
            logger.error(
                "Vosk model not found at '%s'.\n"
                "Download vosk-model-en-in-0.5 from:\n"
                "  https://alphacephei.com/vosk/models\n"
                "and extract it to: models/vosk_model/",
                self._model_path,
            )
            return

        try:
            import vosk  # noqa: PLC0415
            vosk.SetLogLevel(-1)   # Suppress Kaldi's verbose stdout
            self._model = vosk.Model(str(self._model_path))
            logger.info("Vosk model loaded from '%s'", self._model_path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load Vosk model: %s", exc)
            self._model = None

    @property
    def is_ready(self) -> bool:
        """True if the Vosk model is loaded and ready."""
        return self._model is not None

    def reload(self) -> None:
        """Attempt to reload model (call after placing model files)."""
        self._model = None
        self._load_model()


# ---------------------------------------------------------------------------
# Standalone test helper (not part of the application flow)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    engine = SpeechToTextEngine()
    if engine.is_ready:
        print("Recording for 10 seconds — speak now...")
        text = engine.live_transcribe(duration_seconds=10)
        print("Transcript:", text)
    else:
        print("Model not loaded. Check model path.")