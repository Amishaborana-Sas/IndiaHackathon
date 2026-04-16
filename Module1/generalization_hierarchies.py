"""
Module 1 — Generalization Hierarchies
======================================
Implements value generalization hierarchies (VGH) for quasi-identifiers
as described in:
  - Olatunji et al. (2021) Fig. 1: "Generalization replaces QID values
    with other less specific values consistent with the original data"
  - Samarati (2001): Full-domain generalization hierarchy trees
  - Sepas et al. (2022) Table 1: Multiple generalization strategies

A VGH defines how values can be generalized to broader categories
at increasing levels of abstraction. This enables controlled information
loss during anonymization.

Example hierarchy for Age:
  Level 0: 25 (original)
  Level 1: 20-30 (decade range)
  Level 2: <50 (half-century)
  Level 3: * (fully suppressed)
"""

from __future__ import annotations


# =========================================================================== #
#  PREDEFINED HIERARCHIES FOR CDSCO/HEALTHCARE CONTEXT                        #
# =========================================================================== #

AGE_HIERARCHY = {
    "levels": 4,
    "description": "Age generalization: exact -> decade -> half-century -> suppressed",
    "generalize": [
        lambda age: f"{(age // 10) * 10}-{(age // 10) * 10 + 9}",  # Level 1: decade
        lambda age: "<50" if age < 50 else "50+",                    # Level 2: binary
        lambda age: "*",                                              # Level 3: suppressed
    ],
}

DATE_HIERARCHY = {
    "levels": 4,
    "description": "Date: exact -> month-year -> year-only -> suppressed",
    "generalize": [
        lambda d: d[:7] if len(d) >= 7 else d,         # Level 1: YYYY-MM
        lambda d: d[:4] if len(d) >= 4 else d,         # Level 2: YYYY
        lambda d: f"{d[:3]}0s" if len(d) >= 4 else "*", # Level 3: decade
    ],
}

LOCATION_HIERARCHY = {
    "levels": 4,
    "description": "Location: exact -> city -> state -> country -> suppressed",
    # This requires a lookup table; using labels as placeholders
    "generalize": [
        lambda loc: "[CITY]",     # Level 1: city-level
        lambda loc: "[STATE]",    # Level 2: state-level
        lambda loc: "INDIA",      # Level 3: country-level
    ],
}

GENDER_HIERARCHY = {
    "levels": 2,
    "description": "Gender: exact -> person -> suppressed",
    "generalize": [
        lambda g: "*",  # Level 1: suppressed
    ],
}

ZIP_CODE_HIERARCHY = {
    "levels": 4,
    "description": "ZIP/PIN code: exact -> 3-digit -> 1-digit -> suppressed",
    "generalize": [
        lambda z: z[:3] + "***" if len(z) >= 6 else z[:3] + "**",  # Level 1
        lambda z: z[:1] + "*****" if len(z) >= 6 else z[:1] + "****",  # Level 2
        lambda z: "******",  # Level 3
    ],
}

# Registry of all predefined hierarchies
PREDEFINED_HIERARCHIES = {
    "age": AGE_HIERARCHY,
    "date": DATE_HIERARCHY,
    "date_of_birth": DATE_HIERARCHY,
    "dob": DATE_HIERARCHY,
    "location": LOCATION_HIERARCHY,
    "city": LOCATION_HIERARCHY,
    "address": LOCATION_HIERARCHY,
    "gender": GENDER_HIERARCHY,
    "sex": GENDER_HIERARCHY,
    "zip_code": ZIP_CODE_HIERARCHY,
    "pin_code": ZIP_CODE_HIERARCHY,
    "postal_code": ZIP_CODE_HIERARCHY,
}


def generalize_value_at_level(value, hierarchy: dict, level: int):
    """Apply a specific generalization level from a hierarchy.

    Level 0 = original value (no generalization)
    Level 1 = first generalization, etc.
    Level max = full suppression (*)
    """
    if level <= 0:
        return value
    fns = hierarchy.get("generalize", [])
    level_idx = min(level - 1, len(fns) - 1)
    if level_idx < 0:
        return value
    try:
        return fns[level_idx](value)
    except Exception:
        return "*"


def get_hierarchy_for_attribute(attr_name: str) -> dict | None:
    """Look up a predefined hierarchy by attribute name (case-insensitive)."""
    return PREDEFINED_HIERARCHIES.get(attr_name.lower().strip())


def compute_information_loss_for_level(hierarchy: dict, level: int) -> float:
    """Compute the fraction of information lost at a generalization level.

    Per Olatunji §2.3: Information loss = generalization_level / max_level.
    Level 0 = 0% loss, Level max = 100% loss.
    """
    max_levels = hierarchy.get("levels", 1)
    return min(level / max(max_levels - 1, 1), 1.0)


# =========================================================================== #
#  ADAPTIVE GENERALIZATION                                                     #
#  Per Majeed et al. (Olatunji §3.1.1): "focused on adaptive attribute         #
#  generalization based on different information contents of QIDs"              #
# =========================================================================== #

def find_minimum_generalization_level(
    df, quasi_identifiers: list[str], hierarchies: dict[str, dict],
    target_k: int = 5
) -> dict[str, int]:
    """Find the minimum generalization level for each QI that achieves target_k.

    Iteratively increases generalization levels until k-anonymity is satisfied.
    Returns a dict mapping QI names to their optimal generalization levels.
    """
    pd = __import__("pandas")

    current_levels = {qi: 0 for qi in quasi_identifiers}
    max_iterations = 20

    for _ in range(max_iterations):
        # Apply current generalization levels
        test_df = df.copy()
        for qi in quasi_identifiers:
            h = hierarchies.get(qi)
            if h and current_levels[qi] > 0:
                test_df[qi] = test_df[qi].apply(
                    lambda v, hi=h, lv=current_levels[qi]:
                        generalize_value_at_level(v, hi, lv)
                )

        # Check k-anonymity
        sizes = test_df.groupby(quasi_identifiers, dropna=False).size()
        achieved_k = int(sizes.min()) if len(sizes) else 0

        if achieved_k >= target_k:
            return current_levels

        # Increase the level of the QI with the most unique values
        # (the one contributing most to re-identification risk)
        uniqueness = {
            qi: test_df[qi].nunique()
            for qi in quasi_identifiers
            if current_levels[qi] < hierarchies.get(qi, {}).get("levels", 1) - 1
        }
        if not uniqueness:
            break  # All QIs at max level

        most_unique = max(uniqueness, key=uniqueness.get)
        current_levels[most_unique] += 1

    return current_levels
