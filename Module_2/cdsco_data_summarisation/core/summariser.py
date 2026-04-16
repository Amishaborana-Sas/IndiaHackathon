"""
==============================================================================
core/summariser.py — Offline Extractive Summarisation Engine
==============================================================================
Uses the `sumy` library for extractive summarisation (no internet required,
no large language model required).

Algorithm options (set in config/settings.py):
  • LSA          — Latent Semantic Analysis (best for regulatory/structured text)
  • LexRank      — Graph-based, robust for long documents
  • Luhn         — Frequency-based, fast
  • TextRank     — PageRank-variant, good general purpose

Why extractive and not abstractive?
--------------------------------------
Abstractive summarisation (e.g. BART, T5) requires downloading 400MB–1.5GB
model weights. For a hackathon setup that must work fully offline on any
machine, extractive summarisation via sumy is the correct choice:
  - Lightweight (~2 MB total)
  - Deterministic & auditable (required for regulatory submissions)
  - Sentences are verbatim from the source — no hallucination risk
  - CDSCO inspection reports require verbatim traceability
==============================================================================
"""

import logging
from typing import Optional

from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer
from sumy.summarizers.lex_rank import LexRankSummarizer
from sumy.summarizers.luhn import LuhnSummarizer
from sumy.summarizers.text_rank import TextRankSummarizer
from sumy.nlp.stemmers import Stemmer
from sumy.utils import get_stop_words

from config.settings import (
    SUMMARY_SENTENCE_COUNT,
    SUMMARISATION_ALGORITHM,
)

logger = logging.getLogger("cdsco.summariser")

LANGUAGE = "english"

# Map algorithm name → sumy summariser class
_SUMMARISER_MAP = {
    "lsa":       LsaSummarizer,
    "lexrank":   LexRankSummarizer,
    "luhn":      LuhnSummarizer,
    "text_rank": TextRankSummarizer,
}


class DataSummariser:
    """
    Offline extractive summariser for CDSCO inspection text.

    Usage
    -----
        summariser = DataSummariser()
        result = summariser.summarise(text, sentence_count=8)
        print(result.summary)
        print(result.key_points)
    """

    def __init__(
        self,
        algorithm: str = SUMMARISATION_ALGORITHM,
        sentence_count: int = SUMMARY_SENTENCE_COUNT,
    ) -> None:
        """
        Parameters
        ----------
        algorithm      : str  — summarisation algorithm key (see _SUMMARISER_MAP)
        sentence_count : int  — number of sentences to extract
        """
        self.algorithm      = algorithm.lower()
        self.sentence_count = sentence_count

        if self.algorithm not in _SUMMARISER_MAP:
            raise ValueError(
                f"Unknown algorithm '{algorithm}'. "
                f"Choose from: {list(_SUMMARISER_MAP.keys())}"
            )

        self._stemmer       = Stemmer(LANGUAGE)
        self._stop_words    = get_stop_words(LANGUAGE)
        self._summariser_cls = _SUMMARISER_MAP[self.algorithm]
        logger.info(
            "DataSummariser ready | algorithm=%s | sentences=%d",
            self.algorithm, self.sentence_count,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def summarise(
        self,
        text: str,
        sentence_count: Optional[int] = None,
    ) -> "SummarisationResult":
        """
        Summarise the given text.

        Parameters
        ----------
        text           : str  — pre-processed inspection text
        sentence_count : int  — override default sentence count for this call

        Returns
        -------
        SummarisationResult
            .summary      → str  (joined summary paragraph)
            .sentences    → list[str]  (individual summary sentences)
            .key_points   → list[str]  (bullet-ready key findings)
            .word_count   → int
            .sentence_count → int
        """
        n = sentence_count if sentence_count is not None else self.sentence_count

        if not text or not text.strip():
            logger.warning("Empty text passed to summariser; returning empty result")
            return SummarisationResult(sentences=[], original_text=text)

        try:
            parser    = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
            summariser = self._summariser_cls(self._stemmer)
            summariser.stop_words = self._stop_words

            raw_sentences = summariser(parser.document, n)
            sentence_list = [str(s) for s in raw_sentences]

            logger.info(
                "Summarisation complete: %d → %d sentences",
                len(list(parser.document.sentences)),
                len(sentence_list),
            )
            return SummarisationResult(
                sentences=sentence_list,
                original_text=text,
                algorithm=self.algorithm,
            )

        except Exception as exc:  # noqa: BLE001
            logger.exception("Summarisation failed: %s", exc)
            # Graceful degradation: return first N sentences as fallback
            fallback = self._fallback_summarise(text, n)
            return SummarisationResult(
                sentences=fallback,
                original_text=text,
                algorithm="fallback",
            )

    def summarise_sections(
        self,
        sections: dict[str, str],
        sentence_count: Optional[int] = None,
    ) -> dict[str, "SummarisationResult"]:
        """
        Summarise a dict of named sections independently.

        Parameters
        ----------
        sections : dict[str, str]  — e.g. {"observations": "...", "capa": "..."}

        Returns
        -------
        dict[str, SummarisationResult]
        """
        results: dict[str, SummarisationResult] = {}
        for section_name, section_text in sections.items():
            if section_text.strip():
                logger.debug("Summarising section: %s", section_name)
                results[section_name] = self.summarise(section_text, sentence_count)
        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_summarise(text: str, n: int) -> list[str]:
        """
        Simple first-N-sentences fallback used when sumy encounters an error
        (e.g. text too short to build an LSA matrix).
        """
        import re
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return sentences[:n]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

class SummarisationResult:
    """
    Structured container for a summarisation output.

    Attributes
    ----------
    sentences     : list[str]  — extracted sentences
    summary       : str        — sentences joined into a paragraph
    key_points    : list[str]  — same sentences, formatted as bullet points
    word_count    : int        — word count of the summary
    sentence_count: int
    algorithm     : str
    original_text : str
    """

    def __init__(
        self,
        sentences: list[str],
        original_text: str = "",
        algorithm: str = "",
    ) -> None:
        self.sentences      = sentences
        self.original_text  = original_text
        self.algorithm      = algorithm
        self.summary        = " ".join(sentences)
        self.key_points     = [f"• {s}" for s in sentences]
        self.word_count     = len(self.summary.split())
        self.sentence_count = len(sentences)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"SummarisationResult("
            f"algorithm={self.algorithm!r}, "
            f"sentences={self.sentence_count}, "
            f"words={self.word_count})"
        )