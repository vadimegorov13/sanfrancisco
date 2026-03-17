"""
Merges the 311 and filtered fire neighborhood-month feature tables into a
single analysis-ready table with one row per (neighborhood, year_month).

Join strategy
-------------
The spine is the **full Cartesian product** of all 41 canonical neighborhoods
x all 24 months in the v1 window (2024-01 through 2025-12), giving 984 rows.

Both the 311 and fire feature tables are left-joined onto this spine so that:

- Every neighborhood-month combination is represented, even if it had zero
  filtered activity in one or both source datasets.
- No valid row is silently dropped because a neighborhood happened to be quiet
  in a particular month.

Missing-value handling
-----------------------
After the join, some neighborhood-months will lack a match in one or both
source tables (the row was absent because aggregation produced no rows for zero
activity). The fill rules are:

  311 integer count columns  → fill with 0  (zero issues reported)
  fire integer count columns → fill with 0  (zero incidents recorded)
  avg_closure_days           → leave as NaN (no cases to compute a mean over)
  avg_suppression_units      → leave as NaN (no incidents to compute a mean over)

The NaN value for avg_* columns on zero-activity months is intentional:
filling with 0 would be misleading (a mean of 0 implies infrastructure is
faster/lighter than any real month, not that there was no activity).

Usage:
    from src.preprocessing.filters_311 import filter_311_v1
    from src.preprocessing.filters_fire import filter_fire_v1
    from src.preprocessing.aggregator_311 import build_311_features
    from src.preprocessing.aggregator_fire import build_fire_features
    from src.preprocessing.neighborhood_normalizer import apply_neighborhood_normalization
    from src.preprocessing.merger import build_v1_analysis_table

    # --- 311 pipeline ---
    df_311 = filter_311_v1(raw_311)
    df_311 = apply_neighborhood_normalization(df_311, col="analysis_neighborhood")
    features_311 = build_311_features(df_311)

    # --- fire pipeline ---
    df_fire = filter_fire_v1(raw_fire)
    df_fire = apply_neighborhood_normalization(df_fire, col="neighborhood_district")
    features_fire = build_fire_features(df_fire)

    # --- merge ---
    v1 = build_v1_analysis_table(features_311, features_fire)
"""

from __future__ import annotations

import pandas as pd

from .neighborhood_normalizer import CANONICAL_NEIGHBORHOODS

# time window helpers
V1_START_MONTH = "2024-01"
V1_END_MONTH   = "2025-12"   # inclusive

# Generate the complete list of 24 months in the v1 window.
_V1_MONTHS: list[str] = (
    pd.period_range(start=V1_START_MONTH, end=V1_END_MONTH, freq="M")
    .strftime("%Y-%m")
    .tolist()
)

# Column fill rules
# Integer feature columns that should be 0 when there was no activity.
_311_INT_COLS: list[str] = [
    "total_311_count",
    "count_street_pavement",
    "count_sidewalk_curb",
    "count_sewer_drainage",
    "count_streetlights",
    "count_traffic_signs",
    "count_trees",
    "distinct_issue_groups",
]
_311_FLOAT_COLS: list[str] = [
    "avg_closure_days",    # NaN for zero-activity months — no mean to compute
]

_FIRE_INT_COLS: list[str] = [
    "total_fire_count",
    "count_fire_building",
    "count_fire_electrical",
    "count_fire_gas",
    "count_fire_water",
    "total_fire_injuries",
]
_FIRE_FLOAT_COLS: list[str] = [
    "avg_suppression_units",   # NaN for zero-incident months — no mean to compute
]


def build_v1_analysis_table(
    features_311: pd.DataFrame,
    features_fire: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge the 311 and fire neighborhood-month feature tables into the single table.

    Args:
        features_311:  Output of build_311_features — one row per
                       (neighborhood, year_month) with 311 feature columns.
        features_fire: Output of build_fire_features — one row per
                       (neighborhood, year_month) with fire feature columns.

    Returns:
        DataFrame with 984 rows (41 neighborhoods × 24 months) and 18 columns:
          neighborhood, year_month,
          [9 x 311 feature columns],
          [7 x fire feature columns]
        Sorted by neighborhood then year_month.
    """
    join_keys = ["neighborhood", "year_month"]

    # Build the full spine 
    spine = pd.DataFrame(
        [
            {"neighborhood": nbhd, "year_month": ym}
            for nbhd in CANONICAL_NEIGHBORHOODS
            for ym in _V1_MONTHS
        ]
    )

    # Join 311 features
    merged = spine.merge(
        features_311[join_keys + _311_INT_COLS + _311_FLOAT_COLS],
        on=join_keys,
        how="left",
    )

    # Join fire features
    merged = merged.merge(
        features_fire[join_keys + _FIRE_INT_COLS + _FIRE_FLOAT_COLS],
        on=join_keys,
        how="left",
    )

    # Fill zero-activity count columns
    merged[_311_INT_COLS] = merged[_311_INT_COLS].fillna(0).astype("int32")
    merged[_FIRE_INT_COLS] = merged[_FIRE_INT_COLS].fillna(0).astype("int32")

    # avg_closure_days and avg_suppression_units stay NaN where no activity

    # Sort for deterministic output
    merged = merged.sort_values(join_keys, ignore_index=True)

    return merged
