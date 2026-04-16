"""
Module 1 — Synthetic Indian Regulatory Data Generator
======================================================
Produces realistic-looking CDSCO-style narratives with known ground-truth
PII spans, so you can evaluate detection without needing the i2b2 dataset
(which requires a DUA) or real CDSCO data (which you get on the secure
server in Stage 2).

Usage
-----
    from synthetic import generate_dataset
    samples = generate_dataset(n=100, seed=42)
    for text, spans in samples:
        ...

Each sample is a (text, spans) tuple where `spans` is a list of
{start, end, entity, text} dicts — the same shape `detection.Span` uses.

No heavy deps: Faker is used if installed, otherwise a stdlib fallback
generates equally valid synthetic identifiers.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass
from typing import Callable


# --------------------------------------------------------------------------- #
# Identifier generators (stdlib-only)                                         #
# --------------------------------------------------------------------------- #
INDIAN_FIRST_NAMES = [
    "Rajesh", "Priya", "Amit", "Sunita", "Vikram", "Anjali", "Sanjay",
    "Deepika", "Arjun", "Kavita", "Ravi", "Meera", "Suresh", "Neha",
    "Manoj", "Pooja", "Karthik", "Lakshmi", "Ashok", "Divya", "Rahul",
    "Shruti", "Nitin", "Geeta", "Harish", "Anita", "Kiran", "Sneha",
]
INDIAN_LAST_NAMES = [
    "Sharma", "Kumar", "Patel", "Reddy", "Singh", "Iyer", "Menon",
    "Nair", "Gupta", "Shah", "Rao", "Bose", "Das", "Joshi", "Mehta",
    "Desai", "Kapoor", "Malhotra", "Chopra", "Agarwal", "Mishra",
]
INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata", "Hyderabad",
    "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Kochi", "Nagpur",
]
INDIAN_HOSPITALS = [
    "AIIMS Delhi", "Tata Memorial Hospital", "Apollo Hospitals",
    "Fortis Hospital", "Kokilaben Hospital", "PGIMER Chandigarh",
    "CMC Vellore", "NIMHANS Bengaluru", "Max Super Speciality",
]
DRUGS = [
    "Paracetamol 500mg", "Atorvastatin 20mg", "Metformin 850mg",
    "Amlodipine 5mg", "Omeprazole 40mg", "Losartan 50mg",
    "Ciprofloxacin 500mg", "Azithromycin 250mg",
]
ADVERSE_EVENTS = [
    "severe headache", "nausea and vomiting", "skin rash",
    "elevated liver enzymes", "hypotension", "tachycardia",
    "allergic reaction", "dizziness", "chest pain",
]


def _gen_aadhaar(rng: random.Random) -> str:
    # Format XXXX XXXX XXXX — not Verhoeff-valid but lexically realistic
    return f"{rng.randint(1000, 9999)} {rng.randint(1000, 9999)} {rng.randint(1000, 9999)}"


def _gen_pan(rng: random.Random) -> str:
    letters = "".join(rng.choices(string.ascii_uppercase, k=5))
    digits = "".join(rng.choices(string.digits, k=4))
    return f"{letters}{digits}{rng.choice(string.ascii_uppercase)}"


def _gen_phone(rng: random.Random) -> str:
    return f"+91-{rng.choice('6789')}{''.join(rng.choices(string.digits, k=9))}"


def _gen_email(first: str, last: str, rng: random.Random) -> str:
    domain = rng.choice(["example.com", "mail.in", "hospital.org", "test.co.in"])
    sep = rng.choice([".", "_", ""])
    return f"{first.lower()}{sep}{last.lower()}@{domain}"


def _gen_date(rng: random.Random) -> str:
    day = rng.randint(1, 28)
    month = rng.randint(1, 12)
    year = rng.randint(2018, 2025)
    fmt = rng.choice(["{:02d}/{:02d}/{}", "{:02d}-{:02d}-{}", "{}-{:02d}-{:02d}"])
    if fmt.startswith("{:02d}"):
        return fmt.format(day, month, year)
    return fmt.format(year, month, day)


def _gen_drug_id(rng: random.Random) -> str:
    return f"IND-{rng.randint(10000, 99999)}"


def _gen_cdsco_file(rng: random.Random) -> str:
    dept = rng.choice(["NDD", "BIO", "CT", "MD", "SAE"])
    return f"CDSCO/{dept}/{rng.randint(2020, 2025)}/{rng.randint(100, 999):03d}"


def _gen_mrn(rng: random.Random) -> str:
    return f"MRN{rng.randint(100000, 9999999)}"


# --------------------------------------------------------------------------- #
# Narrative templates                                                         #
# --------------------------------------------------------------------------- #
@dataclass
class Slot:
    name: str          # placeholder key in the template, e.g. "{NAME}"
    entity: str        # what detection.py should tag this as
    generator: Callable[[random.Random], str]


def _name_slot(rng: random.Random) -> tuple[str, str, str]:
    first = rng.choice(INDIAN_FIRST_NAMES)
    last = rng.choice(INDIAN_LAST_NAMES)
    return first, last, f"{first} {last}"


# Each template is a string with {SLOTS}. The filler replaces them and
# tracks the final character offsets.
TEMPLATES = [
    (
        "Patient {NAME} (Aadhaar {AADHAAR}, PAN {PAN}) was admitted to "
        "{HOSPITAL} on {DATE}. Contact number {PHONE}, email {EMAIL}. "
        "Reported {EVENT} after {DRUG}. Trial reference {DRUG_ID}, "
        "CDSCO file {CDSCO_FILE}."
    ),
    (
        "SAE Report: {NAME} ({MRN}) experienced {EVENT} on {DATE}. "
        "The patient, resident of {CITY}, was prescribed {DRUG} as part "
        "of trial {DRUG_ID}. Notification dispatched to {EMAIL}."
    ),
    (
        "Clinical trial file {CDSCO_FILE} includes data for subject "
        "{NAME} (Aadhaar {AADHAAR}) at {HOSPITAL}. Screening date {DATE}. "
        "Reachable at {PHONE}."
    ),
    (
        "Inspection memo dated {DATE}: Visited {HOSPITAL} in {CITY}. "
        "Met with PI {NAME}, reviewed records for {DRUG} (IND {DRUG_ID}). "
        "PI contact: {EMAIL} / {PHONE}."
    ),
    (
        "{NAME}, PAN {PAN}, filed an adverse event report on {DATE}. "
        "Observed {EVENT} following administration of {DRUG}. "
        "Record ID {MRN}. Follow-up scheduled at {HOSPITAL}."
    ),
]


# --------------------------------------------------------------------------- #
# Core sample generator                                                       #
# --------------------------------------------------------------------------- #
def generate_sample(rng: random.Random | None = None) -> tuple[str, list[dict]]:
    """Fill a random template and return (text, ground_truth_spans)."""
    rng = rng or random.Random()
    template = rng.choice(TEMPLATES)

    first, last, full_name = _name_slot(rng)
    city = rng.choice(INDIAN_CITIES)
    hospital = rng.choice(INDIAN_HOSPITALS)

    fills = {
        "{NAME}":       (full_name,                "PERSON"),
        "{AADHAAR}":    (_gen_aadhaar(rng),        "AADHAAR"),
        "{PAN}":        (_gen_pan(rng),            "PAN"),
        "{PHONE}":      (_gen_phone(rng),          "IN_PHONE"),
        "{EMAIL}":      (_gen_email(first, last, rng), "EMAIL_ADDRESS"),
        "{DATE}":       (_gen_date(rng),           "DATE_TIME"),
        "{DRUG_ID}":    (_gen_drug_id(rng),        "DRUG_ID"),
        "{CDSCO_FILE}": (_gen_cdsco_file(rng),     "CDSCO_FILE"),
        "{MRN}":        (_gen_mrn(rng),            "MRN"),
        "{HOSPITAL}":   (hospital,                 "ORGANIZATION"),
        "{CITY}":       (city,                     "LOCATION"),
        "{EVENT}":      (rng.choice(ADVERSE_EVENTS), None),
        "{DRUG}":       (rng.choice(DRUGS),        None),
    }

    # Walk the template, substituting placeholders and recording offsets
    out: list[str] = []
    spans: list[dict] = []
    i = 0
    pos = 0
    while i < len(template):
        if template[i] == "{":
            end = template.find("}", i)
            if end == -1:
                out.append(template[i:])
                break
            key = template[i:end + 1]
            if key in fills:
                value, entity = fills[key]
                if entity is not None:
                    spans.append({
                        "start": pos,
                        "end": pos + len(value),
                        "entity": entity,
                        "text": value,
                    })
                out.append(value)
                pos += len(value)
                i = end + 1
                continue
        out.append(template[i])
        pos += 1
        i += 1

    return "".join(out), spans


def generate_dataset(n: int = 100, seed: int | None = None
                     ) -> list[tuple[str, list[dict]]]:
    """Generate `n` synthetic samples with ground-truth spans."""
    rng = random.Random(seed)
    return [generate_sample(rng) for _ in range(n)]


if __name__ == "__main__":
    import json
    dataset = generate_dataset(n=3, seed=42)
    for i, (text, spans) in enumerate(dataset, 1):
        print(f"\n--- SAMPLE {i} ---")
        print(text)
        print(f"  {len(spans)} ground-truth spans:")
        for s in spans:
            print(f"    {s['entity']:<15} {s['text']}")
