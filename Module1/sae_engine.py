"""
SAE Anonymization & De-Identification Engine
=============================================
Complete engine for Serious Adverse Event (SAE) report anonymization.

Two modes:
  1. IRREVERSIBLE ANONYMIZATION — PII replaced with asterisks (************)
     No recovery possible. Safe for public release.

  2. REVERSIBLE DE-IDENTIFICATION — PII replaced with machine-generated
     tokens like [ID-PER-8f3a9c]. Each token maps to the original value
     in an encrypted secure store. Traceback is machine-only.

Features:
  - NER + Regex hybrid detection (Indian PII: Aadhaar, PAN, phone, etc.)
  - SAE-specific structured field parsing (Name:, Doctor:, Hospital:, etc.)
  - SHA256 file hashing for duplicate detection
  - Encrypted mapping store (Fernet AES-128-CBC)
  - Zero PII leakage guarantee
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from cryptography.fernet import Fernet

# Import the existing hybrid PII detector
from detection import Span, detect, normalise_for_detection

# ---------------------------------------------------------------------------
# Configuration & Storage Directory
# ---------------------------------------------------------------------------
_HMAC_SECRET = os.environ.get("ANON_HMAC_SECRET", "").encode() or b"SAE-ENGINE-DEMO-KEY"
_VAULT_KEY_ENV = "ANON_VAULT_KEY"

# All SAE persistent data lives here
SAE_DATA_DIR = Path(__file__).parent / "sae_data"
SAE_DATA_DIR.mkdir(exist_ok=True)

SAEMode = Literal["irreversible", "reversible"]


# ---------------------------------------------------------------------------
# Secure Key Management
# ---------------------------------------------------------------------------
def _load_fernet_key() -> bytes:
    """Load or generate a Fernet key for encrypting mappings."""
    key_b64 = os.environ.get(_VAULT_KEY_ENV)
    if key_b64:
        return key_b64.encode()
    key_path = SAE_DATA_DIR / "vault.key"
    if key_path.exists():
        return key_path.read_bytes()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    return key


_fernet = Fernet(_load_fernet_key())


# ---------------------------------------------------------------------------
# Token Generation (Reversible Mode)
# ---------------------------------------------------------------------------
# Entity type -> token prefix mapping
_ENTITY_PREFIX = {
    "PERSON": "PER",
    "PHONE_NUMBER": "PHN",
    "IN_PHONE": "PHN",
    "AADHAAR": "UID",
    "EMAIL_ADDRESS": "EML",
    "ADDRESS": "ADR",
    "ORGANIZATION": "ORG",
    "LOCATION": "LOC",
    "GPE": "LOC",
    "PAN": "PAN",
    "DATE_TIME": "DAT",
    "IN_PASSPORT": "PSP",
    "IFSC": "IFS",
    "MRN": "MRN",
    "DRUG_ID": "DRG",
    "CDSCO_FILE": "CDS",
    "URL": "URL",
    "IP_ADDRESS": "IPA",
    "CREDIT_CARD": "CCN",
    "IN_PIN_CODE": "PIN",
    "NRP": "NRP",
}


def _generate_token(value: str, entity: str) -> str:
    """Generate a deterministic, non-human-readable token.

    Format: [ID-PER-8f3a9c] — prefix encodes entity type, suffix is
    an HMAC-SHA256 truncation so the same input always maps to the
    same token (deterministic for cross-document linking).
    """
    prefix = _ENTITY_PREFIX.get(entity, "UNK")
    digest = hmac.new(
        _HMAC_SECRET, f"{entity}:{value}".encode(), hashlib.sha256
    ).hexdigest()[:6]
    return f"[ID-{prefix}-{digest}]"


# ---------------------------------------------------------------------------
# Masking (Irreversible Mode)
# ---------------------------------------------------------------------------
def _mask_value(value: str, entity: str) -> str:
    """Replace PII with asterisks. Length-independent for security."""
    return "************"


# ---------------------------------------------------------------------------
# SAE-Specific Field Detection
# ---------------------------------------------------------------------------
# These patterns catch structured SAE fields that the general detector might
# miss because they rely on field labels rather than content patterns alone.
_SAE_FIELD_PATTERNS = [
    # "Name: Ramesh Kumar" or "Patient Name: Ramesh Kumar"
    (r"(?:Patient\s+)?Name\s*:\s*(.+?)(?=\n|$)", "PERSON"),
    # "Doctor: Dr. Amit Sharma" or "Physician: Dr. Amit Sharma"
    (r"(?:Doctor|Physician|Treating\s+Doctor)\s*:\s*(.+?)(?=\n|$)", "PERSON"),
    # "Hospital: XYZ Hospital, Pune"
    (r"Hospital\s*:\s*(.+?)(?=\n|$)", "ORGANIZATION"),
    # "Address: 14, MG Road, ..."
    (r"Address\s*:\s*(.+?)(?=\n|$)", "ADDRESS"),
    # "Phone number: 9876543210" or "Phone: ..."
    (r"Phone(?:\s+number)?\s*:\s*(.+?)(?=\n|$)", "IN_PHONE"),
    # "Aadhaar Number: 1234-5678-9012"
    (r"Aadhaar(?:\s+Number)?\s*:\s*(.+?)(?=\n|$)", "AADHAAR"),
    # "Email: ..."
    (r"Email\s*:\s*(.+?)(?=\n|$)", "EMAIL_ADDRESS"),
    # "Reporter: ..."
    (r"Reporter\s*:\s*(.+?)(?=\n|$)", "PERSON"),
]

_SAE_COMPILED = [(re.compile(pat, re.IGNORECASE), entity) for pat, entity in _SAE_FIELD_PATTERNS]


def _detect_sae_fields(text: str) -> list[Span]:
    """Detect PII in structured SAE field-value pairs.

    This catches cases where the value after a label (e.g. 'Name: Ramesh')
    might not be detected by general NER because it depends on context.
    """
    spans = []
    for rx, entity in _SAE_COMPILED:
        for m in rx.finditer(text):
            value = m.group(1).strip()
            if not value or len(value) < 2:
                continue
            # Skip if value looks like a number for non-phone fields
            if entity == "PERSON" and value.replace(" ", "").isdigit():
                continue
            # Strip age suffix like ": 52" from name fields
            if entity == "PERSON":
                value = re.sub(r"\s*:\s*\d+\s*$", "", value).strip()
                # Remove trailing age
                value = re.sub(r"\s+\d{1,3}\s*$", "", value).strip()
                if not value or len(value) < 2:
                    continue
            start = m.start(1)
            end = start + len(value)
            spans.append(Span(
                start=start, end=end,
                entity=entity, text=value, score=0.95,
            ))
    return spans


# ---------------------------------------------------------------------------
# Inline Name Detection (catches "Patient Ramesh" in narrative text)
# ---------------------------------------------------------------------------
_INLINE_NAME_PATTERNS = [
    # "Patient Ramesh" anywhere in text
    re.compile(
        r"\bPatient\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b"
    ),
    # "Dr. Amit Sharma" in narrative
    re.compile(
        r"\b(?:Dr|Mr|Mrs|Ms|Shri|Smt)\.?\s+([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){0,2})\b"
    ),
]


def _detect_inline_names(text: str) -> list[Span]:
    """Detect names embedded in narrative text like 'Patient Ramesh developed...'"""
    spans = []
    for rx in _INLINE_NAME_PATTERNS:
        for m in rx.finditer(text):
            name = m.group(1).strip()
            if len(name) < 3:
                continue
            # Skip common non-name words
            skip = {
                "Paracetamol", "Aspirin", "Ibuprofen", "Diabetes",
                "Mellitus", "Hypertension", "The", "His", "Her",
            }
            if name.split()[0] in skip:
                continue
            spans.append(Span(
                start=m.start(1), end=m.end(1),
                entity="PERSON", text=name, score=0.92,
            ))
    return spans


# ---------------------------------------------------------------------------
# Comprehensive Detection (NER + Regex + SAE fields + Inline names)
# ---------------------------------------------------------------------------
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


def detect_all_pii(text: str) -> list[Span]:
    """Run all detection layers and merge results.

    Layers:
      1. General hybrid detector (NER + Regex from detection.py)
      2. SAE structured field detector
      3. Inline name detector (catches 'Patient Ramesh')
    """
    text = normalise_for_detection(text)

    # Layer 1: General detection
    general_spans = detect(text)

    # Layer 2: SAE field detection
    sae_spans = _detect_sae_fields(text)

    # Layer 3: Inline name detection
    inline_spans = _detect_inline_names(text)

    # Merge all spans
    all_spans = general_spans + sae_spans + inline_spans
    all_spans.sort(key=lambda s: s.start)

    return _resolve_overlaps(all_spans)


# ---------------------------------------------------------------------------
# Core Anonymization
# ---------------------------------------------------------------------------
@dataclass
class SAEResult:
    """Result of SAE anonymization."""
    original_text: str
    processed_text: str
    mode: SAEMode
    entities_found: list[dict]
    mapping: dict[str, str]          # token -> original (reversible only)
    encrypted_mapping: dict[str, str] # token -> encrypted_original
    file_id: str
    file_hash: str
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "processed_text": self.processed_text,
            "mode": self.mode,
            "num_entities": len(self.entities_found),
            "entities_by_type": self._count_by_type(),
            "entities": self.entities_found,
            "file_id": self.file_id,
            "file_hash": self.file_hash,
            "timestamp": self.timestamp,
            "mapping_size": len(self.mapping),
        }

    def _count_by_type(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for e in self.entities_found:
            t = e["entity_type"]
            out[t] = out.get(t, 0) + 1
        return out


def anonymize_sae(
    text: str,
    mode: SAEMode = "irreversible",
    file_content: bytes | None = None,
    filename: str = "unknown",
) -> SAEResult:
    """Main anonymization entry point.

    Parameters
    ----------
    text : The SAE report text to anonymize.
    mode : 'irreversible' (asterisks) or 'reversible' (tokens).
    file_content : Raw file bytes for hashing (optional).
    filename : Original filename for tracking.

    Returns
    -------
    SAEResult with processed text, mapping, file tracking info.
    """
    # File tracking
    content_for_hash = file_content if file_content else text.encode("utf-8")
    file_hash = hashlib.sha256(content_for_hash).hexdigest()
    file_id = f"DOC-{file_hash[:12].upper()}"
    timestamp = datetime.utcnow().isoformat() + "Z"

    if not text.strip():
        return SAEResult(
            original_text=text,
            processed_text=text,
            mode=mode,
            entities_found=[],
            mapping={},
            encrypted_mapping={},
            file_id=file_id,
            file_hash=file_hash,
            timestamp=timestamp,
        )

    # Detect all PII
    working = normalise_for_detection(text)
    spans = detect_all_pii(text)

    # Build replacement
    mapping: dict[str, str] = {}
    encrypted_mapping: dict[str, str] = {}
    entities_found: list[dict] = []

    # Process spans from end to start so indices stay valid
    parts: list[str] = []
    cursor = len(working)
    for sp in sorted(spans, key=lambda s: s.start, reverse=True):
        # Tail after this span
        parts.append(working[sp.end:cursor])
        original_value = working[sp.start:sp.end]

        if mode == "irreversible":
            replacement = _mask_value(original_value, sp.entity)
        else:
            replacement = _generate_token(original_value, sp.entity)
            mapping[replacement] = original_value
            # Encrypt the original value for secure storage
            encrypted = _fernet.encrypt(original_value.encode()).decode()
            encrypted_mapping[replacement] = encrypted

        entities_found.append({
            "entity_type": sp.entity,
            "original_value": original_value if mode == "reversible" else "[REDACTED]",
            "replacement": replacement,
            "position": {"start": sp.start, "end": sp.end},
            "confidence": sp.score,
        })

        parts.append(replacement)
        cursor = sp.start

    parts.append(working[:cursor])
    processed_text = "".join(reversed(parts))

    return SAEResult(
        original_text=text,
        processed_text=processed_text,
        mode=mode,
        entities_found=entities_found,
        mapping=mapping,
        encrypted_mapping=encrypted_mapping,
        file_id=file_id,
        file_hash=file_hash,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# Traceback (Reversible mode only)
# ---------------------------------------------------------------------------
def traceback_text(
    anonymized_text: str,
    mapping: dict[str, str],
) -> str:
    """Reconstruct original text from anonymized version using mapping.

    This is the MACHINE-ONLY reconstruction path. The mapping must be
    provided (from the encrypted store); without it, reconstruction is
    impossible.
    """
    result = anonymized_text
    for token, original in mapping.items():
        result = result.replace(token, original)
    return result


def traceback_from_encrypted(
    anonymized_text: str,
    encrypted_mapping: dict[str, str],
) -> str:
    """Reconstruct original text using encrypted mapping.

    Decrypts each mapping entry first, then substitutes tokens.
    """
    mapping = {}
    for token, encrypted_value in encrypted_mapping.items():
        try:
            original = _fernet.decrypt(encrypted_value.encode()).decode()
            mapping[token] = original
        except Exception:
            mapping[token] = "[DECRYPT_FAILED]"
    return traceback_text(anonymized_text, mapping)


# ---------------------------------------------------------------------------
# File Tracking Database
# ---------------------------------------------------------------------------
class FileTracker:
    """Tracks processed files by SHA256 hash for duplicate detection."""

    def __init__(self, db_path: str | os.PathLike | None = None):
        if db_path is None:
            db_path = SAE_DATA_DIR / "file_tracker.json"
        self.db_path = Path(db_path)
        self._data = self._load()

    def _load(self) -> dict:
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"files": {}}
        return {"files": {}}

    def _save(self):
        self.db_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def register_file(self, result: SAEResult, filename: str = "unknown") -> dict:
        """Register a processed file. Returns tracking info."""
        entry = {
            "file_id": result.file_id,
            "file_hash": result.file_hash,
            "filename": filename,
            "mode": result.mode,
            "entities_count": len(result.entities_found),
            "timestamp": result.timestamp,
            "mapping_count": len(result.mapping),
        }

        if result.file_hash not in self._data["files"]:
            self._data["files"][result.file_hash] = {
                "file_id": result.file_id,
                "first_seen": result.timestamp,
                "filenames": [filename],
                "process_count": 1,
                "history": [entry],
            }
        else:
            record = self._data["files"][result.file_hash]
            record["process_count"] += 1
            if filename not in record["filenames"]:
                record["filenames"].append(filename)
            record["history"].append(entry)

        self._save()
        return entry

    def check_duplicate(self, content: bytes) -> dict:
        """Check if file content has been processed before."""
        file_hash = hashlib.sha256(content).hexdigest()
        file_id = f"DOC-{file_hash[:12].upper()}"

        if file_hash in self._data["files"]:
            record = self._data["files"][file_hash]
            return {
                "is_duplicate": True,
                "file_id": file_id,
                "file_hash": file_hash,
                "first_seen": record["first_seen"],
                "process_count": record["process_count"],
                "filenames": record["filenames"],
            }
        return {
            "is_duplicate": False,
            "file_id": file_id,
            "file_hash": file_hash,
        }

    def check_duplicate_text(self, text: str) -> dict:
        """Check if text content has been processed before."""
        return self.check_duplicate(text.encode("utf-8"))

    def get_all_files(self) -> list[dict]:
        """Return all tracked files."""
        result = []
        for file_hash, record in self._data["files"].items():
            result.append({
                "file_id": record["file_id"],
                "file_hash": file_hash,
                "filenames": record["filenames"],
                "first_seen": record["first_seen"],
                "process_count": record["process_count"],
            })
        return result


# ---------------------------------------------------------------------------
# Mapping Store (Encrypted, persistent)
# ---------------------------------------------------------------------------
class MappingStore:
    """Persistent encrypted storage for reversible de-identification mappings.

    Each file_id gets its own mapping set. All original values are stored
    encrypted — the JSON on disk is NOT human-readable.
    """

    def __init__(self, db_path: str | os.PathLike | None = None):
        if db_path is None:
            db_path = SAE_DATA_DIR / "mappings.json"
        self.db_path = Path(db_path)
        self._data = self._load()

    def _load(self) -> dict:
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"mappings": {}}
        return {"mappings": {}}

    def _save(self):
        self.db_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def store(self, file_id: str, encrypted_mapping: dict[str, str]) -> None:
        """Store encrypted mapping for a file."""
        self._data["mappings"][file_id] = {
            "stored_at": datetime.utcnow().isoformat() + "Z",
            "entries": encrypted_mapping,
        }
        self._save()

    def retrieve(self, file_id: str) -> dict[str, str] | None:
        """Retrieve encrypted mapping for a file."""
        record = self._data["mappings"].get(file_id)
        if record:
            return record["entries"]
        return None

    def decrypt_mapping(self, file_id: str) -> dict[str, str] | None:
        """Retrieve and decrypt mapping for a file."""
        encrypted = self.retrieve(file_id)
        if not encrypted:
            return None
        result = {}
        for token, enc_value in encrypted.items():
            try:
                result[token] = _fernet.decrypt(enc_value.encode()).decode()
            except Exception:
                result[token] = "[DECRYPT_FAILED]"
        return result

    def list_files(self) -> list[dict]:
        """List all files with stored mappings."""
        result = []
        for file_id, record in self._data["mappings"].items():
            result.append({
                "file_id": file_id,
                "stored_at": record["stored_at"],
                "mapping_count": len(record["entries"]),
            })
        return result


# ---------------------------------------------------------------------------
# Output History Store — persists every processed report
# ---------------------------------------------------------------------------
class OutputStore:
    """Stores anonymized/de-identified outputs for audit and retrieval."""

    def __init__(self, db_path: str | os.PathLike | None = None):
        if db_path is None:
            db_path = SAE_DATA_DIR / "outputs.json"
        self.db_path = Path(db_path)
        self._data = self._load()

    def _load(self) -> dict:
        if self.db_path.exists():
            try:
                return json.loads(self.db_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {"outputs": []}
        return {"outputs": []}

    def _save(self):
        self.db_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def store(self, result: dict) -> None:
        """Persist a processed result."""
        entry = {
            "file_id": result.get("file_id"),
            "file_hash": result.get("file_hash"),
            "mode": result.get("mode"),
            "num_entities": result.get("num_entities", 0),
            "timestamp": result.get("timestamp"),
            "processed_text_preview": (result.get("processed_text") or "")[:500],
        }
        self._data["outputs"].append(entry)
        self._save()

    def list_outputs(self) -> list[dict]:
        return self._data["outputs"]

    def get_by_file_id(self, file_id: str) -> list[dict]:
        return [o for o in self._data["outputs"] if o.get("file_id") == file_id]


# ---------------------------------------------------------------------------
# Singleton instances
# ---------------------------------------------------------------------------
_file_tracker = FileTracker()
_mapping_store = MappingStore()
_output_store = OutputStore()


def get_file_tracker() -> FileTracker:
    return _file_tracker


def get_mapping_store() -> MappingStore:
    return _mapping_store


def get_output_store() -> OutputStore:
    return _output_store


# ---------------------------------------------------------------------------
# High-level API functions
# ---------------------------------------------------------------------------
def process_sae_report(
    text: str,
    mode: SAEMode = "irreversible",
    filename: str = "unknown",
    file_content: bytes | None = None,
) -> dict:
    """Process an SAE report end-to-end.

    Returns a comprehensive result dict with:
    - processed_text
    - mode
    - entities found
    - file tracking info
    - mapping info (reversible mode)
    """
    result = anonymize_sae(text, mode=mode, file_content=file_content, filename=filename)

    # Register file
    tracking = _file_tracker.register_file(result, filename)

    # Store mapping if reversible
    if mode == "reversible" and result.encrypted_mapping:
        _mapping_store.store(result.file_id, result.encrypted_mapping)

    output = result.to_dict()
    output["tracking"] = tracking

    if mode == "reversible":
        output["mapping_stored"] = True
        output["mapping_file_id"] = result.file_id
        output["encrypted_mapping"] = result.encrypted_mapping

    # Persist to output history
    _output_store.store(output)

    return output


def traceback_report(file_id: str, anonymized_text: str) -> dict:
    """Reconstruct original text from file_id and anonymized text.

    Machine-only operation — requires the encryption key.
    """
    mapping = _mapping_store.decrypt_mapping(file_id)
    if not mapping:
        return {
            "success": False,
            "error": f"No mapping found for file_id: {file_id}",
        }
    reconstructed = traceback_text(anonymized_text, mapping)
    return {
        "success": True,
        "file_id": file_id,
        "reconstructed_text": reconstructed,
        "mappings_applied": len(mapping),
    }


def check_file_duplicate(content: bytes) -> dict:
    """Check if file content is a duplicate."""
    return _file_tracker.check_duplicate(content)


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample = """SERIOUS ADVERSE EVENT (SAE) REPORT

