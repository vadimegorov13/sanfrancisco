"""
Neighborhood key normalization.

Both sf_311_cases.analysis_neighborhood and sf_fire_incidents.neighborhood_district
use the same 41 neighborhood labels with identical spelling, punctuation, and
character encoding.

The normalized key is called `neighborhood` and is the canonical label value.

The only required transformations are:
  1. Strip leading/trailing whitespace
  2. Drop or flag NULL values in the fire table (1,531 rows in fire).

No name-mapping is required between the two tables.
This module still defines an explicit mapping dict so that future mismatches
can be patched here without touching pipeline logic.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# Canonical neighborhood list (41 neighborhoods)
# Source: 311 analysis_neighborhood label set, verified against fire
#         neighborhood_district label set — 41/41 exact matches.
# ---------------------------------------------------------------------------
CANONICAL_NEIGHBORHOODS: list[str] = [
    "Bayview Hunters Point",
    "Bernal Heights",
    "Castro/Upper Market",
    "Chinatown",
    "Excelsior",
    "Financial District/South Beach",
    "Glen Park",
    "Golden Gate Park",
    "Haight Ashbury",
    "Hayes Valley",
    "Inner Richmond",
    "Inner Sunset",
    "Japantown",
    "Lakeshore",
    "Lincoln Park",
    "Lone Mountain/USF",
    "Marina",
    "McLaren Park",
    "Mission",
    "Mission Bay",
    "Nob Hill",
    "Noe Valley",
    "North Beach",
    "Oceanview/Merced/Ingleside",
    "Outer Mission",
    "Outer Richmond",
    "Pacific Heights",
    "Portola",
    "Potrero Hill",
    "Presidio",
    "Presidio Heights",
    "Russian Hill",
    "Seacliff",
    "South of Market",
    "Sunset/Parkside",
    "Tenderloin",
    "Treasure Island",
    "Twin Peaks",
    "Visitacion Valley",
    "West of Twin Peaks",
    "Western Addition",
]

# ---------------------------------------------------------------------------
# Explicit mapping: raw label -> canonical label.
#
# Every raw label already equals the canonical label.
# The dict still exists so future data reloads with renamed or alternate labels
# can be patched here without modifying pipeline code.
# ---------------------------------------------------------------------------
_NEIGHBORHOOD_MAP: dict[str, str] = {label: label for label in CANONICAL_NEIGHBORHOODS}

def normalize_neighborhood(raw: str | None) -> str | None:
    """
    Map a raw neighborhood label to its canonical form.

    Returns None if the input is None or blank, so callers can easily filter
    rows with missing geography.

    Args:
        raw: Raw label from analysis_neighborhood or neighborhood_district.

    Returns:
        Canonical neighborhood string, or None.
    """
    if raw is None:
        return None
    
    stripped = raw.strip()

    if stripped == "":
        return None
    
    canonical = _NEIGHBORHOOD_MAP.get(stripped)

    if canonical is None:
        # Unknown label — return stripped but flag it so callers can log it.
        # Do not silently discard; let the pipeline decide.
        return stripped
    
    return canonical


def apply_neighborhood_normalization(
    df: pd.DataFrame,
    col: str,
    out_col: str = "neighborhood",
    drop_unknown: bool = True,
) -> pd.DataFrame:
    """
    Apply neighborhood normalization to a DataFrame column.

    Adds a new `out_col` column with canonical labels.
    Rows where the normalized value is None are dropped by default.
    Rows whose raw label is not in the mapping are logged as warnings
    and optionally dropped.

    Args:
        df:           Input DataFrame.
        col:          Column containing raw neighborhood labels.
        out_col:      Name of the new canonical column (default: 'neighborhood').
        drop_unknown: If True (default), drop rows with None/unknown neighborhoods.

    Returns:
        DataFrame with `out_col` added and invalid rows removed.
    """
    df = df.copy()
    df[out_col] = df[col].apply(normalize_neighborhood)

    # Identify rows that are None after normalization (NULL input or blank)
    null_mask = df[out_col].isna()
    if null_mask.any():
        print(
            f"[neighborhood_normalizer] Dropping {null_mask.sum()} rows with "
            f"null/blank '{col}'."
        )

    # Identify rows whose normalized label is not in the canonical set
    # (i.e., normalize_neighborhood returned the raw value as a fallback)
    unknown_mask = df[out_col].notna() & ~df[out_col].isin(CANONICAL_NEIGHBORHOODS)
    if unknown_mask.any():
        unknown_labels = df.loc[unknown_mask, out_col].unique().tolist()
        print(
            f"[neighborhood_normalizer] WARNING: {unknown_mask.sum()} rows have "
            f"unrecognized neighborhood labels not in the canonical list: "
            f"{unknown_labels}"
        )
        if drop_unknown:
            print(
                f"[neighborhood_normalizer] Dropping {unknown_mask.sum()} rows "
                f"with unrecognized labels."
            )

    if drop_unknown:
        df = df[df[out_col].isin(CANONICAL_NEIGHBORHOODS)].copy()

    return df
