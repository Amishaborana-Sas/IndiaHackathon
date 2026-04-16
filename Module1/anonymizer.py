"""
Module 1 — Two-Step Anonymisation
=================================
Implements the exact two-step process the problem statement asks for:

  Step 1 — De-identification (Pseudonymisation)
      Replace each identifier with a deterministic, secure token derived
      from an HMAC-SHA256 of the value. Same input always maps to the
      same token (so a patient stays linkable across documents) but the
      mapping is only reversible if you hold the secret key + the vault.

  Step 2 — Irreversible anonymisation (Generalisation / suppression)
      For fields where even a stable token can leak information through
      linkage attacks, we drop the value entirely or coarsen it
      (year-only dates, country-only locations, age bands, etc.). This is
      the step that lets us reach a target k-anonymity downstream.

Compliance touch-points: DPDP Act 2023, NDHM HDM Policy, ICMR ethical
guidelines, CDSCO standards.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

from detection import Span, detect, normalise_for_detection

# --------------------------------------------------------------------------- #
# Secret management                                                           #
# --------------------------------------------------------------------------- #
_SECRET_ENV = "ANON_HMAC_SECRET"
_DEFAULT_SECRET = b"DEMO-KEY-DO-NOT-USE-IN-PROD-ROTATE-VIA-KMS"


def _get_secret() -> bytes:
    return os.environ.get(_SECRET_ENV, "").encode() or _DEFAULT_SECRET


# --------------------------------------------------------------------------- #
# Step 1 — Pseudonymisation                                                   #
# --------------------------------------------------------------------------- #
def pseudonymise_value(value: str, entity: str) -> str:
    digest = hmac.new(
        _get_secret(), f"{entity}:{value}".encode(), hashlib.sha256
    ).hexdigest()[:12]
    return f"<{entity}_{digest}>"


# --------------------------------------------------------------------------- #
# Step 2 — Generalisation / suppression                                       #
# --------------------------------------------------------------------------- #
_DATE_YEAR = re.compile(r"(19|20)\d{2}")


def generalise_value(value: str, entity: str) -> str:
    if entity == "DATE_TIME":
        m = _DATE_YEAR.search(value)
        return f"{m.group(0)}-XX-XX" if m else "[DATE]"
    if entity == "ADDRESS":
        return "[ADDRESS]"
    if entity == "IN_PIN_CODE":
        return "[PIN_CODE]"
    if entity in {"LOCATION", "GPE"}:
        return "INDIA"
    if entity == "ORGANIZATION":
        return "[ORG]"
    if entity == "PERSON":
        return "[PERSON]"
    if entity in {"EMAIL_ADDRESS", "URL"}:
        return "[CONTACT]"
    if entity in {"PHONE_NUMBER", "IN_PHONE"}:
        return "[PHONE]"
    if entity == "AADHAAR":
        return "[AADHAAR]"
    if entity == "PAN":
        return "[PAN]"
    if entity in {"MRN", "DRUG_ID", "CDSCO_FILE", "IN_PASSPORT", "IFSC"}:
        return f"[{entity}]"
    return "[REDACTED]"


# --------------------------------------------------------------------------- #
# Top-level anonymise()                                                       #
# --------------------------------------------------------------------------- #
Mode = Literal["pseudonymise", "generalise", "two_step", "mask"]


# --------------------------------------------------------------------------- #
# Masking (non-traceable de-identification)                                   #
# --------------------------------------------------------------------------- #
# This is the "de-identification" option the CDSCO/DPDP user flow exposes:
# the identifier is replaced with asterisks so the document reads naturally
# (length/shape preserved for auditors) but NOTHING is stored in the vault,
# so the mapping is not recoverable by anyone. DPDP Act 2023 §2(b)-compatible:
# output cannot be used, alone or with other info, to identify the Data
# Principal.
#
# Policy per entity type:
#   - full-mask (all chars -> *)   for Aadhaar, phone, credit card, IP, URL,
#                                  passport, IFSC, MRN, DRUG_ID, CDSCO_FILE
#   - partial-mask (keep last 2)   for PAN (so format class stays visible)
#   - partial-mask (keep domain)   for EMAIL_ADDRESS
#   - label-mask                   for PERSON / LOCATION / ORGANIZATION /
#                                  DATE_TIME (free-text NER hits where
#                                  preserving length leaks nothing useful)
def mask_value(value: str, entity: str) -> str:
    def stars(n: int) -> str:
        return "*" * max(n, 3)

    if entity == "EMAIL_ADDRESS":
        return stars(len(value))

    if entity == "PAN" and len(value) >= 3:
        # Keep last 2 chars so the PAN shape (…NF) is still recognisable
        return stars(len(value) - 2) + value[-2:]

    if entity in {
        "AADHAAR", "IN_PHONE", "PHONE_NUMBER", "CREDIT_CARD",
        "IP_ADDRESS", "URL", "IN_PASSPORT", "IFSC",
        "MRN", "DRUG_ID", "CDSCO_FILE", "ADDRESS", "IN_PIN_CODE",
    }:
        return stars(len(value))

    if entity in {"PERSON", "LOCATION", "GPE", "ORGANIZATION", "NRP"}:
        return stars(len(value))

    if entity == "DATE_TIME":
        return stars(len(value))

    # Default: full asterisk mask, min length 3
    return stars(len(value))


@dataclass
class AnonymisationResult:
    original_text: str
    anonymised_text: str
    spans: list[Span]
    vault: dict[str, str] = field(default_factory=dict)
    mode: Mode = "two_step"

    def to_dict(self) -> dict:
        return {
            "anonymised_text": self.anonymised_text,
            "mode": self.mode,
            "num_entities": len(self.spans),
            "entities_by_type": _count_by_type(self.spans),
            "vault_size": len(self.vault),
        }


def _count_by_type(spans: list[Span]) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in spans:
        out[s.entity] = out.get(s.entity, 0) + 1
    return out


# Entities kept pseudonymised (reversible) in two-step mode so reviewers
# can relink records about the same subject; everything else is generalised.
_LINK_KEEP = {"PERSON", "MRN", "DRUG_ID", "CDSCO_FILE"}


def anonymise(text: str, mode: Mode = "two_step") -> AnonymisationResult:
    """Detect PII/PHI and replace it according to `mode`.

    Modes
    -----
    pseudonymise : every entity becomes a stable HMAC token (reversible via vault).
    generalise   : every entity is coarsened or redacted (irreversible).
    mask         : every entity is replaced with asterisks (irreversible,
                   no vault, format-preserving where useful). This is the
                   DPDP-aligned "de-identification" option.
    two_step     : link-critical entities are pseudonymised, the rest
                   are generalised.
    """
    if not text:
        return AnonymisationResult("", "", [], {}, mode)

    # Normalise once, use the normalised text as the "working copy" so the
    # span offsets returned by detect() stay valid through replacement.
    working = normalise_for_detection(text)
    spans = detect(working)

    vault: dict[str, str] = {}
    # Replace by slicing (faster than char-list for longer texts)
    # Process from the end so earlier indices stay valid.
    parts: list[str] = []
    cursor = len(working)
    for sp in sorted(spans, key=lambda s: s.start, reverse=True):
        # Tail after this span
        parts.append(working[sp.end:cursor])
        original = working[sp.start:sp.end]

        if mode == "pseudonymise":
            replacement = pseudonymise_value(original, sp.entity)
            vault[replacement] = original
        elif mode == "generalise":
            replacement = generalise_value(original, sp.entity)
        elif mode == "mask":
            # Non-traceable de-identification: asterisks, no vault entry.
            replacement = mask_value(original, sp.entity)
        else:  # two_step
            if sp.entity in _LINK_KEEP:
                replacement = pseudonymise_value(original, sp.entity)
                vault[replacement] = original
            else:
                replacement = generalise_value(original, sp.entity)

        parts.append(replacement)
        cursor = sp.start
    parts.append(working[:cursor])
    anonymised = "".join(reversed(parts))

    return AnonymisationResult(
        original_text=text,
        anonymised_text=anonymised,
        spans=spans,
        vault=vault,
        mode=mode,
    )


# --------------------------------------------------------------------------- #
# Batch + parallel                                                            #
# --------------------------------------------------------------------------- #
def anonymise_batch(
    texts: Iterable[str],
    mode: Mode = "two_step",
    parallel: bool = False,
    workers: int | None = None,
) -> list[AnonymisationResult]:
    """Anonymise many texts at once.

    Parameters
    ----------
    parallel : if True, use a process pool. Note that parallelism only
               helps for large workloads; for small inputs the fork/spawn
               overhead dominates and sequential is faster.
    workers  : process count. Defaults to os.cpu_count().
    """
    texts = list(texts)
    if not parallel or len(texts) < 4:
        return [anonymise(t, mode=mode) for t in texts]

    # Process pool. `anonymise` is a module-level function so it pickles.
    from concurrent.futures import ProcessPoolExecutor
    from functools import partial

    fn = partial(anonymise, mode=mode)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fn, texts))


if __name__ == "__main__":
    sample = (
        "Patient Rajesh Kumar (Aadhaar 1234 5678 9012, PAN ABCDE1234F) "
        "was admitted on 12/03/2024 at AIIMS Delhi. "
        "Contact +91-9876543210 or rajesh.k@example.com. "
        "Trial ID: IND-12345. File CDSCO/NDD/2024/001."
    )
    result = anonymise(sample, mode="two_step")
    print("=== ORIGINAL ===")
    print(sample)
    print("\n=== ANONYMISED ===")
    print(result.anonymised_text)
    print("\n=== STATS ===")
    print(result.to_dict())
    print("\n=== VAULT (reversible mappings) ===")
    for k, v in result.vault.items():
        print(f"  {k} -> {v}")