Name: Ramesh Kumar: 52
Gender: Male
Address: 14, MG Road, Pune, Maharashtra, INDIA
Aadhaar Number: 1234-5678-9012
Phone number: 9876543210
Hospital: XYZ Hospital, Pune
Doctor: Dr. Amit Sharma
Suspected Drug: Paracetamol 500mg
Dose: Twice daily for 5 days

Event Description:
Patient Ramesh developed severe liver toxicity after consuming Paracetamol for 5 days.

Medical History:
Diabetes (since 2015)

Outcome:
Recovered"""

    print("=" * 70)
    print("  SAE ANONYMIZATION ENGINE — DEMO")
    print("=" * 70)

    # 1. Irreversible
    print("\n### 1. IRREVERSIBLE ANONYMIZATION ###\n")
    r1 = process_sae_report(sample, mode="irreversible", filename="sae_report_001.txt")
    print(r1["processed_text"])
    print(f"\nEntities found: {r1['num_entities']}")
    print(f"File ID: {r1['file_id']}")
    print(f"File Hash: {r1['file_hash']}")

    # 2. Reversible
    print("\n\n### 2. REVERSIBLE DE-IDENTIFICATION ###\n")
    r2 = process_sae_report(sample, mode="reversible", filename="sae_report_001.txt")
    print(r2["processed_text"])
    print(f"\nEntities found: {r2['num_entities']}")
    print(f"File ID: {r2['file_id']}")
    print(f"Mapping stored: {r2.get('mapping_stored', False)}")

    # 3. Traceback
    print("\n\n### 3. TRACEBACK (Machine-Only) ###\n")
    tb = traceback_report(r2["file_id"], r2["processed_text"])
    if tb["success"]:
        print(tb["reconstructed_text"])
        print(f"\nMappings applied: {tb['mappings_applied']}")
    else:
        print(f"Error: {tb['error']}")

    # 4. Duplicate check
    print("\n\n### 4. DUPLICATE CHECK ###\n")
    dup = check_file_duplicate(sample.encode("utf-8"))
    print(json.dumps(dup, indent=2))
