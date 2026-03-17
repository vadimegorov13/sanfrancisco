"""
Figure generation for the v1 pipeline.

All figures are generated from the merged neighborhood-month table (v1)
produced by build_v1_analysis_table. Every function saves a PNG and returns 1
so the caller can count saved figures.

Figures produced:
  monthly_311_volume.png          — total filtered 311 cases per month
  top_neighborhoods_311.png       — top 15 neighborhoods by 311 volume
  311_category_distribution.png   — 311 case totals by issue category
  top_neighborhoods_fire.png      — top 15 neighborhoods by fire incident volume
  fire_category_distribution.png  — fire incident totals by category
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless — must be set before importing pyplot

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------
try:
    plt.style.use("seaborn-v0_8-whitegrid")
except OSError:
    plt.style.use("ggplot")

_COLOR_311  = "#4C72B0"
_COLOR_FIRE = "#DD8452"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def save_all_figures(v1: pd.DataFrame, figures_dir: Path) -> int:
    """
    Generate and save all v1 figures.

    Args:
        v1:          Merged neighborhood-month table (984 rows × 18 cols).
        figures_dir: Output directory for PNG files (created if absent).

    Returns:
        Number of figures saved.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    n += _monthly_311_volume(v1, figures_dir)
    n += _top_neighborhoods_311(v1, figures_dir)
    n += _category_distribution_311(v1, figures_dir)
    n += _top_neighborhoods_fire(v1, figures_dir)
    n += _category_distribution_fire(v1, figures_dir)
    return n


# ---------------------------------------------------------------------------
# Individual figure functions
# ---------------------------------------------------------------------------

def _save(fig: plt.Figure, path: Path) -> int:
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return 1


def _monthly_311_volume(v1: pd.DataFrame, out: Path) -> int:
    """Line chart: total filtered 311 cases per month across all neighborhoods."""
    monthly = (
        v1.groupby("year_month")["total_311_count"]
        .sum()
        .reset_index()
        .sort_values("year_month")
    )

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(
        monthly["year_month"],
        monthly["total_311_count"],
        marker="o",
        linewidth=1.8,
        markersize=4,
        color=_COLOR_311,
    )
    ax.set_title("Monthly Filtered 311 Issue Volume — All Neighborhoods (2024–2025)", fontsize=12)
    ax.set_xlabel("Month")
    ax.set_ylabel("Total filtered 311 cases")
    ax.tick_params(axis="x", rotation=45)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.tight_layout()
    return _save(fig, out / "monthly_311_volume.png")


def _top_neighborhoods_311(v1: pd.DataFrame, out: Path) -> int:
    """Horizontal bar chart: top 15 neighborhoods by total filtered 311 cases."""
    top = (
        v1.groupby("neighborhood")["total_311_count"]
        .sum()
        .sort_values(ascending=True)   # ascending so longest bar is at top
        .tail(15)
    )

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(top.index, top.values, color=_COLOR_311)
    ax.set_title("Top 15 Neighborhoods by Total Filtered 311 Cases (2024–2025)", fontsize=12)
    ax.set_xlabel("Total filtered cases")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.tight_layout()
    return _save(fig, out / "top_neighborhoods_311.png")


def _category_distribution_311(v1: pd.DataFrame, out: Path) -> int:
    """Horizontal bar chart: aggregate 311 cases by issue category."""
    # Named count columns and their display labels
    count_cols = {
        "Street / Pavement": "count_street_pavement",
        "Sidewalk / Curb":   "count_sidewalk_curb",
        "Sewer / Drainage":  "count_sewer_drainage",
        "Streetlights":      "count_streetlights",
        "Traffic Signs":     "count_traffic_signs",
        "Trees":             "count_trees",
    }
    # "Other" = whatever is in total but not in the six named groups
    named_total = sum(v1[col].sum() for col in count_cols.values())
    other_total = int(v1["total_311_count"].sum()) - int(named_total)

    totals = {label: int(v1[col].sum()) for label, col in count_cols.items()}
    if other_total > 0:
        totals["Other (water, damage, blockage)"] = other_total

    series = pd.Series(totals).sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(series.index, series.values, color=_COLOR_311)
    ax.set_title("Filtered 311 Cases by Issue Category — 2024 to 2025 Total", fontsize=12)
    ax.set_xlabel("Total filtered cases")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.tight_layout()
    return _save(fig, out / "311_category_distribution.png")


