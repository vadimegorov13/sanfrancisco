"""
Analysis pipeline orchestrator.

Entry point: run_pipeline(output_dir)

Pipeline steps
--------------
[1/9] Load 311 and fire tables from MySQL
[2/9] Filter 311 categories
[3/9] Filter fire incidents
[4/9] Normalize neighborhood labels
[5/9] Build 311 neighborhood-month features
[6/9] Build fire neighborhood-month features
[7/9] Merge feature tables
[8/9] Generate figures
[9/9] Run downstream analysis steps

Downstream steps are called through thin wrappers that catch
NotImplementedError and log a skip message, so the pipeline still completes
and saves all artifacts even if a step is not yet implemented.
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
from src.preprocessing.filters_311 import filter_311
from src.preprocessing.filters_fire import filter_fire
from src.preprocessing.merger import build_analysis_table
from src.preprocessing.neighborhood_normalizer import apply_neighborhood_normalization

# SQL queries — load only the columns the pipeline needs
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


# Logging setup
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


# Main entry point
def run_pipeline(output_dir: str = "outputs") -> None:
    """
    Run the complete neighborhood issue-pressure analysis pipeline.

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

    # [1/9] Load raw tables
    log.info("[1/9] Loading 311 and fire tables from MySQL")
    with DatabaseConnector() as db:
        raw_311  = db.query(_SQL_311)
        raw_fire = db.query(_SQL_FIRE)
    log.info(f"      sf_311_cases      : {len(raw_311):,} rows")
    log.info(f"      sf_fire_incidents : {len(raw_fire):,} rows")

    # [2/9] Filter 311
    log.info("[2/9] Filtering 311")
    df_311 = filter_311(raw_311)
    raw_311 = None  # release memory
    log.info(f"      rows after filter : {len(df_311):,}")

    # [3/9] Filter fire
    log.info("[3/9] Filtering fire incidents")
    df_fire = filter_fire(raw_fire)
    raw_fire = None
    log.info(f"      rows after filter : {len(df_fire):,}")

    # [4/9] Normalize neighborhoods
    log.info("[4/9] Normalizing neighborhood labels")
    df_311  = apply_neighborhood_normalization(df_311,  col="analysis_neighborhood")
    df_fire = apply_neighborhood_normalization(df_fire, col="neighborhood_district")
    log.info(f"      311  rows after normalization : {len(df_311):,}")
    log.info(f"      fire rows after normalization : {len(df_fire):,}")

    # Save filtered tables (useful for debugging and demo)
    df_311.to_csv(tables_dir  / "filtered_311.csv",  index=False)
    df_fire.to_csv(tables_dir / "filtered_fire.csv", index=False)
    log.debug("      filtered_311.csv and filtered_fire.csv saved")

    # [5/9] Build 311 neighborhood-month features
    log.info("[5/9] Building 311 neighborhood-month features")
    features_311 = build_311_features(df_311)
    log.info(f"      shape : {features_311.shape[0]} rows × {features_311.shape[1]} cols")
    features_311.to_csv(tables_dir / "features_311_neighborhood_month.csv", index=False)

    # [6/9] Build fire neighborhood-month features
    log.info("[6/9] Building fire neighborhood-month features")
    features_fire = build_fire_features(df_fire)
    log.info(f"      shape : {features_fire.shape[0]} rows × {features_fire.shape[1]} cols")
    features_fire.to_csv(tables_dir / "features_fire_neighborhood_month.csv", index=False)

    # [7/9] Merge
    log.info("[7/9] Merging feature tables")
    merged = build_analysis_table(features_311, features_fire)
    log.info(f"      merged shape : {merged.shape[0]} rows × {merged.shape[1]} cols")
    merged.to_csv(tables_dir / "neighborhood_month.csv", index=False)

    # [8/9] Figures
    log.info("[8/9] Generating figures")
    from .plotter import save_all_figures
    n_figs = save_all_figures(merged, figures_dir)
    log.info(f"      {n_figs} figure(s) saved to {figures_dir}/")

    log.info("[9/9] Running downstream analysis steps")
    _run_scorer(merged, tables_dir, figures_dir, log)
    _run_clusterer(merged, tables_dir, figures_dir, log)
    _run_anomaly(merged, tables_dir, figures_dir, log)
    _run_robustness(merged, tables_dir, summaries_dir, log)

    _write_summary(merged, df_311, df_fire, summaries_dir, log)

    log.info(f"Done. All outputs saved to {out}/")

# Downstream step wrappers
def _run_scorer(
    merged: pd.DataFrame,
    tables_dir: Path,
    figures_dir: Path,
    log: logging.Logger,
) -> None:
    try:
        from .scorer import compute_scores, score_neighborhood_months
        log.info("      [8] Computing composite issue-pressure scores")

        monthly_scores = score_neighborhood_months(merged)
        monthly_scores.to_csv(tables_dir / "neighborhood_month_scores.csv", index=False)
        log.info(f"           saved neighborhood_month_scores.csv — {len(monthly_scores):,} rows")

        scores = compute_scores(merged)
        scores.to_csv(tables_dir / "neighborhood_scores.csv", index=False)
        log.info(f"           saved neighborhood_scores.csv — {len(scores):,} rows")
        log.info(f"           top 5: {scores.head(5)['neighborhood'].tolist()}")

        from .plotter import save_score_figure
        save_score_figure(scores, figures_dir)
        log.info("           saved top_neighborhoods_score.png")

    except NotImplementedError:
        log.info("      [8] Scorer not yet implemented — skipping")


