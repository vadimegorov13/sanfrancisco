"""
Analysis pipeline orchestrator.

Entry point: run_v1_pipeline(output_dir)

Pipeline steps
--------------
[1/9] Load 311 and fire tables from MySQL
[2/9] Filter 311
[3/9] Filter fire 
[4/9] Normalize neighborhood labels
[5/9] Build 311 neighborhood-month features
[6/9] Build fire neighborhood-month features
[7/9] Merge feature tables
[8/9] Generate figures
[9/9] Run downstream analysis (Stories 8-10; skipped until implemented)

Downstream steps (8-10) are called through thin wrappers that catch
NotImplementedError and log a skip message, so the pipeline still completes
and saves all data artifacts even before those stories are implemented.
"""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from src.database.db_connector import DatabaseConnector
from src.preprocessing.aggregator_311 import build_311_features
from src.preprocessing.aggregator_fire import build_fire_features
from src.preprocessing.filters_311 import filter_311_v1
from src.preprocessing.filters_fire import filter_fire_v1
from src.preprocessing.merger import build_v1_analysis_table
from src.preprocessing.neighborhood_normalizer import apply_neighborhood_normalization

# ---------------------------------------------------------------------------
# SQL queries — load only the columns the pipeline needs
# ---------------------------------------------------------------------------
_SQL_311 = (
    "SELECT service_request_id, requested_datetime, closed_date, "
    "service_name, service_subtype, service_details, analysis_neighborhood "
    "FROM assignment_1.sf_311_cases"
)
_SQL_FIRE = (
    "SELECT incident_number, incident_date, neighborhood_district, "
    "primary_situation, fire_injuries, civilian_injuries, suppression_units "
    "FROM assignment_1.sf_fire_incidents"
)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging(logs_dir: Path) -> logging.Logger:
    """Configure a logger that writes to both stdout and a timestamped log file."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"analysis_{timestamp}.log"

    fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    log = logging.getLogger("analyze")
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    log.addHandler(fh)
    log.addHandler(ch)

    log.info(f"Log → {log_file}")
    return log


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_v1_pipeline(output_dir: str = "outputs") -> None:
    """
    Run the complete v1 neighborhood issue-pressure analysis pipeline.

    Creates four sub-directories under output_dir:
      logs/       — timestamped log file for this run
      tables/     — CSV artifacts (filtered data, features, merged table, scores)
      figures/    — PNG plots
      summaries/  — analysis_summary.md

    Args:
        output_dir: Root output directory (created if absent). Default: "outputs".
    """
    out = Path(output_dir)
    tables_dir    = out / "tables"
    figures_dir   = out / "figures"
    logs_dir      = out / "logs"
    summaries_dir = out / "summaries"

    for d in (tables_dir, figures_dir, logs_dir, summaries_dir):
        d.mkdir(parents=True, exist_ok=True)

    log = _setup_logging(logs_dir)

    # ------------------------------------------------------------------
    # [1/9] Load raw tables
    # ------------------------------------------------------------------
    log.info("[1/9] Loading 311 and fire tables from MySQL")
    with DatabaseConnector() as db:
        raw_311  = db.query(_SQL_311)
        raw_fire = db.query(_SQL_FIRE)
    log.info(f"      sf_311_cases      : {len(raw_311):,} rows")
    log.info(f"      sf_fire_incidents : {len(raw_fire):,} rows")

    # ------------------------------------------------------------------
    # [2/9] Filter 311
    # ------------------------------------------------------------------
    log.info("[2/9] Filtering 311")
    df_311 = filter_311_v1(raw_311)
    raw_311 = None  # release memory
    log.info(f"      rows after filter : {len(df_311):,}")

    # ------------------------------------------------------------------
    # [3/9] Filter fire
    # ------------------------------------------------------------------
    log.info("[3/9] Filtering fire incidents")
    df_fire = filter_fire_v1(raw_fire)
    raw_fire = None
    log.info(f"      rows after filter : {len(df_fire):,}")

    # ------------------------------------------------------------------
    # [4/9] Normalize neighborhoods
    # ------------------------------------------------------------------
    log.info("[4/9] Normalizing neighborhood labels")
    df_311  = apply_neighborhood_normalization(df_311,  col="analysis_neighborhood")
    df_fire = apply_neighborhood_normalization(df_fire, col="neighborhood_district")
    log.info(f"      311  rows after normalization : {len(df_311):,}")
    log.info(f"      fire rows after normalization : {len(df_fire):,}")

    # Save filtered tables (useful for debugging and demo)
    df_311.to_csv(tables_dir  / "filtered_311.csv",  index=False)
    df_fire.to_csv(tables_dir / "filtered_fire.csv", index=False)
    log.debug("      filtered_311.csv and filtered_fire.csv saved")

    # ------------------------------------------------------------------
    # [5/9] Build 311 neighborhood-month features
    # ------------------------------------------------------------------
    log.info("[5/9] Building 311 neighborhood-month features")
    features_311 = build_311_features(df_311)
    log.info(f"      shape : {features_311.shape[0]} rows × {features_311.shape[1]} cols")
    features_311.to_csv(tables_dir / "features_311_neighborhood_month.csv", index=False)

    # ------------------------------------------------------------------
    # [6/9] Build fire neighborhood-month features
    # ------------------------------------------------------------------
    log.info("[6/9] Building fire neighborhood-month features")
    features_fire = build_fire_features(df_fire)
    log.info(f"      shape : {features_fire.shape[0]} rows × {features_fire.shape[1]} cols")
    features_fire.to_csv(tables_dir / "features_fire_neighborhood_month.csv", index=False)

    # ------------------------------------------------------------------
    # [7/9] Merge
    # ------------------------------------------------------------------
    log.info("[7/9] Merging feature tables")
    v1 = build_v1_analysis_table(features_311, features_fire)
    log.info(f"      merged shape : {v1.shape[0]} rows × {v1.shape[1]} cols")
    v1.to_csv(tables_dir / "v1_neighborhood_month.csv", index=False)

    # ------------------------------------------------------------------
    # [8/9] Figures
    # ------------------------------------------------------------------
    log.info("[8/9] Generating figures")
    from .plotter import save_all_figures
    n_figs = save_all_figures(v1, figures_dir)
    log.info(f"      {n_figs} figure(s) saved to {figures_dir}/")

    # ------------------------------------------------------------------
    # [9/9] Downstream analysis (stubs until Stories 8-10 are implemented)
    # ------------------------------------------------------------------
    log.info("[9/9] Running downstream analysis steps")
    _run_scorer(v1, tables_dir, figures_dir, log)
    _run_clusterer(v1, tables_dir, figures_dir, log)
    _run_anomaly(v1, tables_dir, log)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    _write_summary(v1, df_311, df_fire, summaries_dir, log)

    log.info(f"Done. All outputs saved to {out}/")


# ---------------------------------------------------------------------------
# Downstream step wrappers (catch NotImplementedError until stories land)
# ---------------------------------------------------------------------------

def _run_scorer(
    v1: pd.DataFrame,
    tables_dir: Path,
    figures_dir: Path,
    log: logging.Logger,
) -> None:
    try:
        from .scorer import compute_scores, score_neighborhood_months
        log.info("      [8] Computing composite issue-pressure scores")

        # Neighborhood-month level scores
        monthly_scores = score_neighborhood_months(v1)
        monthly_scores.to_csv(tables_dir / "neighborhood_month_scores.csv", index=False)
        log.info(f"           saved neighborhood_month_scores.csv — {len(monthly_scores):,} rows")

        # Neighborhood summary scores
        scores = compute_scores(v1)
        scores.to_csv(tables_dir / "neighborhood_scores.csv", index=False)
        log.info(f"           saved neighborhood_scores.csv — {len(scores):,} rows")
        log.info(f"           top 5: {scores.head(5)['neighborhood'].tolist()}")

        # Score figure
        from .plotter import save_score_figure
        save_score_figure(scores, figures_dir)
        log.info("           saved top_neighborhoods_score.png")

    except NotImplementedError:
        log.info("      [8] Scorer not yet implemented — skipping")


def _run_clusterer(
    v1: pd.DataFrame,
    tables_dir: Path,
    figures_dir: Path,
    log: logging.Logger,
) -> None:
    try:
        from .clusterer import run_clustering
        log.info("      [9] Running hierarchical clustering")
        assignments, profiles = run_clustering(v1)
        assignments.to_csv(tables_dir / "cluster_assignments.csv", index=False)
        profiles.to_csv(tables_dir / "cluster_profiles.csv", index=False)
        log.info(f"           saved cluster_assignments.csv — {len(assignments):,} neighborhoods")
        log.info(f"           saved cluster_profiles.csv — {len(profiles):,} clusters")

        # Log cluster composition
        for _, row in profiles.iterrows():
            nbhds = assignments.loc[
                assignments["cluster"] == row["cluster"], "neighborhood"
            ].tolist()
            log.info(
                f"           cluster {int(row['cluster'])} "
                f"(n={int(row['n_neighborhoods'])}): {', '.join(sorted(nbhds))}"
            )

        # Figures: dendrogram + cluster profile heatmap
        from .plotter import save_cluster_figures
        n_figs = save_cluster_figures(v1, assignments, profiles, figures_dir)
        log.info(f"           saved {n_figs} clustering figure(s) to {figures_dir}/")

    except NotImplementedError:
        log.info("      [9] Clusterer not yet implemented — skipping")


def _run_anomaly(v1: pd.DataFrame, tables_dir: Path, log: logging.Logger) -> None:
    try:
        from .anomaly import run_anomaly_detection
        log.info("      [10] Running anomaly detection")
        anomalies = run_anomaly_detection(v1)
        anomalies.to_csv(tables_dir / "anomaly_scores.csv", index=False)
        log.info(f"            saved anomaly_scores.csv — {len(anomalies):,} rows")
    except NotImplementedError:
        log.info("      [10] Anomaly detection not yet implemented")


# ---------------------------------------------------------------------------
# Summary markdown
# ---------------------------------------------------------------------------

def _write_summary(
    v1: pd.DataFrame,
    df_311: pd.DataFrame,
    df_fire: pd.DataFrame,
    summaries_dir: Path,
    log: logging.Logger,
) -> None:
    n_nbhd   = v1["neighborhood"].nunique()
    n_months = v1["year_month"].nunique()

    top5_311 = (
        v1.groupby("neighborhood")["total_311_count"].sum()
        .sort_values(ascending=False)
        .head(5)
    )
    top5_fire = (
        v1.groupby("neighborhood")["total_fire_count"].sum()
        .sort_values(ascending=False)
        .head(5)
    )

    lines = [
        "# v1 Analysis Summary",
        "",
        f"**Generated:** {date.today().isoformat()}",
        "**Time window:** 2024-01 to 2025-12",
        "**Unit:** neighborhood-month",
        "",
        "## Dataset sizes",
        "",
        "| Dataset | Filtered rows |",
        "| ------- | ------------- |",
        f"| sf_311_cases (filtered) | {len(df_311):,} |",
        f"| sf_fire_incidents (filtered) | {len(df_fire):,} |",
        f"| Merged table | {len(v1):,} rows × {v1.shape[1]} cols "
        f"({n_nbhd} neighborhoods × {n_months} months) |",
        "",
        "## Top 5 neighborhoods by 311 volume",
        "",
        "| Neighborhood | Total 311 cases |",
        "| ------------ | --------------- |",
        *[f"| {nbhd} | {cnt:,} |" for nbhd, cnt in top5_311.items()],
        "",
        "## Top 5 neighborhoods by fire incident volume",
        "",
        "| Neighborhood | Total fire incidents |",
        "| ------------ | -------------------- |",
        *[f"| {nbhd} | {cnt:,} |" for nbhd, cnt in top5_fire.items()],
        "",
        "## Downstream steps",
        "",
        "| Step | Status |",
        "| ---- | ------ |",
        "| Composite score | pending |",
        "| Hierarchical clustering | pending |",
        "| Anomaly detection | pending |",
    ]

    (summaries_dir / "analysis_summary.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    log.debug("      analysis_summary.md written")