def _top_neighborhoods_fire(v1: pd.DataFrame, out: Path) -> int:
    """Horizontal bar chart: top 15 neighborhoods by total filtered fire incidents."""
    top = (
        v1.groupby("neighborhood")["total_fire_count"]
        .sum()
        .sort_values(ascending=True)
        .tail(15)
    )

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(top.index, top.values, color=_COLOR_FIRE)
    ax.set_title("Top 15 Neighborhoods by Filtered Fire Incidents (2024–2025)", fontsize=12)
    ax.set_xlabel("Total filtered incidents")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.tight_layout()
    return _save(fig, out / "top_neighborhoods_fire.png")


def _category_distribution_fire(v1: pd.DataFrame, out: Path) -> int:
    """Horizontal bar chart: aggregate fire incidents by incident category."""
    count_cols = {
        "Building fire":  "count_fire_building",
        "Electrical":     "count_fire_electrical",
        "Gas leak":       "count_fire_gas",
        "Water utility":  "count_fire_water",
    }

    totals = {label: int(v1[col].sum()) for label, col in count_cols.items()}
    series = pd.Series(totals).sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(series.index, series.values, color=_COLOR_FIRE)
    ax.set_title("Filtered Fire Incidents by Category — 2024 to 2025 Total", fontsize=12)
    ax.set_xlabel("Total filtered incidents")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}"))
    fig.tight_layout()
    return _save(fig, out / "fire_category_distribution.png")


def save_score_figure(scores: pd.DataFrame, out: Path) -> int:
    """
    Horizontal bar chart: all 41 neighborhoods ranked by mean pressure score.

    Args:
        scores: Output of compute_scores() — one row per neighborhood,
                columns include 'neighborhood' and 'mean_pressure_score'.
        out:    Directory to write top_neighborhoods_score.png.
    """
    sorted_scores = scores.sort_values("mean_pressure_score", ascending=True)

    fig, ax = plt.subplots(figsize=(9, 9))
    bars = ax.barh(
        sorted_scores["neighborhood"],
        sorted_scores["mean_pressure_score"],
        color="#2ca02c",
    )
    ax.set_title(
        "Neighborhood Issue-Pressure Score\n(mean monthly composite, 2024–2025)",
        fontsize=12,
    )
    ax.set_xlabel("Mean pressure score (0–100)")
    ax.axvline(
        sorted_scores["mean_pressure_score"].median(),
        color="grey", linewidth=1, linestyle="--", label="median",
    )
    ax.legend(fontsize=9)
    fig.tight_layout()
    return _save(fig, out / "top_neighborhoods_score.png")

# Clustering figures

