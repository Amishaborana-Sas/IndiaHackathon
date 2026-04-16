"""
Module 1 — Privacy Metrics & Enforcement
=========================================
Privacy models: k-anonymity, l-diversity, t-closeness (measurement + enforcement).
Information loss metrics: NCP, Discernability, CAVG.
Equivalence class tracking.

References:
  - Olatunji et al. (2021) "A Review of Anonymization for Healthcare Data"
  - Sepas et al. (2022) "Algorithms to anonymize structured medical and healthcare data"
  - Andrew et al. (2023) "An anonymization-based privacy-preserving data collection protocol"
  - Chong (2021) "Privacy-preserving healthcare informatics: a review"
  - Yang & Wiese (2024) "Privacy-preserving Anonymization of FHIR healthcare data"

pandas is imported lazily so this module can be loaded on systems where
pandas isn't installed — structured-data scoring simply becomes unavailable.
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence


def _require_pandas():
    try:
        import pandas as pd
        return pd
    except ImportError as e:
        raise ImportError(
            "pandas is required for k-anonymity / l-diversity / t-closeness. "
            "Install with: pip install pandas"
        ) from e


# =========================================================================== #
#  PRIVACY MODEL MEASUREMENTS                                                 #
# =========================================================================== #

def k_anonymity(df, quasi_identifiers: Sequence[str]) -> int:
    """Measure k-anonymity: minimum equivalence class size.

    Per Sweeney (2002): A table satisfies k-anonymity if every record is
    indistinguishable from at least k-1 other records w.r.t. quasi-identifiers.
    """
    _require_pandas()
    if not quasi_identifiers:
        raise ValueError("quasi_identifiers must be non-empty")
    sizes = df.groupby(list(quasi_identifiers), dropna=False).size()
    return int(sizes.min()) if len(sizes) else 0


def l_diversity(df, quasi_identifiers: Sequence[str], sensitive_attr: str) -> int:
    """Measure l-diversity: minimum distinct SA values per equivalence class.

    Per Machanavajjhala et al. (2006): Each equivalence class must have at
    least l distinct values for the sensitive attribute.
    """
    _require_pandas()
    grouped = df.groupby(list(quasi_identifiers), dropna=False)[sensitive_attr]
    distinct_counts = grouped.nunique()
    return int(distinct_counts.min()) if len(distinct_counts) else 0


def _distribution(values: Sequence) -> dict:
    counts = Counter(values)
    total = sum(counts.values()) or 1
    return {k: v / total for k, v in counts.items()}


def _total_variation(p: dict, q: dict) -> float:
    keys = set(p) | set(q)
    return 0.5 * sum(abs(p.get(k, 0) - q.get(k, 0)) for k in keys)


def t_closeness(df, quasi_identifiers: Sequence[str], sensitive_attr: str) -> float:
    """Measure t-closeness: max distributional distance between any
    equivalence class and the global SA distribution.

    Per Li et al. (2007): The distance between the distribution of SA in
    each equivalence class and the overall table must be ≤ threshold t.
    Uses Total Variation Distance (TVD).
    """
    _require_pandas()
    global_dist = _distribution(df[sensitive_attr].tolist())
    worst = 0.0
    for _, group in df.groupby(list(quasi_identifiers), dropna=False):
        local_dist = _distribution(group[sensitive_attr].tolist())
        worst = max(worst, _total_variation(local_dist, global_dist))
    return worst


# =========================================================================== #
#  EQUIVALENCE CLASS TRACKING                                                  #
# =========================================================================== #

def equivalence_classes(df, quasi_identifiers: Sequence[str]) -> list[dict]:
    """Return a list of equivalence classes with their members and stats.

    Per Andrew et al. (2023) Definition 5: An equivalence class is the
    collection of records grouped by the same anonymized quasi attributes.
    """
    _require_pandas()
    classes = []
    for qi_values, group in df.groupby(list(quasi_identifiers), dropna=False):
        if not isinstance(qi_values, tuple):
            qi_values = (qi_values,)
        classes.append({
            "qi_values": dict(zip(quasi_identifiers, qi_values)),
            "size": len(group),
            "record_indices": group.index.tolist(),
        })
    return classes


def equivalence_class_summary(df, quasi_identifiers: Sequence[str],
                               sensitive_attr: str | None = None) -> dict:
    """Summary statistics of equivalence classes in the anonymized dataset."""
    _require_pandas()
    ec = equivalence_classes(df, quasi_identifiers)
    sizes = [c["size"] for c in ec]
    summary = {
        "num_equivalence_classes": len(ec),
        "min_class_size": min(sizes) if sizes else 0,
        "max_class_size": max(sizes) if sizes else 0,
        "avg_class_size": round(sum(sizes) / len(sizes), 2) if sizes else 0,
        "total_records": sum(sizes),
    }
    if sensitive_attr:
        # Check l-diversity per class
        diversities = []
        for c in ec:
            group = df.loc[c["record_indices"]]
            diversities.append(group[sensitive_attr].nunique())
        summary["min_l_diversity"] = min(diversities) if diversities else 0
        summary["max_l_diversity"] = max(diversities) if diversities else 0
    return summary


# =========================================================================== #
#  INFORMATION LOSS METRICS                                                    #
#  Per Olatunji et al. (2021) §2.3, Sepas et al. (2022) Discussion            #
# =========================================================================== #

def normalized_certainty_penalty(
    original_df, anonymized_df, quasi_identifiers: Sequence[str]
) -> float:
    """NCP (Normalized Certainty Penalty) — measures generalization loss.

    For each QI attribute, NCP is the ratio of the range lost due to
    generalization to the total range. Lower NCP = better utility.

    Per Xu et al. (2006): NCP is widely used to measure information loss
    in k-anonymity based approaches.
    """
    pd = _require_pandas()
    import numpy as np

    ncp_total = 0.0
    n_attrs = 0

    for qi in quasi_identifiers:
        orig_col = original_df[qi]
        anon_col = anonymized_df[qi]

        # Only compute for numeric columns
        if pd.api.types.is_numeric_dtype(orig_col):
            global_range = orig_col.max() - orig_col.min()
            if global_range == 0:
                continue

            # Group by anonymized values, compute range within each group
            group_penalties = []
            for _, group in anonymized_df.groupby(qi, dropna=False):
                orig_values = original_df.loc[group.index, qi]
                local_range = orig_values.max() - orig_values.min()
                group_penalties.append(local_range / global_range * len(group))

            ncp_total += sum(group_penalties) / len(original_df)
            n_attrs += 1

    return round(ncp_total / max(n_attrs, 1), 4)


def discernability_metric(df, quasi_identifiers: Sequence[str]) -> float:
    """Discernability Metric (DM) — penalizes large equivalence classes.

    Per Bayardo & Agrawal (2005): DM assigns to each record a penalty
    equal to the size of the equivalence class it belongs to.
    DM = sum(|EC_i|^2) for all equivalence classes EC_i.
    Lower DM = better utility (each record is more distinguishable).
    """
    _require_pandas()
    sizes = df.groupby(list(quasi_identifiers), dropna=False).size()
    return float(sum(s * s for s in sizes))


def cavg_metric(df, quasi_identifiers: Sequence[str]) -> float:
    """CAVG (Classification Average) metric — average class size.

    CAVG = (1/n) * sum(|EC_i|^2), normalized by dataset size.
    Lower CAVG = better classification utility.
    """
    _require_pandas()
    n = len(df)
    if n == 0:
        return 0.0
    dm = discernability_metric(df, quasi_identifiers)
    return round(dm / n, 4)


# =========================================================================== #
#  ENFORCEMENT FUNCTIONS                                                       #
#  Per the papers: privacy models should be ENFORCED, not just measured        #
# =========================================================================== #

def enforce_l_diversity(
    df, quasi_identifiers: Sequence[str], sensitive_attr: str,
    target_l: int = 2
) -> "pd.DataFrame":
    """Enforce l-diversity by suppressing records from homogeneous classes.

    Per Machanavajjhala et al. (2006): If an equivalence class doesn't have
    at least l distinct SA values, it's vulnerable to homogeneity attacks.

    This function suppresses (removes) records from equivalence classes that
    fail the l-diversity requirement. Returns the filtered DataFrame.
    """
    pd = _require_pandas()

    keep_mask = pd.Series(True, index=df.index)
    for _, group in df.groupby(list(quasi_identifiers), dropna=False):
        if group[sensitive_attr].nunique() < target_l:
            keep_mask.loc[group.index] = False

    suppressed = df[keep_mask].copy()
    return suppressed


def enforce_t_closeness(
    df, quasi_identifiers: Sequence[str], sensitive_attr: str,
    threshold_t: float = 0.3
) -> "pd.DataFrame":
    """Enforce t-closeness by suppressing classes that exceed threshold.

    Per Li et al. (2007): Classes where the SA distribution diverges too
    far from the global distribution are suppressed.
    """
    pd = _require_pandas()

    global_dist = _distribution(df[sensitive_attr].tolist())
    keep_mask = pd.Series(True, index=df.index)

    for _, group in df.groupby(list(quasi_identifiers), dropna=False):
        local_dist = _distribution(group[sensitive_attr].tolist())
        tvd = _total_variation(local_dist, global_dist)
        if tvd > threshold_t:
            keep_mask.loc[group.index] = False

    return df[keep_mask].copy()


# =========================================================================== #
#  HIPAA SAFE HARBOR 18 IDENTIFIERS COVERAGE CHECK                            #
#  Per Sepas et al. (2022), Chong (2021)                                       #
# =========================================================================== #

# The 18 HIPAA Safe Harbor identifier types
HIPAA_SAFE_HARBOR_18 = {
    "NAMES": "Names",
    "GEOGRAPHIC_DATA": "Geographic data smaller than state (street, city, ZIP, etc.)",
    "DATES": "All dates except year (birth, admission, discharge, death, age >89)",
    "PHONE_NUMBERS": "Phone numbers",
    "FAX_NUMBERS": "Fax numbers",
    "EMAIL_ADDRESSES": "Email addresses",
    "SSN": "Social Security numbers",
    "MRN": "Medical record numbers",
    "HEALTH_PLAN_BENEFICIARY": "Health plan beneficiary numbers",
    "ACCOUNT_NUMBERS": "Account numbers",
    "LICENSE_NUMBERS": "Certificate/license numbers",
    "VEHICLE_IDS": "Vehicle identifiers and serial numbers",
    "DEVICE_IDS": "Device identifiers and serial numbers",
    "URLS": "Web URLs",
    "IP_ADDRESSES": "IP address numbers",
    "BIOMETRIC_IDS": "Biometric identifiers (fingerprints, retinal scans)",
    "FACE_PHOTOS": "Full-face photos and comparable images",
    "OTHER_UNIQUE_IDS": "Any other unique identifying number/code/characteristic",
}

# Mapping of our detection entity types to HIPAA categories
_ENTITY_TO_HIPAA = {
    "PERSON": "NAMES",
    "EMAIL_ADDRESS": "EMAIL_ADDRESSES",
    "IN_PHONE": "PHONE_NUMBERS",
    "URL": "URLS",
    "IP_ADDRESS": "IP_ADDRESSES",
    "DATE_TIME": "DATES",
    "MRN": "MRN",
    "AADHAAR": "OTHER_UNIQUE_IDS",     # Indian equivalent of SSN
    "PAN": "OTHER_UNIQUE_IDS",
    "ADDRESS": "GEOGRAPHIC_DATA",
    "LOCATION": "GEOGRAPHIC_DATA",
    "IN_PIN_CODE": "GEOGRAPHIC_DATA",
    "IN_PASSPORT": "LICENSE_NUMBERS",
    "CREDIT_CARD": "ACCOUNT_NUMBERS",
    "IFSC": "ACCOUNT_NUMBERS",
    "DRUG_ID": "OTHER_UNIQUE_IDS",
    "CDSCO_FILE": "OTHER_UNIQUE_IDS",
    "ORGANIZATION": "OTHER_UNIQUE_IDS",
}


def hipaa_coverage_check(detected_entity_types: set[str]) -> dict:
    """Check which HIPAA Safe Harbor identifiers are covered by detection.

    Returns a dict with 'covered', 'not_covered', and 'coverage_pct'.
    """
    covered_hipaa = set()
    for entity in detected_entity_types:
        hipaa_cat = _ENTITY_TO_HIPAA.get(entity)
        if hipaa_cat:
            covered_hipaa.add(hipaa_cat)

    all_hipaa = set(HIPAA_SAFE_HARBOR_18.keys())
    not_covered = all_hipaa - covered_hipaa

    return {
        "covered": sorted(covered_hipaa),
        "not_covered": sorted(not_covered),
        "coverage_count": len(covered_hipaa),
        "total": len(all_hipaa),
        "coverage_pct": round(len(covered_hipaa) / len(all_hipaa) * 100, 1),
        "notes": {
            cat: HIPAA_SAFE_HARBOR_18[cat]
            for cat in sorted(not_covered)
        },
    }


# =========================================================================== #
#  DIFFERENTIAL PRIVACY LITE — Noise Addition                                  #
#  Per Olatunji §6, Chong §3.2                                                #
# =========================================================================== #

def add_laplace_noise(
    df, numeric_columns: Sequence[str], epsilon: float = 1.0,
    sensitivity: float = 1.0
) -> "pd.DataFrame":
    """Add calibrated Laplace noise to numeric columns for differential privacy.

    Per Dwork & Roth (2014): ε-differential privacy adds Laplace noise
    with scale = sensitivity / epsilon.

    Parameters
    ----------
    df : DataFrame to perturb (a copy is returned)
    numeric_columns : columns to add noise to
    epsilon : privacy budget (smaller = more private, less utility)
    sensitivity : query sensitivity (default 1.0 for counting queries)
    """
    pd = _require_pandas()
    import numpy as np

    noisy = df.copy()
    scale = sensitivity / epsilon

    for col in numeric_columns:
        if pd.api.types.is_numeric_dtype(noisy[col]):
            noise = np.random.laplace(0, scale, size=len(noisy))
            noisy[col] = noisy[col] + noise
            # Round to original precision
            if noisy[col].dtype in (int, 'int64', 'int32'):
                noisy[col] = noisy[col].round(0).astype(int)

    return noisy


# =========================================================================== #
#  COMPREHENSIVE PRIVACY REPORT                                                #
# =========================================================================== #

def privacy_report(df, quasi_identifiers: Sequence[str],
                   sensitive_attr: str | None = None) -> dict:
    """Generate a comprehensive privacy report covering all metrics.

    Covers: k-anonymity, l-diversity, t-closeness, equivalence class
    summary, information loss metrics, and HIPAA coverage.
    """
    _require_pandas()
    report = {
        "rows": len(df),
        "quasi_identifiers": list(quasi_identifiers),
        "k_anonymity": k_anonymity(df, quasi_identifiers),
        "equivalence_classes": equivalence_class_summary(
            df, quasi_identifiers, sensitive_attr
        ),
        "discernability_metric": discernability_metric(df, quasi_identifiers),
        "cavg_metric": cavg_metric(df, quasi_identifiers),
    }
    if sensitive_attr:
        report["sensitive_attribute"] = sensitive_attr
        report["l_diversity"] = l_diversity(df, quasi_identifiers, sensitive_attr)
        report["t_closeness"] = round(
            t_closeness(df, quasi_identifiers, sensitive_attr), 4
        )
    return report


if __name__ == "__main__":
    pd = _require_pandas()
    data = pd.DataFrame([
        {"age_band": "20-30", "gender": "M", "state": "MH", "disease": "Flu"},
        {"age_band": "20-30", "gender": "M", "state": "MH", "disease": "Cold"},
        {"age_band": "20-30", "gender": "M", "state": "MH", "disease": "Flu"},
        {"age_band": "30-40", "gender": "F", "state": "DL", "disease": "TB"},
        {"age_band": "30-40", "gender": "F", "state": "DL", "disease": "Flu"},
    ])
    qi = ["age_band", "gender", "state"]
    sa = "disease"

    print("=== Privacy Report ===")
    import json
    print(json.dumps(privacy_report(data, qi, sa), indent=2))

    print("\n=== Equivalence Classes ===")
    for ec in equivalence_classes(data, qi):
        print(ec)

    print("\n=== HIPAA Coverage ===")
    sample_entities = {"PERSON", "EMAIL_ADDRESS", "IN_PHONE", "DATE_TIME",
                       "AADHAAR", "PAN", "ADDRESS", "URL", "IP_ADDRESS", "MRN"}
    print(json.dumps(hipaa_coverage_check(sample_entities), indent=2))

    print("\n=== l-diversity enforcement (l=2) ===")
    enforced = enforce_l_diversity(data, qi, sa, target_l=2)
    print(f"Records remaining: {len(enforced)} / {len(data)}")
