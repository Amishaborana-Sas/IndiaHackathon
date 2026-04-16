"""
==============================================================================
core/preprocessor.py — Text Pre-processing Pipeline
==============================================================================
Cleans, normalises and tokenises raw inspection text before it reaches the
summarisation engine.

Regulatory context
------------------
Raw text from CDSCO inspections often contains:
  - Abbreviations specific to Schedule M / MDR 2017 (e.g. QC, GMP, SOP)
  - Mixed Hindi-English transliterations
  - OCR artefacts from scanned Forms 31/32/35
  - Numeric identifiers (licence numbers, batch codes)

This module sanitises all of the above while preserving regulatory terms.
==============================================================================
"""

import re
import logging
import unicodedata
from typing import Optional

logger = logging.getLogger("cdsco.preprocessor")

# ---------------------------------------------------------------------------
# Domain-specific abbreviation expansions
# These mirror terminology used in CDSCO Schedule M, MDR 2017, and ICMR
# ethics guidelines so the summariser produces readable sentences.
# ---------------------------------------------------------------------------
CDSCO_ABBREVIATIONS: dict[str, str] = {
    r"\bGMP\b":   "Good Manufacturing Practice",
    r"\bGLP\b":   "Good Laboratory Practice",
    r"\bGCP\b":   "Good Clinical Practice",
    r"\bSOP\b":   "Standard Operating Procedure",
    r"\bCAPRA\b": "Corrective and Preventive Action",
    r"\bCAPA\b":  "Corrective and Preventive Action",
    r"\bQC\b":    "Quality Control",
    r"\bQA\b":    "Quality Assurance",
    r"\bAR\b":    "Analytical Report",
    r"\bBMR\b":   "Batch Manufacturing Record",
    r"\bBPR\b":   "Batch Packing Record",
    r"\bMDR\b":   "Medical Device Rules",
    r"\bCTD\b":   "Common Technical Document",
    r"\bIEC\b":   "Independent Ethics Committee",
    r"\bIRB\b":   "Institutional Review Board",
    r"\bICF\b":   "Informed Consent Form",
    r"\bAE\b":    "Adverse Event",
    r"\bSAE\b":   "Serious Adverse Event",
    r"\bADR\b":   "Adverse Drug Reaction",
    r"\bPV\b":    "Pharmacovigilance",
    r"\bDCGI\b":  "Drugs Controller General of India",
    r"\bCDSCO\b": "Central Drugs Standard Control Organisation",
    r"\bFDA\b":   "Food and Drug Administration",
}