def save_cluster_figures(
    v1: pd.DataFrame,
    assignments: pd.DataFrame,
    profiles: pd.DataFrame,
    figures_dir: Path,
) -> int:
    """
    Generate and save two clustering figures:
      dendrogram.png              — Ward linkage dendrogram for 41 neighborhoods
      cluster_profile_heatmap.png — standardised mean feature values per cluster

    Args:
        v1:          Merged neighborhood-month table (needed to recompute linkage).
        assignments: Output of run_clustering() — neighborhood + cluster columns.
        profiles:    Output of run_clustering() — cluster profiles (raw means).
        figures_dir: Directory to save PNG files.

    Returns:
        Number of figures saved (2).
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    n += _dendrogram_figure(v1, assignments, figures_dir)
    n += _cluster_heatmap_figure(profiles, figures_dir)
    return n


def _dendrogram_figure(
    v1: pd.DataFrame,
    assignments: pd.DataFrame,
    out: Path,
) -> int:
    """Ward linkage dendrogram with leaf labels coloured by cluster assignment."""
    from scipy.cluster.hierarchy import dendrogram as _scipy_dendrogram
    from sklearn.preprocessing import StandardScaler

    from .clusterer import N_CLUSTERS, _compute_linkage

    Z, labels = _compute_linkage(v1)

    # Build a label → cluster map for leaf colouring
    label_to_cluster = assignments.set_index("neighborhood")["cluster"].to_dict()
    n_clusters = N_CLUSTERS
    _palette = plt.cm.get_cmap("tab10", n_clusters)
    cluster_colors = {c: _palette(c - 1) for c in range(1, n_clusters + 1)}

    # Determine color threshold so that exactly N_CLUSTERS branches are coloured
    # The threshold sits just below the (N_CLUSTERS-1)th merge from the top.
    color_threshold = float(Z[-(n_clusters - 1), 2]) * 0.999

    fig, ax = plt.subplots(figsize=(6, 10))
    ddata = _scipy_dendrogram(
        Z,
        labels=labels,
        orientation="left",
        ax=ax,
        color_threshold=color_threshold,
        above_threshold_color="grey",
        leaf_font_size=8,
    )
    ax.set_title(
        "Ward Hierarchical Clustering — 41 SF Neighborhoods\n"
        "(Euclidean distance, standardised features, 2024–2025)",
        fontsize=10,
    )
    ax.set_xlabel("Ward linkage distance")
    ax.axvline(color_threshold, color="red", linewidth=1, linestyle="--",
               label=f"k={n_clusters} cut")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return _save(fig, out / "dendrogram.png")


def _cluster_heatmap_figure(profiles: pd.DataFrame, out: Path) -> int:
    """
    Heatmap of standardised cluster profiles.

    Each row is a cluster; each column is a feature. Values are z-scored
    across clusters so relative differences are visible regardless of scale.
    Un-standardised absolute means are annotated inside each cell.
    """
    import seaborn as sns

    from .clusterer import CLUSTER_FEATURES

    feature_cols = [c for c in CLUSTER_FEATURES if c in profiles.columns]
    raw = profiles.set_index("cluster")[feature_cols]

    # Z-score across clusters per feature (column-wise)
    z = (raw - raw.mean()) / raw.std().replace(0, 1)

    # Shorten feature names for display
    short_names = {
        "total_311_count":      "311 total",
        "count_street_pavement":"street pav.",
        "count_sidewalk_curb":  "sidewalk",
        "count_sewer_drainage": "sewer",
        "count_streetlights":   "streetlights",
        "count_traffic_signs":  "traffic signs",
        "count_trees":          "trees",
        "distinct_issue_groups":"311 diversity",
        "avg_closure_days":     "avg closure d.",
        "total_fire_count":     "fire total",
        "count_fire_building":  "fire building",
        "count_fire_electrical":"fire elec.",
        "count_fire_gas":       "fire gas",
        "count_fire_water":     "fire water",
        "total_fire_injuries":  "fire injuries",
        "avg_suppression_units":"suppression un.",
    }
    z.columns = [short_names.get(c, c) for c in z.columns]
    raw_display = raw.copy()
    raw_display.columns = z.columns

    # Cluster labels with size annotation
    if "n_neighborhoods" in profiles.columns:
        size_map = profiles.set_index("cluster")["n_neighborhoods"].to_dict()
        z.index = [f"Cluster {c}  (n={size_map.get(c, '?')})" for c in z.index]
        raw_display.index = z.index

    fig, ax = plt.subplots(figsize=(12, 4))
    sns.heatmap(
        z,
        annot=raw_display.round(1),
        fmt="g",
        cmap="RdYlGn_r",
        center=0,
        linewidths=0.5,
        ax=ax,
        cbar_kws={"label": "z-score across clusters"},
    )
    ax.set_title(
        "Cluster Profiles — Mean Feature Values per Cluster\n"
        "(colour = z-score; annotation = raw mean)",
        fontsize=11,
    )
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.xticks(rotation=40, ha="right", fontsize=8)
    fig.tight_layout()
    return _save(fig, out / "cluster_profile_heatmap.png")
