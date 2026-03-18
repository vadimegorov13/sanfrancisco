"""
311 neighborhood-month aggregation.

Takes a filtered sf_311_cases DataFrame (output of filter_311) and
produces one row per (neighborhood, year_month) with the 9 feature columns.

Feature columns produced:
  total_311_count       — count of all filtered records
  count_street_pavement — count of street_pavement group rows
  count_sidewalk_curb   — count of sidewalk_curb group rows
  count_sewer_drainage  — count of sewer_drainage group rows
  count_streetlights    — count of streetlights group rows
  count_traffic_signs   — count of traffic_signs group rows
  count_trees           — count of trees group rows
  distinct_issue_groups — number of distinct issue groups present
  avg_closure_days      — mean closure time in calendar days (positive only,
                          capped at MAX_CLOSURE_DAYS; NaN if no valid rows)

Usage:
    df_raw      = db.query("SELECT * FROM assignment_1.sf_311_cases")
    df_filtered = filter_311(df_raw)
    df_filtered = apply_neighborhood_normalization(df_filtered, col="analysis_neighborhood")
    features    = build_311_features(df_filtered)
"""

from __future__ import annotations

import pandas as pd

# Maximum closure time in calendar days included in the avg_closure_days
# calculation. Cases open longer than this are capped to avoid extreme outliers
# distorting the per-neighborhood monthly average.
MAX_CLOSURE_DAYS: float = 365.0

# Groups that get their own individual count column in the feature table.
# water_utility, property_damage_infra, and blocked_street are deliberately
# omitted here — they contribute to total_311_count and distinct_issue_groups
# but are too small or too uncertain for individual monthly columns.
_COUNTED_GROUPS: list[str] = [
    "street_pavement",
    "sidewalk_curb",
    "sewer_drainage",
    "streetlights",
    "traffic_signs",
    "trees",
]


def build_311_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate a filtered 311 DataFrame into a neighborhood-month feature table.

    The input DataFrame must have already been processed by filter_311 and
    apply_neighborhood_normalization, so it has:
      - `neighborhood`       (str)  canonical neighborhood label
      - `issue_group`        (str)  one of the 9 issue groups
      - `requested_datetime` (datetime or parseable str) request open timestamp
      - `closed_date`        (datetime or parseable str) request close timestamp
      - `service_request_id` (any)  present for total count

    Args:
        df: Filtered and neighborhood-normalized 311 DataFrame.

    Returns:
        DataFrame with columns:
          neighborhood, year_month,
          total_311_count, count_street_pavement, count_sidewalk_curb,
          count_sewer_drainage, count_streetlights, count_traffic_signs,
          count_trees, distinct_issue_groups, avg_closure_days
        One row per (neighborhood, year_month). Sorted by neighborhood then month.
    """
    df = df.copy()

    # Parse datetimes
    df["requested_datetime"] = pd.to_datetime(df["requested_datetime"], errors="coerce")
    df["closed_date"]        = pd.to_datetime(df["closed_date"],        errors="coerce")

    # Derive year_month from request open date
    df["year_month"] = df["requested_datetime"].dt.strftime("%Y-%m")

    # Compute closure days
    # Only count rows where close > open (both non-null, positive difference).
    # Cap extreme values to avoid outliers distorting monthly means.
    delta = (df["closed_date"] - df["requested_datetime"]).dt.total_seconds() / 86400.0
    valid_closure = delta.where(delta > 0)                     # NaN if <= 0
    df["closure_days"] = valid_closure.clip(upper=MAX_CLOSURE_DAYS)

    # Boolean indicators for individually-counted groups
    for group in _COUNTED_GROUPS:
        df[f"_is_{group}"] = (df["issue_group"] == group).astype("int8")

    # Aggregate by (neighborhood, year_month)
    group_keys = ["neighborhood", "year_month"]

    agg: dict[str, tuple] = {
        "total_311_count": ("service_request_id", "count"),
        **{
            f"count_{g}": (f"_is_{g}", "sum")
            for g in _COUNTED_GROUPS
        },
        "distinct_issue_groups": ("issue_group", "nunique"),
        "avg_closure_days":      ("closure_days", "mean"),
    }

    features = (
        df.groupby(group_keys, sort=False)
        .agg(**agg)
        .reset_index()
    )

    # Cast integer columns cleanly (sum on int8 may stay int8).
    int_cols = ["total_311_count", "distinct_issue_groups"] + [
        f"count_{g}" for g in _COUNTED_GROUPS
    ]
    features[int_cols] = features[int_cols].astype("int32")

    # Sort for deterministic output order.
    features = features.sort_values(
        ["neighborhood", "year_month"], ignore_index=True
    )

    return features
