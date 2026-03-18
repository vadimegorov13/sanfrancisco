"""
Composite issue-pressure score.

Score design
------------
The score summarises the feature table into a single number per
neighborhood-month and then into a per-neighborhood summary.

Feature selection
------------
All 16 features in the table are ↑ = more pressure. To avoid
double-counting, only a non-redundant subset is used in the composite score:

  From 311 (3 features):
    total_311_count       — overall volume        (primary spine)
    distinct_issue_groups — breadth of issue types
    avg_closure_days      — resolution strain proxy

  From fire (3 features):
    total_fire_count      — overall emergency volume
    total_fire_injuries   — severity signal
    avg_suppression_units — incident seriousness proxy

The per-category count columns (count_street_pavement, count_fire_building …)
are deliberately excluded from the composite: they are sub-components of the
two total_* columns and including them alongside totals would inflate the
volume signal. They remain available for clustering and anomaly detection.

Normalisation
------------
Each of the 6 features is min-max scaled to [0, 1] across all
neighborhood-month rows:

    scaled = (x - min) / (max - min)

  • avg_closure_days NaN (month with no closeable cases) → 0.0 before scaling
  • avg_suppression_units NaN (month with no fire incidents) → 0.0 before scaling

Weighting
------------
Equal weight within each dataset group, then a 60/40 split between 311 and fire:

    311_sub  = mean(scaled_total_311, scaled_distinct_groups, scaled_avg_closure)
    fire_sub = mean(scaled_total_fire, scaled_injuries, scaled_suppression)
    raw      = 0.60 * 311_sub + 0.40 * fire_sub

Final score is rescaled to 0-100 for readability.

Neighbourhood summary
------------
The per-neighborhood score is the mean of the 24 monthly scores.

Outputs
-------
score_neighborhood_months(features)  →  984-row DataFrame, one row per (nbhd, month)
compute_scores(features)             →  41-row DataFrame, one row per neighborhood
"""

from __future__ import annotations

import pandas as pd

# Score configuration — change here to update the entire scoring model
# Features included in the composite score (non-redundant subset).
SCORE_FEATURES_311: dict[str, str] = {
    "total_311_count":       "total 311 cases",
    "distinct_issue_groups": "distinct issue types",
    "avg_closure_days":      "avg closure days",
}
SCORE_FEATURES_FIRE: dict[str, str] = {
    "total_fire_count":      "total fire incidents",
    "total_fire_injuries":   "total fire injuries",
    "avg_suppression_units": "avg suppression units",
}
ALL_SCORE_FEATURES: dict[str, str] = {**SCORE_FEATURES_311, **SCORE_FEATURES_FIRE}

# Dataset bucket weights (must sum to 1).
WEIGHT_311  = 0.60
WEIGHT_FIRE = 0.40

# NaN fill value (both avg_ columns) before normalisation.
_NAN_FILL = 0.0


# Internal helpers
def _minmax(series: pd.Series) -> pd.Series:
    """Min-max scale a Series to [0, 1]. Returns 0.0 everywhere if range == 0."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return pd.Series(0.0, index=series.index)
    return (series - lo) / (hi - lo)

def score_neighborhood_months(features: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the composite score for every (neighborhood, year_month) row.

    Args:
        features: Merged neighborhood-month table.

    Returns:
        DataFrame with columns:
          neighborhood, year_month,
          scaled_<feature>  (one per score feature — normalised [0,1]),
          score_311_sub, score_fire_sub, pressure_score (0–100)
        Sorted by neighborhood then year_month.
    """
    df = features[["neighborhood", "year_month", *ALL_SCORE_FEATURES]].copy()

    # Fill NaN avg columns before normalisation
    df["avg_closure_days"]      = df["avg_closure_days"].fillna(_NAN_FILL)
    df["avg_suppression_units"] = df["avg_suppression_units"].fillna(_NAN_FILL)

    # Min-max scale each feature
    scaled_cols_311  = []
    scaled_cols_fire = []

    for col in SCORE_FEATURES_311:
        sc = f"scaled_{col}"
        df[sc] = _minmax(df[col])
        scaled_cols_311.append(sc)

    for col in SCORE_FEATURES_FIRE:
        sc = f"scaled_{col}"
        df[sc] = _minmax(df[col])
        scaled_cols_fire.append(sc)

    # Sub-scores (mean within each bucket)
    df["score_311_sub"]  = df[scaled_cols_311].mean(axis=1)
    df["score_fire_sub"] = df[scaled_cols_fire].mean(axis=1)

    # Composite raw: weighted combination
    raw = WEIGHT_311 * df["score_311_sub"] + WEIGHT_FIRE * df["score_fire_sub"]

    # Rescale to 0–100
    df["pressure_score"] = (raw * 100).round(2)

    # Drop the intermediate raw feature columns (keep scaled_ for transparency)
    df = df.drop(columns=list(ALL_SCORE_FEATURES))

    return df.sort_values(["neighborhood", "year_month"], ignore_index=True)


def compute_scores(features: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-neighborhood composite issue-pressure scores.

    Aggregates monthly scores to the neighborhood level by taking the mean
    of the monthly pressure_score values.

    Args:
        features: Merged neighborhood-month table from build_analysis_table.

    Returns:
        41-row DataFrame with columns:
          neighborhood, mean_pressure_score, rank,
          mean_311_sub, mean_fire_sub
        Sorted descending by mean_pressure_score.
    """
    monthly = score_neighborhood_months(features)

    summary = (
        monthly.groupby("neighborhood")
        .agg(
            mean_pressure_score=("pressure_score",  "mean"),
            mean_311_sub        =("score_311_sub",   "mean"),
            mean_fire_sub       =("score_fire_sub",  "mean"),
        )
        .round(2)
        .reset_index()
        .sort_values("mean_pressure_score", ascending=False, ignore_index=True)
    )
    summary["rank"] = range(1, len(summary) + 1)

    # Reorder columns
    return summary[["rank", "neighborhood", "mean_pressure_score", "mean_311_sub", "mean_fire_sub"]]