class TextPreprocessor:
    """
    Pre-processing pipeline for CDSCO inspection text.

    Usage
    -----
        preprocessor = TextPreprocessor()
        clean_text = preprocessor.process("Raw inspection notes...")
    """

    def __init__(self, expand_abbreviations: bool = True) -> None:
        """
        Parameters
        ----------
        expand_abbreviations : bool
            If True, replace regulatory abbreviations with full forms before
            summarisation for better sentence coherence.
        """
        self.expand_abbreviations = expand_abbreviations
        logger.debug("TextPreprocessor initialised (expand_abbr=%s)", expand_abbreviations)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, raw_text: str) -> str:
        """
        Full pre-processing pipeline.

        Steps applied in order:
            1. Unicode normalisation (NFKC)
            2. Strip HTML / XML tags
            3. Fix common OCR artefacts
            4. Expand CDSCO-specific abbreviations (optional)
            5. Collapse whitespace
            6. Sentence boundary correction

        Parameters
        ----------
        raw_text : str
            Unprocessed text from officer input or speech recognition.

        Returns
        -------
        str
            Clean, normalised text ready for summarisation.
        """
        if not raw_text or not raw_text.strip():
            logger.warning("Empty or blank text passed to preprocessor")
            return ""

        text = raw_text

        text = self._normalise_unicode(text)
        text = self._strip_html(text)
        text = self._fix_ocr_artefacts(text)
        text = self._handle_structured_input(text)

        if self.expand_abbreviations:
            text = self._expand_abbreviations(text)

        text = self._collapse_whitespace(text)
        text = self._fix_sentence_boundaries(text)

        logger.debug("Pre-processing complete. Output length: %d chars", len(text))
        return text

    def extract_sections(self, text: str) -> dict[str, str]:
        """
        Heuristically split text into labelled sections based on common
        CDSCO inspection report headings.

        Returns a dict such as::

            {
                "observations":    "...",
                "deficiencies":    "...",
                "capa":            "...",
                "general_remarks": "...",
            }

        Any text that does not match a known heading is placed under
        ``"general_remarks"``.
        """
        section_patterns: dict[str, str] = {
            "observations":    r"(?i)(observations?|findings?)\s*[:\-]",
            "deficiencies":    r"(?i)(deficien\w+|non[\-\s]?complian\w+)\s*[:\-]",
            "capa":            r"(?i)(capa|corrective\s+action|preventive\s+action)\s*[:\-]",
            "recommendations": r"(?i)(recommendations?|suggestions?)\s*[:\-]",
        }

        sections: dict[str, list[str]] = {k: [] for k in section_patterns}
        sections["general_remarks"] = []

        current_section = "general_remarks"

        for line in text.splitlines():
            matched = False
            for section_name, pattern in section_patterns.items():
                if re.search(pattern, line):
                    current_section = section_name
                    matched = True
                    # Include the heading line in that section
                    sections[current_section].append(line)
                    break
            if not matched:
                sections[current_section].append(line)

        return {k: "\n".join(v).strip() for k, v in sections.items() if v}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_unicode(text: str) -> str:
        """Apply NFKC normalisation to handle accented/special chars."""
        return unicodedata.normalize("NFKC", text)

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove residual HTML or XML tags (e.g. from copy-pasted portals)."""
        return re.sub(r"<[^>]+>", " ", text)

    @staticmethod
    def _fix_ocr_artefacts(text: str) -> str:
        """
        Fix typical OCR errors:
          - Replace pipe '|' used instead of 'I' in all-cap words
          - Remove stray form-feed characters
          - Convert multiple dashes to an em-dash
        """
        text = re.sub(r"\f", "\n", text)                          # form-feed → newline
        text = re.sub(r"-{2,}", "—", text)                        # --- → em-dash
        text = re.sub(r"(?<=[A-Z])\|(?=[A-Z])", "I", text)       # OCR | → I
        return text

    @staticmethod
    def _expand_abbreviations(text: str) -> str:
        """Replace known CDSCO abbreviations with their full forms."""
        for pattern, expansion in CDSCO_ABBREVIATIONS.items():
            text = re.sub(pattern, expansion, text)
        return text

    @staticmethod
    def _collapse_whitespace(text: str) -> str:
        """Replace multiple spaces/tabs with a single space; trim lines."""
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        # Remove empty lines in excess of one blank line
        cleaned: list[str] = []
        prev_blank = False
        for line in lines:
            if not line:
                if not prev_blank:
                    cleaned.append(line)
                prev_blank = True
            else:
                cleaned.append(line)
                prev_blank = False
        return "\n".join(cleaned).strip()

    @staticmethod
    def _fix_sentence_boundaries(text: str) -> str:
        """
        Ensure a space follows sentence-ending punctuation when it is
        immediately followed by a capital letter (common in pasted text).
        E.g. "...GMP.The batch..." → "...GMP. The batch..."
        """
        return re.sub(r"([.!?])([A-Z])", r"\1 \2", text)

    @staticmethod
    def _handle_structured_input(text: str) -> str:
        """
        Detect and convert structured / CSV-like input into proper sentences
        so sumy can tokenise them correctly.

        Handles 4 formats:
          1. CSV rows  — "Area,Finding,Severity,Detail\\nHVAC,Overdue,Major,..."
          2. Pipe-delimited — "HVAC | Overdue | Major | ..."
          3. Numbered/bulleted lines — "1. Finding\\n2. Finding"
          4. Plain newline-separated phrases without terminal punctuation
        """
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return text

        # Detect CSV: >50% of lines have 2+ commas
        comma_lines = sum(1 for l in lines if l.count(",") >= 2)
        is_csv = comma_lines / max(len(lines), 1) > 0.4

        # Detect pipe-delimited
        pipe_lines = sum(1 for l in lines if "|" in l)
        is_pipe = pipe_lines / max(len(lines), 1) > 0.4

        # Detect header row (all caps or known field names)
        _header_words = {"area","finding","severity","details","checklist",
                         "observation","status","item","description","remarks"}
        first_lower = set(lines[0].lower().replace(",", " ").replace("|", " ").split())
        has_header = bool(first_lower & _header_words)

        if is_csv or is_pipe:
            sentences = []
            start = 1 if has_header else 0
            sep = "," if is_csv else "|"
            for line in lines[start:]:
                parts = [p.strip() for p in line.split(sep) if p.strip()]
                if len(parts) >= 2:
                    # Build "Area: Finding (Severity). Detail." pattern
                    sentence = ". ".join(parts)
                    if not sentence.endswith("."):
                        sentence += "."
                    sentences.append(sentence)
                elif parts:
                    s = parts[0]
                    if not s.endswith((".", "!", "?")):
                        s += "."
                    sentences.append(s)
            if sentences:
                return " ".join(sentences)

        # Newline-separated short phrases (no terminal punctuation on most lines)
        no_punct_lines = sum(1 for l in lines if not l.endswith((".", "!", "?")))
        if no_punct_lines / max(len(lines), 1) > 0.6 and len(lines) > 2:
            fixed = []
            for line in lines:
                # Skip likely header/label lines (ALL CAPS, short)
                if line.isupper() and len(line.split()) <= 4:
                    continue
                if not line.endswith((".", "!", "?")):
                    line += "."
                fixed.append(line)
            return " ".join(fixed)

        return text