def _run_clusterer(
    merged: pd.DataFrame,
    tables_dir: Path,
    figures_dir: Path,
    log: logging.Logger,
) -> None:
    try:
        from .clusterer import run_clustering
        log.info("      [9] Running hierarchical clustering")
        assignments, profiles = run_clustering(merged)
        assignments.to_csv(tables_dir / "cluster_assignments.csv", index=False)
        profiles.to_csv(tables_dir / "cluster_profiles.csv", index=False)
        log.info(f"           saved cluster_assignments.csv — {len(assignments):,} neighborhoods")
        log.info(f"           saved cluster_profiles.csv — {len(profiles):,} clusters")

        for _, row in profiles.iterrows():
            nbhds = assignments.loc[
                assignments["cluster"] == row["cluster"], "neighborhood"
            ].tolist() # type: ignore
            log.info(
                f"           cluster {int(row['cluster'])} "
                f"(n={int(row['n_neighborhoods'])}): {', '.join(sorted(nbhds))}" # type: ignore
            )

        from .plotter import save_cluster_figures
        n_figs = save_cluster_figures(merged, assignments, profiles, figures_dir)
        log.info(f"           saved {n_figs} clustering figure(s) to {figures_dir}/")

    except NotImplementedError:
        log.info("      [9] Clusterer not yet implemented — skipping")


def _run_anomaly(
    merged: pd.DataFrame,
    tables_dir: Path,
    figures_dir: Path,
    log: logging.Logger,
) -> None:
    try:
        from .anomaly import FLAG_MIN_FEATURES, run_anomaly_detection
        log.info("      [10] Running anomaly detection")
        anomalies = run_anomaly_detection(merged)
        anomalies.to_csv(tables_dir / "anomaly_scores.csv", index=False)
        log.info(f"            saved anomaly_scores.csv — {len(anomalies):,} rows")

        flagged = anomalies[anomalies["anomaly_score"] >= FLAG_MIN_FEATURES]
        log.info(f"            flagged rows (≥{FLAG_MIN_FEATURES} features spiked): {len(flagged):,}")
        if len(flagged):
            top5 = flagged.head(5)[["neighborhood", "year_month", "anomaly_score", "top_feature", "top_z"]]
            for _, r in top5.iterrows():
                log.info(
                    f"            #{int(r['anomaly_score'])} spikes — "
                    f"{r['neighborhood']} {r['year_month']} "
                    f"(top: {r['top_feature']} z={r['top_z']})"
                )

        from .plotter import save_anomaly_figure
        save_anomaly_figure(anomalies, figures_dir)
        log.info("            saved anomaly_scatter.png")

    except NotImplementedError:
        log.info("      [10] Anomaly detection not yet implemented — skipping")


def _run_robustness(
    merged: pd.DataFrame,
    tables_dir: Path,
    summaries_dir: Path,
    log: logging.Logger,
) -> None:
    try:
        from .robustness import build_report, run_robustness
        log.info("      [11] Running robustness checks")

        results = run_robustness(merged)

        # Save tabular results as CSV
        sw: pd.DataFrame = results["score_weights"]   # type: ignore[assignment]
        fd: pd.DataFrame = results["feature_drop"]    # type: ignore[assignment]
        ck: pd.DataFrame = results["cluster_k"]       # type: ignore[assignment]
        at: pd.DataFrame = results["anomaly_threshold"] # type: ignore[assignment]

        sw.to_csv(tables_dir / "robustness_score_weights.csv",    index=False)
        fd.to_csv(tables_dir / "robustness_feature_drop.csv",     index=False)
        ck.to_csv(tables_dir / "robustness_cluster_k.csv",        index=False)
        at.to_csv(tables_dir / "robustness_anomaly_threshold.csv", index=False)
        log.info("           saved 4 robustness CSV(s) to tables/")

        # Save markdown report
        report = build_report(results)
        (summaries_dir / "robustness_report.md").write_text(report, encoding="utf-8")
        log.info("           saved robustness_report.md")

    except NotImplementedError:
        log.info("      [11] Robustness checks not yet implemented — skipping")


# Summary markdown
def _write_summary(
    merged: pd.DataFrame,
    df_311: pd.DataFrame,
    df_fire: pd.DataFrame,
    summaries_dir: Path,
    log: logging.Logger,
) -> None:
    n_nbhd   = merged["neighborhood"].nunique()
    n_months = merged["year_month"].nunique()

    top5_311 = (
        merged.groupby("neighborhood")["total_311_count"].sum()
        .sort_values(ascending=False)
        .head(5)
    )
    top5_fire = (
        merged.groupby("neighborhood")["total_fire_count"].sum()
        .sort_values(ascending=False)
        .head(5)
    )

    lines = [
        "# Analysis Summary",
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
        f"| Merged table | {len(merged):,} rows × {merged.shape[1]} cols "
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
    ]

    (summaries_dir / "analysis_summary.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    log.debug("      analysis_summary.md written")
