"""
Fire incident neighborhood-month aggregation

Takes a filtered sf_fire_incidents DataFrame (output of filter_fire_v1) and
produces one row per (neighborhood, year_month) with the 7 v1 fire feature
columns defined in Story 3.

Feature columns produced:
  total_fire_count      — count of all filtered records
  count_fire_building   — count of building_fire group rows
  count_fire_electrical — count of electrical group rows
  count_fire_gas        — count of gas group rows
  count_fire_water      — count of water_utility group rows
  total_fire_injuries   — sum of (fire_injuries + civilian_injuries) per row
  avg_suppression_units — mean suppression_units per incident (float)

Usage:
    from src.preprocessing.filters_fire import filter_fire_v1
    from src.preprocessing.aggregator_fire import build_fire_features
    from src.preprocessing.neighborhood_normalizer import apply_neighborhood_normalization

    df_raw      = db.query("SELECT * FROM assignment_1.sf_fire_incidents")
    df_filtered = filter_fire_v1(df_raw)
    df_filtered = apply_neighborhood_normalization(df_filtered, col="neighborhood_district")
    features    = build_fire_features(df_filtered)
"""

from __future__ import annotations

import pandas as pd

# Groups that get their own count column in the fire feature table.
# Key = v1_incident_group value; value = column name suffix (count_fire_{suffix}).
_COUNTED_GROUPS: dict[str, str] = {
    "building_fire": "building",
    "electrical":    "electrical",
    "gas":           "gas",
    "water_utility": "water",
}


def build_fire_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate a filtered fire DataFrame into a neighborhood-month feature table.

    The input DataFrame must have already been processed by filter_fire_v1 and
    apply_neighborhood_normalization, so it has:
      - `neighborhood`      (str)      canonical neighborhood label
      - `v1_incident_group` (str)      one of the 4 v1 incident groups
      - `incident_date`     (datetime or parseable str or None)
      - `fire_injuries`     (str or numeric)  injuries to fire personnel
      - `civilian_injuries` (str or numeric)  injuries to civilians
      - `suppression_units` (str or numeric)  units dispatched

    All three numeric columns are stored as TEXT in MySQL and are cast here
    before aggregation.

    Args:
        df: Filtered and neighborhood-normalized fire DataFrame.

    Returns:
        DataFrame with columns:
          neighborhood, year_month,
          total_fire_count,
          count_fire_building, count_fire_electrical, count_fire_gas, count_fire_water,
          total_fire_injuries, avg_suppression_units
        One row per (neighborhood, year_month). Sorted by neighborhood then month.
    """
    df = df.copy()

    # Parse incident_date if still a string (filter_fire_v1 parses it, but be defensive)
    df["incident_date"] = pd.to_datetime(df["incident_date"], errors="coerce")

    # Derive year_month from incident date
    df["year_month"] = df["incident_date"].dt.strftime("%Y-%m")

    # Cast numeric columns — all stored as TEXT in MySQL
    df["fire_injuries"]     = pd.to_numeric(df["fire_injuries"],     errors="coerce").fillna(0)
    df["civilian_injuries"] = pd.to_numeric(df["civilian_injuries"], errors="coerce").fillna(0)
    df["suppression_units"] = pd.to_numeric(df["suppression_units"], errors="coerce")

    # Per-row total injuries (feed into SUM later)
    df["row_injuries"] = df["fire_injuries"] + df["civilian_injuries"]

    # Boolean indicators for individually-counted groups
    for group in _COUNTED_GROUPS:
        df[f"_is_{group}"] = (df["v1_incident_group"] == group).astype("int8")

    # Aggregate by (neighborhood, year_month)
    group_keys = ["neighborhood", "year_month"]

    agg: dict[str, tuple] = {
        "total_fire_count": ("incident_date", "count"),
        **{
            f"count_fire_{col_suffix}": (f"_is_{group}", "sum")
            for group, col_suffix in _COUNTED_GROUPS.items()
        },
        "total_fire_injuries":   ("row_injuries",      "sum"),
        "avg_suppression_units": ("suppression_units", "mean"),
    }

    features = (
        df.groupby(group_keys, sort=False)
        .agg(**agg)
        .reset_index()
    )

    # Cast integer columns
    int_cols = ["total_fire_count", "total_fire_injuries"] + [
        f"count_fire_{col_suffix}" for col_suffix in _COUNTED_GROUPS.values()
    ]
    features[int_cols] = features[int_cols].astype("int32")

    # Sort for deterministic output order
    features = features.sort_values(
        ["neighborhood", "year_month"], ignore_index=True
    )

    return features
