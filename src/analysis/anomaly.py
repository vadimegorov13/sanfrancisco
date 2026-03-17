"""
Anomaly detection on neighborhood-months.

Method
------
Per-feature z-scores are computed across all 984 neighborhood-month rows.
The anomaly score for a row is the count of features whose z-score exceeds a
threshold (|z| > Z_THRESHOLD, default 2.0).  A row is flagged as anomalous
when at least FLAG_MIN_FEATURES features breach the threshold.

Why this approach?
  * Fully transparent — every score component is a z-score the reader can
    verify by hand.
  * Directional — we flag only the high-pressure direction (z > +threshold),
    not unusually quiet months, which better matches the issue-pressure framing.
  * No hyper-parameters beyond the threshold and minimum-feature count.
  * Easy to compare against the composite pressure score (Story 8).

Output columns
--------------
  neighborhood       — canonical label
  year_month         — "YYYY-MM"
  anomaly_score      — count of features with z > Z_THRESHOLD  (0..16)
  top_feature        — name of the feature with the highest z-score
  top_z              — that feature's z-score (rounded to 2 dp)
  n_features_spiked  — synonym of anomaly_score (kept for readability)
  <feature>_z        — individual z-score columns for all ANOMALY_FEATURES

Rows are sorted descending by anomaly_score, then by year_month.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Features included in anomaly scoring.
# Per-category count sub-columns are included so the reader can see *which*
# category drove a spike in a given month.
ANOMALY_FEATURES: list[str] = [
    "total_311_count",
    "count_street_pavement",
    "count_sidewalk_curb",
    "count_sewer_drainage",
    "count_streetlights",
    "count_traffic_signs",
    "count_trees",
    "distinct_issue_groups",
    "avg_closure_days",
    "total_fire_count",
    "count_fire_building",
    "count_fire_electrical",
    "count_fire_gas",
    "count_fire_water",
    "total_fire_injuries",
    "avg_suppression_units",
]

# A feature is "spiking" when its z-score exceeds this value (one-tailed, high).
Z_THRESHOLD: float = 2.0

# Minimum number of spiking features for a row to be considered anomalous.
FLAG_MIN_FEATURES: int = 2

# NaN fill before z-scoring (same logic as scorer — no activity = baseline 0).
_NAN_FILL: float = 0.0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def run_anomaly_detection(v1: pd.DataFrame) -> pd.DataFrame:
    """
    Identify unusual neighborhood-months using per-feature z-scores.

    Args:
        v1: Merged neighborhood-month table from build_v1_analysis_table.
            Must contain columns: neighborhood, year_month, and all
            columns in ANOMALY_FEATURES.

    Returns:
        DataFrame sorted descending by anomaly_score. Contains:
          neighborhood, year_month, anomaly_score, top_feature, top_z,
          n_features_spiked, plus one <feature>_z column per scored feature.
        Only rows with anomaly_score >= FLAG_MIN_FEATURES are returned, plus
        all rows are included with their scores so the caller can slice further.
    """
    df = v1.copy()

    # Fill NaN in avg columns so they participate in z-scoring.
    for col in ("avg_closure_days", "avg_suppression_units"):
        if col in df.columns:
            df[col] = df[col].fillna(_NAN_FILL)

    # ---- Compute per-feature z-scores ------------------------------------
    z_cols: dict[str, str] = {}
    for feat in ANOMALY_FEATURES:
        if feat not in df.columns:
            continue
        col_z = f"{feat}_z"
        mu  = df[feat].mean()
        sigma = df[feat].std(ddof=0)
        if sigma == 0:
            df[col_z] = 0.0
        else:
            df[col_z] = (df[feat] - mu) / sigma
        z_cols[feat] = col_z

    present_z = list(z_cols.values())

    # ---- Anomaly score = count of features where z > Z_THRESHOLD ----------
    z_matrix = df[present_z].values
    df["anomaly_score"] = (z_matrix > Z_THRESHOLD).sum(axis=1).astype(int)
    df["n_features_spiked"] = df["anomaly_score"]

    # ---- Identify the single most-spiking feature per row -----------------
    if present_z:
        best_idx = np.argmax(z_matrix, axis=1)
        feat_names = list(z_cols.keys())
        df["top_feature"] = [feat_names[i] for i in best_idx]
        df["top_z"] = z_matrix[np.arange(len(df)), best_idx].round(2)
    else:
        df["top_feature"] = ""
        df["top_z"] = 0.0

    # ---- Assemble output -------------------------------------------------
    out_cols = (
        ["neighborhood", "year_month", "anomaly_score",
         "top_feature", "top_z", "n_features_spiked"]
        + present_z
    )
    result = (
        df[out_cols]
        .sort_values(["anomaly_score", "year_month"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return result
