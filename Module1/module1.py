"""
Module 1 — Orchestrator
=======================
Ties ingestion + detection + anonymisation + (optional) k-anonymity into
a single `run()` function that downstream modules consume.

Output JSON schema is the stable contract Module 2+ depend on. See the
docstring in pipeline.py for the full shape.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Sequence

from anonymizer import anonymise
from ingestion import PathLike, ingest, ingest_as, ingest_text

OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


# --------------------------------------------------------------------------- #
# Structured-row anonymisation                                                #
# --------------------------------------------------------------------------- #
def _anonymise_rows(rows: list[dict], mode: str) -> tuple[list[dict], int]:
    """Run anonymisation cell-by-cell on tabular rows."""
    out_rows: list[dict] = []
    total = 0
    for row in rows:
        new_row: dict[str, Any] = {}
        for col, val in row.items():
            if val is None or not isinstance(val, (str, int, float)):
                new_row[col] = val
                continue
            s = str(val)
            if not s.strip():
                new_row[col] = val
                continue
            res = anonymise(s, mode=mode)
            total += len(res.spans)
            new_row[col] = res.anonymised_text
        out_rows.append(new_row)
    return out_rows, total


# --------------------------------------------------------------------------- #
# Main entry point                                                            #
# --------------------------------------------------------------------------- #
def run(
    source: PathLike | str,
    *,
    mode: str = "two_step",
    inline: bool = False,
    forced_type: str | None = None,
    quasi_identifiers: Sequence[str] | None = None,
    save: bool = True,
) -> dict:
    """Run Module 1 end-to-end.

    Parameters
    ----------
    source : file path, or raw text if `inline=True`.
    mode   : "pseudonymise" | "generalise" | "two_step" (default).
    inline : treat `source` as raw text.
    forced_type : override extension-based dispatch (e.g. "pdf", "image",
                  "csv"). Ignored if `inline=True`.
    quasi_identifiers : column names for k-anonymity (tabular only).
    save   : write JSON artifact to Module1/outputs/.
    """
    # 1. Ingest
    if inline:
        ingested = ingest_text(str(source))
    elif forced_type and forced_type not in ("auto", "inline"):
        ingested = ingest_as(source, forced_type)
    else:
        ingested = ingest(source)

    # 2. Anonymise unstructured text
    text_result = anonymise(ingested["text"] or "", mode=mode)

    # 3. Anonymise structured rows if present
    structured_anon: list[dict] | None = None
    extra_entity_count = 0
    if ingested.get("structured"):
        structured_anon, extra_entity_count = _anonymise_rows(
            ingested["structured"], mode=mode
        )

    # 4. Optional k-anonymity
    k_anon_value: int | None = None
    if structured_anon and quasi_identifiers:
        try:
            import pandas as pd
            from metrics import k_anonymity
            df = pd.DataFrame(structured_anon)
            missing = [q for q in quasi_identifiers if q not in df.columns]
            if not missing:
                k_anon_value = k_anonymity(df, quasi_identifiers)
        except Exception:
            k_anon_value = None

    # 5. Build output
    output = {
        "module": "module1_anonymisation",
        "version": "0.1",
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        "input": {
            "source": ingested["source"],
            "source_type": ingested["source_type"],
            "is_scanned": ingested["is_scanned"],
            "metadata": ingested.get("metadata", {}),
        },
        "output": {
            "anonymised_text": text_result.anonymised_text,
            "mode": text_result.mode,
            "num_entities_detected": len(text_result.spans) + extra_entity_count,
            "entities_by_type": _count_by_type(text_result.spans),
            "spans": [
                {"start": s.start, "end": s.end,
                 "entity": s.entity, "score": round(s.score, 3)}
                for s in text_result.spans
            ],
            "structured_anonymised": structured_anon,
            "vault_size": len(text_result.vault),
        },
        "compliance": {
            "two_step_applied": mode == "two_step",
            "k_anonymity": k_anon_value,
            "quasi_identifiers": list(quasi_identifiers) if quasi_identifiers else None,
        },
    }

    # 6. Persist
    if save:
        ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        src_name = Path(ingested["source"]).stem if not inline else "inline"
        # Sanitise filename
        src_name = "".join(c if c.isalnum() or c in "-_" else "_"
                           for c in src_name)[:50]
        out_path = OUTPUT_DIR / f"module1_{src_name}_{ts}.json"
        out_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        output["_artifact_path"] = str(out_path)

    return output


def _count_by_type(spans) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in spans:
        out[s.entity] = out.get(s.entity, 0) + 1
    return out


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python module1.py <file_or_text> [--inline] [--mode MODE]")
        sys.exit(1)

    args = sys.argv[1:]
    inline = "--inline" in args
    if inline:
        args.remove("--inline")
    mode = "two_step"
    if "--mode" in args:
        i = args.index("--mode")
        mode = args[i + 1]
        args.pop(i); args.pop(i)

    result = run(args[0], mode=mode, inline=inline)
    summary = {k: v for k, v in result.items() if k != "output"}
    print(json.dumps(summary, indent=2, default=str))
    print("\n--- ANONYMISED TEXT (first 1500 chars) ---")
    print((result["output"]["anonymised_text"] or "")[:1500])
    print(f"\nArtifact saved to: {result.get('_artifact_path')}")
