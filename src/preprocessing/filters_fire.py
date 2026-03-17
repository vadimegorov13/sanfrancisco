"""
Fire incident filtering

Applies the inclusion rules to a raw sf_fire_incidents DataFrame and
assigns each surviving row to a v1_incident_group.

All filtering logic is expressed as named constants so changes can be made in
one place without touching aggregation or pipeline code.

Usage:
    df_raw = db.query("SELECT * FROM assignment_1.sf_fire_incidents")
    df_filtered = filter_fire_v1(df_raw)
"""

from __future__ import annotations

import pandas as pd

V1_START_DATE = "2024-01-01"
V1_END_DATE   = "2026-01-01"   # exclusive upper bound → effectively 2025-12-31

# Structural / property fires
BUILDING_FIRE_SITUATIONS: frozenset[str] = frozenset({
    "111 Building fire",
    "100 Fire, other",
})

# Electrical infrastructure failures
ELECTRICAL_SITUATIONS: frozenset[str] = frozenset({
    "440 Electrical  wiring/equipment problem, other",   # double space — verified
    "445 Arcing, shorted electrical equipment",
    "4450 Arcing, shorted electrical PG&E equipment",
    "444 Power line down",
    "4440 PG&E Power line down",
})

# Gas utility failures
GAS_SITUATIONS: frozenset[str] = frozenset({
    "412 Gas leak (natural gas or LPG)",
})

# Water infrastructure failures
WATER_UTILITY_SITUATIONS: frozenset[str] = frozenset({
    "520 Water problem, other",
    "522 Water or steam leak",
})

# Combined set of all included situations (fast pre-filter).
ALL_INCLUDED_SITUATIONS: frozenset[str] = (
    BUILDING_FIRE_SITUATIONS
    | ELECTRICAL_SITUATIONS
    | GAS_SITUATIONS
    | WATER_UTILITY_SITUATIONS
)

# Every primary_situation that survives filtering maps to exactly one group.
_SITUATION_TO_GROUP: dict[str, str] = {
    # building_fire
    "111 Building fire": "building_fire",
    "100 Fire, other":   "building_fire",
    # electrical
    "440 Electrical  wiring/equipment problem, other": "electrical",
    "445 Arcing, shorted electrical equipment":        "electrical",
    "4450 Arcing, shorted electrical PG&E equipment":  "electrical",
    "444 Power line down":                             "electrical",
    "4440 PG&E Power line down":                       "electrical",
    # gas
    "412 Gas leak (natural gas or LPG)": "gas",
    # water_utility
    "520 Water problem, other": "water_utility",
    "522 Water or steam leak":  "water_utility",
}

# Ordered list of all 4 groups (used externally for consistency).
V1_INCIDENT_GROUPS: list[str] = [
    "building_fire",
    "electrical",
    "gas",
    "water_utility",
]


def filter_fire_v1(
    df: pd.DataFrame,
    start_date: str = V1_START_DATE,
    end_date: str = V1_END_DATE,
) -> pd.DataFrame:
    """
    Apply filtering rules to a raw sf_fire_incidents DataFrame.

    Steps applied in order:
      1. Parse incident_date (stored as TEXT) to datetime.
      2. Apply time window [start_date, end_date).
      3. Require non-null neighborhood_district.
      4. Filter to v1 primary_situation include set.
      5. Assign v1_incident_group to every surviving row.

    All numeric columns (fire_injuries, civilian_injuries, suppression_units)
    are left as-is here; the aggregator casts them.

    Args:
        df:         Raw DataFrame from sf_fire_incidents.
        start_date: Inclusive lower bound for incident_date (ISO date string).
        end_date:   Exclusive upper bound for incident_date (ISO date string).

    Returns:
        Filtered DataFrame with a new `v1_incident_group` column.
        Index is reset.
    """
    df = df.copy()

    # Parse incident_date — stored as TEXT in MySQL, format is 'YYYY-MM-DD'
    df["incident_date"] = pd.to_datetime(df["incident_date"], errors="coerce")

    # Time window
    mask_time = (
        df["incident_date"] >= pd.Timestamp(start_date)
    ) & (
        df["incident_date"] < pd.Timestamp(end_date)
    )
    df = df[mask_time]

    # Require neighborhood
    df = df[df["neighborhood_district"].notna()]

    # Situation include filter
    df = df[df["primary_situation"].isin(ALL_INCLUDED_SITUATIONS)]

    # Assign v1_incident_group
    df["v1_incident_group"] = df["primary_situation"].map(_SITUATION_TO_GROUP)

    n_missing = df["v1_incident_group"].isna().sum()
    if n_missing > 0:
        unmapped = df.loc[df["v1_incident_group"].isna(), "primary_situation"].unique().tolist()
        raise ValueError(
            f"filter_fire_v1: {n_missing} rows could not be assigned a "
            f"v1_incident_group. Unmapped primary_situation values: {unmapped}"
        )

    return df.reset_index(drop=True)
