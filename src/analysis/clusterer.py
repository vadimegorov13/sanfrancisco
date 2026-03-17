"""
Hierarchical clustering of neighborhoods.

Method
------
* Unit       : neighborhood  (41 rows — mean of each month's observations)
* Features   : all numeric features, standardized with StandardScaler
* Distance   : Euclidean  (natural choice for Ward linkage)
* Linkage    : Ward        (minimises within-cluster variance; produces compact,
                           geometrically meaningful clusters)
* k          : 4 clusters  (selected after inspecting the dendrogram —
                           k=3 merges two visibly-distinct groups,
                           k=5 over-splits the low-volume tail,
                           k=4 gives four human-labellable groups)
* NaN fill   : avg_closure_days → 0.0, avg_suppression_units → 0.0
               (no activity in a month = no delay / no mobilisation)

Public API
----------
run_clustering(v1) → (assignments, profiles)
  assignments : 41 rows — neighborhood, cluster (1-indexed int)
  profiles    : k rows  — cluster, n_neighborhoods, mean of each feature
                          (un-standardised values for interpretability)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# All numeric feature columns in the merged v1 table (excluding keys).
CLUSTER_FEATURES: list[str] = [
    # 311 — volume and mix
    "total_311_count",
    "count_street_pavement",
    "count_sidewalk_curb",
    "count_sewer_drainage",
    "count_streetlights",
    "count_traffic_signs",
    "count_trees",
    "distinct_issue_groups",
    "avg_closure_days",
    # Fire — volume and severity
    "total_fire_count",
    "count_fire_building",
    "count_fire_electrical",
    "count_fire_gas",
    "count_fire_water",
    "total_fire_injuries",
    "avg_suppression_units",
]

# NaN fill value for rate/average columns that are NaN when a neighborhood
# had no relevant activity in a given month.
_NAN_FILL: float = 0.0

# Number of clusters to cut the dendrogram at.
N_CLUSTERS: int = 4


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _neighborhood_profiles(v1: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate the 984-row neighborhood-month table to one row per neighborhood
    by taking the mean of each feature over all months.

    NaN avg columns are filled with _NAN_FILL before averaging so that months
    with no activity (e.g. no fire incidents → avg_suppression_units is NaN)
    are treated as baseline rather than silently dropped.

    Returns:
        DataFrame with index = neighborhood (41 rows) and one column per
        feature in CLUSTER_FEATURES.
    """
    df = v1.copy()
    for col in ("avg_closure_days", "avg_suppression_units"):
        if col in df.columns:
            df[col] = df[col].fillna(_NAN_FILL)
    return df.groupby("neighborhood")[CLUSTER_FEATURES].mean()


def _compute_linkage(v1: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """
    Build the Ward linkage matrix from v1.

    Returns:
        (Z, labels) where Z is the scipy linkage matrix and labels is the
        ordered list of neighborhood names corresponding to the leaf order.
    """
    profiles = _neighborhood_profiles(v1)
    labels = profiles.index.tolist()
    X = StandardScaler().fit_transform(profiles.values)
    Z = linkage(X, method="ward", metric="euclidean")
    return Z, labels


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_clustering(v1: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run hierarchical clustering on the merged neighborhood-month table.

    Steps
    -----
    1. Aggregate monthly rows to one per-neighborhood mean profile.
    2. Standardise with StandardScaler (zero mean, unit variance per feature).
    3. Compute Ward linkage on Euclidean distances.
    4. Cut dendrogram at N_CLUSTERS (=4).
    5. Build assignments and cluster profile tables.

    Args:
        v1: Merged neighborhood-month table from build_v1_analysis_table.

    Returns:
        Tuple of (assignments, profiles):
          assignments  — one row per neighborhood; columns: neighborhood, cluster
          profiles     — one row per cluster; columns: cluster, n_neighborhoods,
                         then mean of every CLUSTER_FEATURES column
                         (un-standardised for human interpretability)
    """
    profiles_raw = _neighborhood_profiles(v1)
    neighborhoods = profiles_raw.index.tolist()

    # Standardise
    scaler = StandardScaler()
    X = scaler.fit_transform(profiles_raw.values)  # shape (41, 16)

    # Ward linkage + flat cut
    Z = linkage(X, method="ward", metric="euclidean")
    raw_labels = fcluster(Z, t=N_CLUSTERS, criterion="maxclust").astype(int)

    # ---- assignments table -----------------------------------------------
    assignments = (
        pd.DataFrame({"neighborhood": neighborhoods, "cluster": raw_labels})
        .sort_values("neighborhood")
        .reset_index(drop=True)
    )

    # ---- profiles table (un-standardised means) --------------------------
    profiles_raw_df = profiles_raw.copy()
    profiles_raw_df["cluster"] = raw_labels

    cluster_means = (
        profiles_raw_df
        .groupby("cluster")[CLUSTER_FEATURES]
        .mean()
        .round(3)
        .reset_index()
    )
    cluster_size = (
        assignments.groupby("cluster")
        .size()
        .rename("n_neighborhoods")
        .reset_index()
    )
    profiles = cluster_means.merge(cluster_size, on="cluster")

    return assignments, profiles
