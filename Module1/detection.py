"""
Module 1 — Hybrid PII / PHI Detection
=====================================
Two-layer detector:

  Layer A — Regex rules (always available, no heavy deps)
            Indian identifiers: Aadhaar, PAN, IN phone, IFSC, passport,
            MRN, CDSCO file numbers, IND trial IDs; plus generic email,
            URL, credit card, IP, ISO dates.

  Layer B — Presidio + spaCy NER (optional, adds PERSON / LOCATION /
            ORGANIZATION / free-text DATE_TIME). Automatically enabled
            if both libraries are importable and a model is installed.
            The pipeline still runs without them — you just lose
            free-text name detection.

Why the fallback?
-----------------
`presidio-analyzer` + `spacy` + `en_core_web_lg` is ~700 MB and often
fails to install cleanly on first setup. We want a first-run success
experience, so regex-only is the default and Presidio is a bonus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Span:
    start: int
    end: int
    entity: str
    text: str
    score: float

    def __repr__(self) -> str:
        return f"Span({self.entity} @ {self.start}-{self.end} = {self.text!r})"


# --------------------------------------------------------------------------- #
# Regex layer                                                                 #
# --------------------------------------------------------------------------- #
# NOTE: ORDER MATTERS — longer / more specific patterns go first so they
# win the overlap-resolution step.
REGEX_PATTERNS: list[tuple[str, str, float]] = [
    # --- Indian identifiers (high confidence) ---
    ("AADHAAR",     r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",          0.95),
    ("PAN",         r"\b[A-Z]{5}\d{4}[A-Z]\b",                    0.95),
    ("IFSC",        r"\b[A-Z]{4}0[A-Z0-9]{6}\b",                  0.90),
    ("IN_PASSPORT", r"\b[A-PR-WY][1-9]\d{6}\b",                   0.80),
    ("CDSCO_FILE",  r"\bCDSCO[/-][A-Z0-9/\-]{4,30}\b",            0.90),
    ("DRUG_ID",     r"\bIND[-/ ]?\d{4,6}\b",                      0.85),
    ("MRN",         r"\bMRN[-:\s]?\d{6,10}\b",                    0.90),

    # --- Generic contact info ---
    ("EMAIL_ADDRESS",
     r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",       0.95),
    ("IN_PHONE",
     r"(?<!\d)(?:\+91[-\s]?|0)?[6-9]\d{9}(?!\d)",                 0.90),
    ("IN_PHONE",
     r"(?<!\d)(?:\+91[-\s]?|0)?[6-9]\d{4}[-\s]\d{5}(?!\d)",       0.90),

    # --- Address / PIN ---
    # Address with PIN code at end
    ("ADDRESS",
     r"\b\d{1,5}[,/\-]?\s*[A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+){1,6}"
     r",\s*[A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+){0,2}"
     r"(?:,\s*[A-Za-z][a-z]+(?:\s+[A-Za-z][a-z]+){0,2})?"
     r"\s*[-–\s]?\d{6}\b",                                         0.75),
    # Address after label "Address:" — captures the value part only
    ("ADDRESS",
     r"(?<=Address: )"
     r"\d{1,5}[,/\-]?\s*[A-Za-z][\w .]+(?:,\s*[A-Za-z][\w .]+){1,5}",  0.90),
    ("IN_PIN_CODE",
     r"\b[1-9]\d{5}\b",                                            0.55),

    ("URL",
     r"\bhttps?://[^\s<>\"']+",                                   0.95),
    ("IP_ADDRESS",
     r"\b(?:\d{1,3}\.){3}\d{1,3}\b",                              0.85),
    ("CREDIT_CARD",
     r"\b(?:\d[ -]*?){13,16}\b",                                  0.50),

    # --- Dates (several common formats) ---
    ("DATE_TIME",
     r"\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b",                    0.85),
    ("DATE_TIME",
     r"\b\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}\b",                      0.85),
    ("DATE_TIME",
     r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
     r"\s+\d{1,2},?\s+\d{4}\b",                                   0.85),
]

_COMPILED = [(name, re.compile(pat), score)
             for name, pat, score in REGEX_PATTERNS]


def _regex_detect(text: str) -> list[Span]:
    spans: list[Span] = []
    for name, rx, score in _COMPILED:
        for m in rx.finditer(text):
            spans.append(Span(
                start=m.start(), end=m.end(),
                entity=name, text=m.group(), score=score,
            ))
    return spans


# --------------------------------------------------------------------------- #
# Optional NER layer (Presidio + spaCy)                                       #
# --------------------------------------------------------------------------- #
_NER_AVAILABLE: bool | None = None
_ANALYZER = None
_NER_ENTITIES = ["PERSON", "LOCATION", "ORGANIZATION", "NRP"]

# Common Indian name prefixes/titles for regex fallback
_INDIAN_NAME_PREFIXES = r"(?:Dr|Mr|Mrs|Ms|Shri|Smt|Prof|Adv)\.?\s+"

# Non-name words that should stop name matching (uppercase-starting common words)
_NON_NAME_WORDS = (
    r"(?!Age|Suspected|Drug|Dose|Event|Medical|History|Outcome|Reporter|"
    r"Details|Description|Gender|Address|Phone|Hospital|Email|CDSCO|"
    r"Aadhaar|Paracetamol|Aspirin|Ibuprofen|Diabetes|Mellitus|"
    r"Hypertension|Contact|Reference|Number|Report|Clinical|Serious|"
    r"Adverse|Treatment|Admitted|Since|The|His|Her|This|That)"
)

_INDIAN_NAME_PATTERN = re.compile(
    rf"(?:{_INDIAN_NAME_PREFIXES})({_NON_NAME_WORDS}[A-Z][a-z]+(?:\s+{_NON_NAME_WORDS}[A-Z][a-z]+){{0,2}})"
)
# Pattern for "Patient <Name>" or "Name: <Name>" or "Patient Name: <Name>"
_NAMED_ENTITY_PATTERN = re.compile(
    r"(?:Patient\s+Name|Patient|Name|Inspector|Officer|Applicant|Investigator|Sponsor|Reporter|Doctor|Physician|Nurse)"
    r"\s*[:\-]?\s*"
    r"(?:(?:Dr|Mr|Mrs|Ms|Shri|Smt|Prof|Adv)\.?\s+)?"
    rf"({_NON_NAME_WORDS}[A-Z][a-z]+(?:\s+{_NON_NAME_WORDS}[A-Z][a-z]+){{0,2}})"
)
# Pattern for names appearing in narrative context (e.g. "Ramesh Kumar developed")
_NARRATIVE_NAME_PATTERN = re.compile(
    r"(?:Patient|Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Shri|Smt)\s+"
    rf"({_NON_NAME_WORDS}[A-Z][a-z]{{2,}}(?:\s+{_NON_NAME_WORDS}[A-Z][a-z]{{2,}}){{0,2}})"
    r"(?=\s+(?:developed|presented|was|had|reported|admitted|complained|visited|received|underwent|showed|experienced|suffered|died|recovered))"
)
# Pattern for names in context like standalone "Ramesh Kumar developed"
_CONTEXT_NAME_PATTERN = re.compile(
    rf"\b({_NON_NAME_WORDS}[A-Z][a-z]{{2,}}(?:\s+{_NON_NAME_WORDS}[A-Z][a-z]{{2,}}){{1,2}})\b"
    r"(?=\s+(?:developed|presented|was|had|reported|complained|visited|received|underwent|showed|experienced|suffered|died|recovered|is\s+a|aged|age))"
)

# --------------------------------------------------------------------------- #
# Hospital / Organization regex fallback                                       #
# --------------------------------------------------------------------------- #
_HOSPITAL_SUFFIXES = (
    r"(?:Hospital|Hospitals|Clinic|Clinics|Medical\s+(?:College|Center|Centre)|"
    r"Institute|Health\s+(?:Center|Centre)|Nursing\s+Home|Pharma|"
    r"Pharmaceuticals|Laboratory|Laboratories|Labs?|"
    r"Research\s+(?:Center|Centre|Institute)|Foundation)"
)
_HOSPITAL_PATTERN = re.compile(
    rf"\b([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*\s+{_HOSPITAL_SUFFIXES})\b"
)
# Well-known Indian hospital names that might not end with "Hospital"
_KNOWN_HOSPITALS = re.compile(
    r"\b(AIIMS|NIMHANS|CMC\s+Vellore|PGI\s+Chandigarh|Safdarjung|"
    r"Apollo|Fortis|Max\s+Healthcare|Medanta|Manipal|Narayana\s+Health|"
    r"Lilavati|Kokilaben|Tata\s+Memorial|KIMS|Aster|Columbia\s+Asia)\b",
    re.IGNORECASE
)

# --------------------------------------------------------------------------- #
# Location / City regex fallback                                               #
# --------------------------------------------------------------------------- #
_INDIAN_CITIES = re.compile(
    r"\b(Mumbai|Delhi|Bangalore|Bengaluru|Chennai|Kolkata|Hyderabad|Pune|"
    r"Ahmedabad|Jaipur|Lucknow|Kanpur|Nagpur|Indore|Thane|Bhopal|"
    r"Visakhapatnam|Patna|Vadodara|Ghaziabad|Ludhiana|Agra|Nashik|"
    r"Faridabad|Meerut|Rajkot|Kalyan|Vasai|Varanasi|Srinagar|Aurangabad|"
    r"Dhanbad|Amritsar|Navi\s+Mumbai|Allahabad|Ranchi|Howrah|Coimbatore|"
    r"Jabalpur|Gwalior|Vijayawada|Jodhpur|Madurai|Raipur|Kota|"
    r"Chandigarh|Guwahati|Solapur|Hubli|Tiruchirappalli|Bareilly|"
    r"Moradabad|Mysore|Thiruvananthapuram|Tiruppur|Noida|Gurgaon|Gurugram|"
    r"Dehradun|Shimla|Gangtok|Imphal|Shillong|Aizawl|Kohima|Itanagar|"
    r"Panaji|Daman|Silvassa|Kavaratti|Port\s+Blair|Puducherry|Pondicherry)\b"
)


def _regex_detect_names(text: str) -> list[Span]:
    """Fallback name detection via regex patterns for Indian names."""
    spans = []
    for rx in (_INDIAN_NAME_PATTERN, _NAMED_ENTITY_PATTERN, _NARRATIVE_NAME_PATTERN, _CONTEXT_NAME_PATTERN):
        for m in rx.finditer(text):
            grp = 1 if rx.groups else 0
            name = m.group(grp)
            # Skip very short or all-caps (likely acronyms)
            if len(name) < 3 or name.isupper():
                continue
            # Skip common non-name words
            _SKIP_WORDS = {
                "Patient", "Name", "Gender", "Male", "Female", "Address",
                "Phone", "Hospital", "Doctor", "Event", "Drug", "Dose",
                "Medical", "History", "Outcome", "Reporter", "Details",
                "Description", "Suspected", "Report", "Diabetes", "The",
                "His", "Her", "This", "That", "Was", "Had", "Has",
            }
            if name.split()[0] in _SKIP_WORDS:
                continue
            start = m.start(grp)
            end = m.end(grp)
            spans.append(Span(start=start, end=end, entity="PERSON", text=name, score=0.85))
    return spans


def _regex_detect_hospitals(text: str) -> list[Span]:
    """Detect hospital and organization names via regex."""
    spans = []
    for rx in (_HOSPITAL_PATTERN, _KNOWN_HOSPITALS):
        for m in rx.finditer(text):
            name = m.group(1) if m.lastindex else m.group(0)
            if len(name) < 3:
                continue
            spans.append(Span(
                start=m.start(), end=m.end(),
                entity="ORGANIZATION", text=m.group(0), score=0.80
            ))
    return spans


def _regex_detect_locations(text: str) -> list[Span]:
    """Detect Indian city names via regex."""
    spans = []
    for m in _INDIAN_CITIES.finditer(text):
        spans.append(Span(
            start=m.start(), end=m.end(),
            entity="LOCATION", text=m.group(0), score=0.80
        ))
    return spans


def _try_build_analyzer():
    """Attempt to build a Presidio analyzer. Return None if anything fails."""
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
    except ImportError:
        return None

    # Try spaCy models — prefer smaller models for speed
    for model in ("en_core_web_sm", "en_core_web_md", "en_core_web_lg"):
        try:
            import spacy
            spacy.load(model)
        except Exception:
            continue
        try:
            nlp_config = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": model}],
            }
            engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()
            return AnalyzerEngine(nlp_engine=engine, supported_languages=["en"])
        except Exception:
            continue
    return None


_NER_CHUNK_SIZE = 10_000  # Process NER in 10K char chunks for speed


def _ner_detect(text: str) -> list[Span]:
    global _NER_AVAILABLE, _ANALYZER
    if _NER_AVAILABLE is False:
        return []
    if _ANALYZER is None:
        _ANALYZER = _try_build_analyzer()
        _NER_AVAILABLE = _ANALYZER is not None
        if not _NER_AVAILABLE:
            return []

    # For large texts, process in chunks to avoid spaCy OOM/slowness
    if len(text) <= _NER_CHUNK_SIZE:
        return _ner_detect_chunk(text, 0)

    all_spans: list[Span] = []
    # Split on paragraph boundaries near chunk size
    offset = 0
    while offset < len(text):
        end = min(offset + _NER_CHUNK_SIZE, len(text))
        # Try to break at a paragraph or sentence boundary
        if end < len(text):
            for sep in ("\n\n", "\n", ". ", " "):
                idx = text.rfind(sep, offset + _NER_CHUNK_SIZE // 2, end + 500)
                if idx > offset:
                    end = idx + len(sep)
                    break
        chunk = text[offset:end]
        chunk_spans = _ner_detect_chunk(chunk, offset)
        all_spans.extend(chunk_spans)
        offset = end
    return all_spans


def _ner_detect_chunk(text: str, offset: int) -> list[Span]:
    """Run NER on a single chunk, adjusting span offsets."""
    try:
        results = _ANALYZER.analyze(
            text=text, language="en", entities=_NER_ENTITIES
        )
    except Exception:
        return []
    return [
        Span(start=r.start + offset, end=r.end + offset, entity=r.entity_type,
             text=text[r.start:r.end], score=r.score)
        for r in results
    ]


def _reclassify_locations(spans: list[Span], text: str) -> list[Span]:
    """Re-tag LOCATION spans that look like full addresses (contain commas + digits)."""
    out: list[Span] = []
    for s in spans:
        if s.entity == "LOCATION" and len(s.text) > 20:
            # If it contains a comma and digits, it's likely an address
            if "," in s.text and re.search(r"\d", s.text):
                out.append(Span(s.start, s.end, "ADDRESS", s.text, s.score))
                continue
        out.append(s)
    return out


# Words that NER often wrongly tags as PERSON / ORGANIZATION.
# Check is case-insensitive for robustness.
_NER_FALSE_POSITIVES = {
    w.lower() for w in (
        "Patient", "Gender", "Male", "Female", "Address", "Phone", "Hospital",
        "Doctor", "Event", "Drug", "Dose", "Medical", "History", "Outcome",
        "Reporter", "Details", "Description", "Suspected", "Report",
        "Diabetes", "Mellitus", "Hypertension", "Paracetamol", "Aspirin",
        "Ibuprofen", "ICU", "OPD", "IPD", "SAE", "SERIOUS", "ADVERSE",
        "Name", "Email", "Age", "CDSCO", "Reference", "Aadhaar", "PAN",
        "Kumar", "Treatment", "Admission", "Clinical", "Number",
        "Twice", "Daily", "Days", "Since", "Severe", "After",
    )
}

# Single words that are valid ORGs (hospital abbreviations etc.)
_VALID_SHORT_ORGS = {"AIIMS", "NIMHANS", "KIMS", "PGI", "CMC", "ICU"}


def _filter_ner_spans(spans: list[Span]) -> list[Span]:
    """Remove common false positive NER results aggressively."""
    out: list[Span] = []
    for s in spans:
        clean = s.text.strip().rstrip(":").strip()

        # Skip if the text (or any single-word version) is a known false positive
        if clean.lower() in _NER_FALSE_POSITIVES:
            continue

        # Skip if span contains newlines (NER grabbed across lines)
        if "\n" in s.text:
            first_line = s.text.split("\n")[0].strip()
            if first_line and first_line.lower() not in _NER_FALSE_POSITIVES and len(first_line) >= 3:
                out.append(Span(s.start, s.start + len(first_line), s.entity, first_line, s.score))
            continue

        # For single-word ORG: only keep known abbreviations
        words = clean.split()
        if s.entity == "ORGANIZATION" and len(words) == 1:
            if clean.upper() not in _VALID_SHORT_ORGS:
                continue

        # For single-word PERSON: skip if it's a common word or too short
        if s.entity == "PERSON" and len(words) == 1:
            if clean.lower() in _NER_FALSE_POSITIVES or len(clean) < 3:
                continue

        # For multi-word spans: if ALL words are false positives, skip
        if all(w.lower() in _NER_FALSE_POSITIVES for w in words):
            continue

        out.append(s)
    return out


def ner_available() -> bool:
    """Check (lazily) whether the NER layer can be used."""
    global _NER_AVAILABLE, _ANALYZER
    if _NER_AVAILABLE is None:
        _ANALYZER = _try_build_analyzer()
        _NER_AVAILABLE = _ANALYZER is not None
    return bool(_NER_AVAILABLE)


# --------------------------------------------------------------------------- #
# Overlap resolution                                                          #
# --------------------------------------------------------------------------- #
def _resolve_overlaps(spans: list[Span]) -> list[Span]:
    """Keep the highest-scoring (then longest) span when two overlap."""
    if not spans:
        return spans
    spans = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    out: list[Span] = []
    for s in spans:
        if out and s.start < out[-1].end:
            prev = out[-1]
            if (s.score, s.end - s.start) > (prev.score, prev.end - prev.start):
                out[-1] = s
        else:
            out.append(s)
    return out


# --------------------------------------------------------------------------- #
# Text cleanup (fixes PDF layout artifacts before detection)                  #
# --------------------------------------------------------------------------- #
# Matches 3+ single letters separated by single spaces, e.g. "K A T U R E"
# that pdfplumber often produces from stylised / letter-spaced headings.
_SPACED_LETTERS = re.compile(r"\b(?:[A-Z] ){2,}[A-Z]\b")


def _collapse_spaced_letters(text: str) -> str:
    """Collapse 'K A T U R E' -> 'KATURE' so NER can see the name properly.
    This is intentionally conservative: only uppercase single letters and
    only runs of 3 or more."""
    return _SPACED_LETTERS.sub(lambda m: m.group(0).replace(" ", ""), text)


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #
def detect(text: str) -> list[Span]:
    """Run regex + (optional) NER + name/hospital/location regex detection.

    Note: the input text is lightly normalised (spaced-out headings are
    collapsed) before detection. The returned span offsets refer to the
    NORMALISED text, so callers that need to highlight entities in the
    original should call `normalise_for_detection(text)` first and use
    that version for both detection and display.
    """
    if not text:
        return []
    text = normalise_for_detection(text)
    ner_spans = _ner_detect(text)
    ner_spans = _reclassify_locations(ner_spans, text)
    ner_spans = _filter_ner_spans(ner_spans)
    # Regex fallback layers — always run so detection works without spaCy
    name_spans = _regex_detect_names(text)
    hospital_spans = _regex_detect_hospitals(text)
    location_spans = _regex_detect_locations(text)
    spans = _regex_detect(text) + ner_spans + name_spans + hospital_spans + location_spans
    spans.sort(key=lambda s: s.start)
    return _resolve_overlaps(spans)


def normalise_for_detection(text: str) -> str:
    """Apply the same preprocessing `detect()` does. Expose it so callers
    can keep detection spans aligned with the text they display."""
    return _collapse_spaced_letters(text)


if __name__ == "__main__":
    sample = (
        "Patient Rajesh Kumar (Aadhaar 1234 5678 9012, PAN ABCDE1234F) "
        "was admitted on 12/03/2024 at AIIMS Delhi. "
        "Contact +91-9876543210 or rajesh.k@example.com. "
        "Trial ID: IND-12345. File CDSCO/NDD/2024/001."
    )
    print(f"NER layer available: {ner_available()}")
    print()
    for sp in detect(sample):
        print(sp)
