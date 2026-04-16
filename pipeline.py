"""
CDSCO-IndiaAI Hackathon — Interactive Pipeline Orchestrator
===========================================================
Run with no arguments for the full interactive experience:

    python pipeline.py

It will:
  1. Ask what kind of document you have (PDF, image, DOCX, XLSX, CSV,
     JSON, HTML, raw text, or "let me auto-detect").
  2. Ask for the file path (or paste text for inline mode).
  3. Ask which anonymisation mode to use.
  4. Run Module 1 and show a clean summary of detected PII + output.
  5. Ask whether to continue to Module 2, 3, 4, 5 one at a time.

You can still use flags for scripting:

    python pipeline.py path\to\file.pdf --auto
    python pipeline.py path\to\file.pdf --module 1
    python pipeline.py "raw text" --inline
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "Module1"))

# --------------------------------------------------------------------------- #
# Imports guarded so a missing dep gives a clear message                      #
# --------------------------------------------------------------------------- #
try:
    from Module1.module1 import run as run_module1
except Exception as e:
    print("ERROR: could not import Module 1.")
    print(f"  {type(e).__name__}: {e}")
    print("\nMake sure you've installed the base requirements:")
    print("  cd Module1 && pip install -r requirements.txt")
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Pretty-print helpers                                                        #
# --------------------------------------------------------------------------- #
HR = "=" * 72
SUB = "-" * 72


def banner(title: str) -> None:
    print(f"\n{HR}\n  {title}\n{HR}")


def info(msg: str) -> None:
    print(f"  {msg}")


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    ans = input(f"  {prompt}{suffix}: ").strip()
    return ans or (default or "")


def ask_choice(prompt: str, options: list[tuple[str, str]],
               default: int = 1) -> str:
    """Show a numbered menu. Returns the *key* of the chosen option."""
    print(f"\n  {prompt}")
    for i, (_, label) in enumerate(options, 1):
        marker = "*" if i == default else " "
        print(f"   {marker} {i}. {label}")
    while True:
        raw = input(f"\n  Choice [1-{len(options)}, default={default}]: ").strip()
        if not raw:
            return options[default - 1][0]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        print("  Please enter a valid number.")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"  {prompt} [{hint}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        if raw in ("q", "quit", "exit"):
            print("  Exiting.")
            sys.exit(0)


# --------------------------------------------------------------------------- #
# Document-type menu                                                          #
# --------------------------------------------------------------------------- #
DOC_TYPES = [
    ("auto",   "Auto-detect from file extension (recommended)"),
    ("pdf",    "PDF document (digital or scanned — auto-fallback to OCR)"),
    ("image",  "Image / scan (PNG, JPG, TIFF, BMP, WEBP)"),
    ("docx",   "Word document (.docx)"),
    ("xlsx",   "Excel spreadsheet (.xlsx / .xlsm)"),
    ("csv",    "CSV or TSV file"),
    ("json",   "JSON file"),
    ("html",   "HTML / HTM web page"),
    ("txt",    "Plain text / markdown / log file"),
    ("inline", "Paste raw text directly (no file)"),
]


def interactive_select_source() -> tuple[str, str, bool]:
    """Returns (source, forced_type_or_'auto', inline_flag)."""
    banner("CDSCO-India AI Pipeline — Document Type")
    doc_type = ask_choice(
        "What kind of document do you want to process?",
        DOC_TYPES,
        default=1,
    )

    if doc_type == "inline":
        print("\n  Paste your text below. Type a line containing only 'END' "
              "(without quotes) when finished.\n")
        lines: list[str] = []
        while True:
            try:
                line = input("  > " if not lines else "    ")
            except EOFError:
                break
            if line.strip() == "END":
                break
            lines.append(line)
        text = "\n".join(lines).strip()
        if not text:
            print("  No text entered. Exiting.")
            sys.exit(0)
        return text, "inline", True

    # File-based types
    while True:
        path = ask("Enter the file path").strip('"').strip("'")
        if not path:
            print("  Empty path. Try again.")
            continue
        p = Path(path).expanduser()
        if not p.exists():
            print(f"  File not found: {p}")
            if not ask_yes_no("Try again?", default=True):
                sys.exit(0)
            continue
        return str(p), doc_type, False


# --------------------------------------------------------------------------- #
# Anonymisation mode menu                                                     #
# --------------------------------------------------------------------------- #
# The CDSCO / DPDP-facing UX is a clean binary choice:
#
#   1. De-identification  — mask identifiers with asterisks. Format is
#      preserved where useful (email domain stays, PAN suffix stays) but
#      nothing is stored in the vault, so the masked output is NOT
#      traceable back to the Data Principal. Aligns with DPDP Act 2023
#      §2(b) "de-identification" where the resulting data can no longer
#      reasonably identify the individual.
#
#   2. Irreversible anonymisation — generalise / redact every identifier
#      to a category label ([PERSON], [PHONE], INDIA, YYYY-XX-XX…). The
#      original values are irrecoverable and the text is stripped of
#      shape/length cues.
#
# Advanced modes (pseudonymise, two_step) are still reachable via the
# --mode flag and via the REST API, but they are intentionally hidden
# from the interactive menu to match the spec the user asked for.
MODE_OPTIONS = [
    ("mask",
     "De-identification — replace identifiers with ***** "
     "(non-traceable, DPDP-aligned)"),
    ("generalise",
     "Irreversible anonymisation — generalise/redact to category labels"),
]


def interactive_select_mode() -> str:
    print("\n" + SUB)
    print("  Choose the anonymisation process")
    print(SUB)
    print("  1. De-identification")
    print("     - Identifiers are masked with asterisks (e.g. **********).")
    print("     - No vault entry is created, mapping is not recoverable.")
    print("     - Document shape is preserved for human review.")
    print()
    print("  2. Irreversible anonymisation")
    print("     - Identifiers are replaced with category labels")
    print("       (e.g. [PERSON], [PHONE], INDIA, YYYY-XX-XX).")
    print("     - Original values are irrecoverable.")
    print("     - Output is suitable for public release / research sharing.")
    print(SUB)
    while True:
        raw = input("\n  Choice [1 = De-identification, 2 = Anonymisation]: ").strip()
        if raw == "1":
            return "mask"
        if raw == "2":
            return "generalise"
        print("  Please enter 1 or 2.")


# --------------------------------------------------------------------------- #
# Module 1 summary                                                            #
# --------------------------------------------------------------------------- #
def print_module1_summary(result: dict) -> None:
    inp = result["input"]
    out = result["output"]
    comp = result["compliance"]

    print(f"\n  Source        : {inp['source']}")
    print(f"  Type          : {inp['source_type']}  (scanned={inp['is_scanned']})")
    if inp.get("metadata"):
        meta = ", ".join(f"{k}={v}" for k, v in inp["metadata"].items()
                         if not isinstance(v, list))
        if meta:
            print(f"  Metadata      : {meta}")

    print(f"\n  Mode          : {out['mode']}")
    print(f"  Entities      : {out['num_entities_detected']}")
    if out["entities_by_type"]:
        print("  By type       :")
        for ent, n in sorted(out["entities_by_type"].items(),
                             key=lambda x: -x[1]):
            print(f"      {ent:<20} {n}")

    print(f"\n  Vault size    : {out['vault_size']} reversible token(s)")
    print(f"  Two-step      : {comp['two_step_applied']}")
    if comp["k_anonymity"] is not None:
        print(f"  k-anonymity   : {comp['k_anonymity']}")

    print(f"\n  Artifact      : {result.get('_artifact_path', '<not saved>')}")

    text = out["anonymised_text"] or ""
    preview = text[:1200]
    print(f"\n{SUB}\n  ANONYMISED OUTPUT (first 1200 chars)\n{SUB}")
    print(preview + ("…" if len(text) > 1200 else ""))
    print(SUB)


# --------------------------------------------------------------------------- #
# Module runners                                                              #
# --------------------------------------------------------------------------- #
def run_m1(source: str, *, inline: bool, mode: str,
           forced_type: str = "auto") -> dict | None:
    banner("MODULE 1 — AI-Powered Anonymisation")
    info(f"Running on: {source[:80]}{'…' if len(source) > 80 else ''}")
    info(f"Mode: {mode}")
    if forced_type != "auto":
        info(f"Forced type: {forced_type}")

    try:
        result = run_module1(
            source,
            mode=mode,
            inline=inline,
            forced_type=forced_type if forced_type not in ("auto", "inline") else None,
        )
    except FileNotFoundError as e:
        print(f"\n  ERROR: file not found: {e}")
        return None
    except Exception as e:
        print(f"\n  ERROR while running Module 1: {type(e).__name__}: {e}")
        print("\n  Traceback (for debugging):")
        traceback.print_exc()
        return None

    print_module1_summary(result)
    return result


def run_m2(module1_artifact: Path) -> dict:
    banner("MODULE 2 — Document Summarisation  [STUB]")
    info(f"Reading Module 1 artifact: {module1_artifact}")
    data = json.loads(module1_artifact.read_text(encoding="utf-8"))
    text = data["output"]["anonymised_text"] or ""
    info(f"Anonymised text length: {len(text)} chars")
    info("Module 2 is not implemented yet. When built it will produce:")
    info("  - SUGAM checklist summaries")
    info("  - SAE case narration summaries")
    info("  - Meeting transcript summaries")
    return {"module": "module2_summarisation", "status": "not_implemented"}


def run_m3(prev: Path) -> dict:
    banner("MODULE 3 — Completeness Assessment & Diff  [STUB]")
    info("Not implemented yet.")
    return {"module": "module3_completeness", "status": "not_implemented"}


def run_m4(prev: Path) -> dict:
    banner("MODULE 4 — SAE Classification  [STUB]")
    info("Not implemented yet.")
    return {"module": "module4_classification", "status": "not_implemented"}


def run_m5(prev: Path) -> dict:
    banner("MODULE 5 — Inspection Report Generation  [STUB]")
    info("Not implemented yet.")
    return {"module": "module5_inspection", "status": "not_implemented"}


NEXT_MODULES = [
    ("Module 2 (Document Summarisation)",       run_m2),
    ("Module 3 (Completeness & Diff)",          run_m3),
    ("Module 4 (SAE Classification)",           run_m4),
    ("Module 5 (Inspection Report Generation)", run_m5),
]


def chain_next_modules(m1_artifact: Path, auto: bool) -> None:
    for label, runner in NEXT_MODULES:
        print()
        if auto:
            runner(m1_artifact)
            continue
        if not ask_yes_no(f">> Proceed to {label}?", default=False):
            info("Stopping pipeline. Module 1 output is saved above.")
            return
        runner(m1_artifact)
    banner("PIPELINE COMPLETE")


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(
        description="CDSCO-IndiaAI Hackathon pipeline orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", nargs="?",
                        help="File path, or raw text if --inline. "
                             "Omit to run in interactive mode.")
    parser.add_argument("--inline", action="store_true",
                        help="Treat SOURCE as raw text instead of a file")
    parser.add_argument("--type", default="auto",
                        choices=["auto", "pdf", "image", "docx", "xlsx",
                                 "csv", "tsv", "json", "html", "txt"],
                        help="Force a specific document type handler")
    parser.add_argument("--mode", default="mask",
                        choices=["pseudonymise", "generalise", "two_step", "mask"],
                        help="mask=de-identification (default), "
                             "generalise=irreversible anonymisation, "
                             "two_step/pseudonymise=advanced")
    parser.add_argument("--module", type=int, choices=range(1, 6),
                        help="Run only one module")
    parser.add_argument("--from-artifact", type=str,
                        help="Previous module's JSON artifact (for --module 2..5)")
    parser.add_argument("--auto", action="store_true",
                        help="Run full pipeline with no prompts")
    args = parser.parse_args()

    # ---- Single-module resume mode -----------------------------------------
    if args.module and args.module > 1:
        if not args.from_artifact:
            print("ERROR: --module 2..5 requires --from-artifact "
                  "pointing to a previous module's JSON.")
            sys.exit(2)
        runner = NEXT_MODULES[args.module - 2][1]
        runner(Path(args.from_artifact))
        return

    # ---- Interactive mode (no source given) --------------------------------
    if args.source is None:
        banner("CDSCO-India AI Hackathon Pipeline")
        info("Welcome! This will walk you through the anonymisation pipeline.")
        source, forced_type, inline = interactive_select_source()
        mode = interactive_select_mode()
    else:
        source = args.source
        inline = args.inline
        forced_type = args.type
        mode = args.mode

    # ---- Run Module 1 ------------------------------------------------------
    m1 = run_m1(source, inline=inline, mode=mode, forced_type=forced_type)
    if m1 is None:
        sys.exit(1)

    if args.module == 1:
        return

    # ---- Chain to later modules -------------------------------------------
    chain_next_modules(Path(m1["_artifact_path"]), auto=args.auto)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrupted. Goodbye.")
        sys.exit(0)
