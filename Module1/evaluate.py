"""
Module 1 — Detection Evaluation Harness
========================================
Scores the PII/PHI detector against ground-truth spans and reports
entity-level Precision, Recall, and F1 — the metrics the hackathon
rubric requires (FUNSD-style, strict entity-level matching).

Usage
-----
    # Quick: evaluate against synthetic data (no downloads needed)
    python evaluate.py

    # With a custom test set
    python evaluate.py --dataset my_labels.jsonl

    # Larger synthetic sample, specific seed
    python evaluate.py --n 500 --seed 7

JSONL input format
------------------
Each line is one sample:
    {"text": "...", "spans": [{"start":0,"end":5,"entity":"PERSON"}, ...]}

Matching rules
--------------
A predicted span is a TRUE POSITIVE iff it matches a ground-truth span
on all three of: start, end, entity type. This is the strict/exact-match
regime the FUNSD benchmark uses. Partial overlap is counted as FP + FN.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from detection import detect
from synthetic import generate_dataset


# --------------------------------------------------------------------------- #
# Core scoring                                                                #
# --------------------------------------------------------------------------- #
def _span_key(s) -> tuple:
    """Normalise both Span objects and dicts to (start, end, entity)."""
    if isinstance(s, dict):
        return (s["start"], s["end"], s["entity"])
    return (s.start, s.end, s.entity)


def score_dataset(dataset: list[tuple[str, list[dict]]]
                  ) -> dict:
    """Run detection over every sample and return a full metrics report."""
    tp_by_entity: dict[str, int] = defaultdict(int)
    fp_by_entity: dict[str, int] = defaultdict(int)
    fn_by_entity: dict[str, int] = defaultdict(int)

    total_truth = 0
    total_pred = 0

    for text, truth_spans in dataset:
        truth_set = {_span_key(s) for s in truth_spans}
        pred_spans = detect(text)
        pred_set = {_span_key(s) for s in pred_spans}

        total_truth += len(truth_set)
        total_pred += len(pred_set)

        for key in pred_set & truth_set:
            tp_by_entity[key[2]] += 1
        for key in pred_set - truth_set:
            fp_by_entity[key[2]] += 1
        for key in truth_set - pred_set:
            fn_by_entity[key[2]] += 1

    # Per-entity metrics
    entity_types = set(tp_by_entity) | set(fp_by_entity) | set(fn_by_entity)
    per_entity: dict[str, dict] = {}
    macro_p = macro_r = macro_f = 0.0
    for ent in sorted(entity_types):
        tp = tp_by_entity[ent]
        fp = fp_by_entity[ent]
        fn = fn_by_entity[ent]
        p = tp / (tp + fp) if (tp + fp) else 0.0
        r = tp / (tp + fn) if (tp + fn) else 0.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        per_entity[ent] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 4),
            "recall":    round(r, 4),
            "f1":        round(f, 4),
        }
        macro_p += p
        macro_r += r
        macro_f += f

    n_entities = max(len(entity_types), 1)
    macro = {
        "precision": round(macro_p / n_entities, 4),
        "recall":    round(macro_r / n_entities, 4),
        "f1":        round(macro_f / n_entities, 4),
    }

    # Micro (global)
    tp_total = sum(tp_by_entity.values())
    fp_total = sum(fp_by_entity.values())
    fn_total = sum(fn_by_entity.values())
    mp = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
    mr = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
    mf = 2 * mp * mr / (mp + mr) if (mp + mr) else 0.0
    micro = {
        "precision": round(mp, 4),
        "recall":    round(mr, 4),
        "f1":        round(mf, 4),
    }

    return {
        "num_samples": len(dataset),
        "total_truth_spans": total_truth,
        "total_predicted_spans": total_pred,
        "micro": micro,
        "macro": macro,
        "per_entity": per_entity,
    }


# --------------------------------------------------------------------------- #
# Pretty-print                                                                #
# --------------------------------------------------------------------------- #
def print_report(report: dict) -> None:
    print("\n" + "=" * 72)
    print("  DETECTION EVALUATION REPORT")
    print("=" * 72)
    print(f"  Samples           : {report['num_samples']}")
    print(f"  Ground-truth spans: {report['total_truth_spans']}")
    print(f"  Predicted spans   : {report['total_predicted_spans']}")

    print("\n  " + "-" * 68)
    print(f"  {'Entity':<18}{'TP':>6}{'FP':>6}{'FN':>6}"
          f"{'Prec':>10}{'Recall':>10}{'F1':>10}")
    print("  " + "-" * 68)
    for ent, m in report["per_entity"].items():
        print(f"  {ent:<18}{m['tp']:>6}{m['fp']:>6}{m['fn']:>6}"
              f"{m['precision']:>10.3f}{m['recall']:>10.3f}{m['f1']:>10.3f}")
    print("  " + "-" * 68)

    micro = report["micro"]
    macro = report["macro"]
    print(f"  {'MICRO':<18}{'':>18}"
          f"{micro['precision']:>10.3f}{micro['recall']:>10.3f}"
          f"{micro['f1']:>10.3f}")
    print(f"  {'MACRO':<18}{'':>18}"
          f"{macro['precision']:>10.3f}{macro['recall']:>10.3f}"
          f"{macro['f1']:>10.3f}")
    print("=" * 72)


# --------------------------------------------------------------------------- #
# Custom-dataset loader                                                       #
# --------------------------------------------------------------------------- #
def load_jsonl(path: Path) -> list[tuple[str, list[dict]]]:
    out: list[tuple[str, list[dict]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        out.append((obj["text"], obj.get("spans", [])))
    return out


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Module 1 detection against ground-truth spans"
    )
    parser.add_argument("--dataset", type=str,
                        help="JSONL test set; if omitted, uses synthetic data")
    parser.add_argument("--n", type=int, default=200,
                        help="Synthetic sample count (default: 200)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--save", type=str,
                        help="Save the full report to a JSON file")
    args = parser.parse_args()

    if args.dataset:
        dataset = load_jsonl(Path(args.dataset))
        print(f"Loaded {len(dataset)} samples from {args.dataset}")
    else:
        dataset = generate_dataset(n=args.n, seed=args.seed)
        print(f"Generated {len(dataset)} synthetic samples (seed={args.seed})")

    report = score_dataset(dataset)
    print_report(report)

    if args.save:
        Path(args.save).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport saved to {args.save}")


if __name__ == "__main__":
    main()
