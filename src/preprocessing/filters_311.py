"""
311 filtering

Applies the inclusion/exclusion rules to a raw sf_311_cases DataFrame and
assigns each surviving row to a v1_issue_group.

All filtering logic is expressed as named constants so changes can be made in
one place without touching aggregation or pipeline code.

Usage:
    df_raw = db.query("SELECT * FROM assignment_1.sf_311_cases")
    df_filtered = filter_311_v1(df_raw)
"""

from __future__ import annotations

import pandas as pd

V1_START_DATE = "2024-01-01"
V1_END_DATE   = "2026-01-01"

# Core service names: included purely on service_name match.
CORE_SERVICE_NAMES: frozenset[str] = frozenset({
    "Street Defect",
    "Street Defects",                                       # legacy duplicate
    "Sidewalk and Curb",
    "Sidewalk or Curb",                                     # legacy duplicate
    "Sewer",
    "Sewer Issues",                                         # legacy duplicate
    "Streetlights",
    "MTA Parking Traffic Signs Normal Priority",
    "MTA Parking Traffic Signs High Priority",
    "Sign Repair",
    "Catch Basin Maintenance",
    "Tree Maintenance",
    "Waste of Water",
})

# Damage Property: included ONLY when service_subtype is in the list below.
DAMAGE_PROPERTY_NAMES: frozenset[str] = frozenset({
    "Damage Property",
    "Damaged Property",                                     # legacy duplicate
})
DAMAGE_PROPERTY_SUBTYPES: frozenset[str] = frozenset({
    "parking_meter",
    "traffic_signal",
})

# Blocked Street: included ONLY when subtype is in the list below AND
# service_details is not a scooter-type detail.
BLOCKED_STREET_NAMES: frozenset[str] = frozenset({
    "Blocked Street and Sidewalk",
    "Blocked Street or SideWalk",                           # legacy duplicate
})
BLOCKED_STREET_SUBTYPES: frozenset[str] = frozenset({
    "blocked_sidewalk",
    "blocked_parking_space_or_strip",
})
SCOOTER_DETAILS: frozenset[str] = frozenset({
    "scooter_without_license_plate",
    "lime_standing_scooter",
    "spin_standing_scooter",
})

# Combined set of all included service names (used as a fast pre-filter).
ALL_INCLUDED_SERVICE_NAMES: frozenset[str] = (
    CORE_SERVICE_NAMES | DAMAGE_PROPERTY_NAMES | BLOCKED_STREET_NAMES
)

# ---------------------------------------------------------------------------
# v1 issue-group mapping
#
# Every service_name that survives filtering maps to exactly one group.
# The group is used for per-category counts and distinct-breadth calculation.
# ---------------------------------------------------------------------------
_SERVICE_NAME_TO_GROUP: dict[str, str] = {
    # street_pavement
    "Street Defect":     "street_pavement",
    "Street Defects":    "street_pavement",
    # sidewalk_curb
    "Sidewalk and Curb": "sidewalk_curb",
    "Sidewalk or Curb":  "sidewalk_curb",
    # sewer_drainage
    "Sewer":                  "sewer_drainage",
    "Sewer Issues":           "sewer_drainage",
    "Catch Basin Maintenance": "sewer_drainage",
    # streetlights
    "Streetlights": "streetlights",
    # traffic_signs
    "MTA Parking Traffic Signs Normal Priority": "traffic_signs",
    "MTA Parking Traffic Signs High Priority":   "traffic_signs",
    "Sign Repair":                               "traffic_signs",
    # trees
    "Tree Maintenance": "trees",
    # water_utility
    "Waste of Water": "water_utility",
    # property_damage_infra (subtype-filtered rows only)
    "Damage Property":  "property_damage_infra",
    "Damaged Property": "property_damage_infra",
    # blocked_street (scooter-filtered rows only)
    "Blocked Street and Sidewalk": "blocked_street",
    "Blocked Street or SideWalk":  "blocked_street",
}

# Ordered list of all 9 groups (used externally for consistency).
V1_ISSUE_GROUPS: list[str] = [
    "street_pavement",
    "sidewalk_curb",
    "sewer_drainage",
    "streetlights",
    "traffic_signs",
    "trees",
    "water_utility",
    "property_damage_infra",
    "blocked_street",
]

def filter_311_v1(
    df: pd.DataFrame,
    start_date: str = V1_START_DATE,
    end_date: str = V1_END_DATE,
) -> pd.DataFrame:
    """
    Apply filtering rules to a raw sf_311_cases DataFrame.

    Steps applied in order:
      1. Parse requested_datetime to datetime.
      2. Apply time window [start_date, end_date).
      3. Require non-null analysis_neighborhood.
      4. Apply service_name inclusion rules (core + damage + blocked).
      5. Apply subtype filter for Damage Property rows.
      6. Apply subtype + details exclusion filter for Blocked Street rows.
      7. Assign v1_issue_group to every surviving row.

    Args:
        df:         Raw DataFrame from sf_311_cases.
        start_date: Inclusive lower bound for requested_datetime (ISO date string).
        end_date:   Exclusive upper bound for requested_datetime (ISO date string).

    Returns:
        Filtered DataFrame with a new `v1_issue_group` column.
        Index is reset.
    """
    df = df.copy()

    # Parse requested_datetime
    df["requested_datetime"] = pd.to_datetime(df["requested_datetime"], errors="coerce")

    # Time window
    mask_time = (
        df["requested_datetime"] >= pd.Timestamp(start_date)
    ) & (
        df["requested_datetime"] < pd.Timestamp(end_date)
    )
    df = df[mask_time]

    # Require neighborhood
    df = df[df["analysis_neighborhood"].notna()]

    # Service name pre-filter
    df = df[df["service_name"].isin(ALL_INCLUDED_SERVICE_NAMES)]

    # Damage Property: require infrastructure subtype
    is_damage = df["service_name"].isin(DAMAGE_PROPERTY_NAMES)
    damage_ok = is_damage & df["service_subtype"].isin(DAMAGE_PROPERTY_SUBTYPES)
    not_damage = ~is_damage
    df = df[not_damage | damage_ok]

    # Blocked Street: require subtype + exclude scooter details
    is_blocked = df["service_name"].isin(BLOCKED_STREET_NAMES)
    blocked_subtype_ok = df["service_subtype"].isin(BLOCKED_STREET_SUBTYPES)
    # Treat NULL service_details as non-scooter (safe to include).
    is_scooter = df["service_details"].isin(SCOOTER_DETAILS)
    blocked_ok = is_blocked & blocked_subtype_ok & ~is_scooter
    not_blocked = ~is_blocked
    df = df[not_blocked | blocked_ok]

    # Assign v1_issue_group
    df["v1_issue_group"] = df["service_name"].map(_SERVICE_NAME_TO_GROUP)

    n_missing_group = df["v1_issue_group"].isna().sum()
    if n_missing_group > 0:
        # Should not happen with a complete mapping, but guard explicitly.
        unmapped = df.loc[df["v1_issue_group"].isna(), "service_name"].unique().tolist()
        raise ValueError(
            f"filter_311_v1: {n_missing_group} rows could not be assigned a "
            f"v1_issue_group. Unmapped service_name values: {unmapped}"
        )

    return df.reset_index(drop=True)
