"""
Robustness and interpretation checks.

Runs five focused sensitivity tests against the main analysis results
and writes a markdown report to summaries/robustness_report.md.

Checks
------
1. Score weight sensitivity      — vary 311/fire bucket weights; compare top-5 rankings
2. Score feature sensitivity     — drop each score feature in turn; check rank stability
3. Fire features removed         — re-score / re-cluster / re-flag with 311 features only
4. Cluster k sensitivity         — cut dendrogram at k=3, 4, 5; compare ARI and sizes
5. Anomaly threshold sensitivity — z threshold = 1.5, 2.0, 2.5; compare flagged counts

Public API
----------
run_robustness(features) → dict[str, object]
    Runs all checks; each key maps to a DataFrame or sub-dict summarising one check.

build_report(results) → str
    Formats the run_robustness output as a markdown string for saving.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.stats import spearmanr
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler

from .anomaly import ANOMALY_FEATURES, FLAG_MIN_FEATURES
from .clusterer import CLUSTER_FEATURES, N_CLUSTERS
from .scorer import SCORE_FEATURES_311, SCORE_FEATURES_FIRE

# NaN fill for avg_ columns before any computation.
_NAN_FILL = 0.0

# Fire-side column names (used to build 311-only subsets).
_FIRE_COLS: frozenset[str] = frozenset({
    "total_fire_count",
    "count_fire_building",
    "count_fire_electrical",
    "count_fire_gas",
    "count_fire_water",
    "total_fire_injuries",
    "avg_suppression_units",
})

# 311-only subsets derived from the full feature lists.
CLUSTER_FEATURES_311: list[str] = [f for f in CLUSTER_FEATURES if f not in _FIRE_COLS]
ANOMALY_FEATURES_311: list[str] = [f for f in ANOMALY_FEATURES if f not in _FIRE_COLS]


# Internal helpers ─────────────────────────────────────────────────────────────

def _fill_avgs(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("avg_closure_days", "avg_suppression_units"):
        if col in df.columns:
            df[col] = df[col].fillna(_NAN_FILL)
    return df


def _minmax(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return pd.Series(0.0, index=s.index) if hi == lo else (s - lo) / (hi - lo)


def _nbhd_score(
    features: pd.DataFrame,
    feats_311: list[str],
    feats_fire: list[str],
    w311: float,
    wfire: float,
) -> pd.Series:
    """
    Compute per-neighborhood mean pressure score (0–100) with explicit parameters.
    Returns a Series indexed by neighborhood name, sorted descending.
    """
    df = _fill_avgs(features.copy())

    feats_311  = [f for f in feats_311  if f in df.columns]
    feats_fire = [f for f in feats_fire if f in df.columns]

    sub_311 = (
        pd.DataFrame({f: _minmax(df[f]) for f in feats_311}).mean(axis=1)
        if feats_311 else pd.Series(0.0, index=df.index)
    )
    sub_fire = (
        pd.DataFrame({f: _minmax(df[f]) for f in feats_fire}).mean(axis=1)
        if feats_fire else pd.Series(0.0, index=df.index)
    )

    df["_score"] = (w311 * sub_311 + wfire * sub_fire) * 100
    return (
        df.groupby("neighborhood")["_score"]
        .mean()
        .sort_values(ascending=False)
        .rename("score")
    )


def _cluster_labels(features: pd.DataFrame, feats: list[str], k: int) -> dict[str, int]:
    """
    Cluster neighborhoods using Ward/Euclidean linkage cut at k.
    Returns {neighborhood: cluster_label}.
    """
    df    = _fill_avgs(features.copy())
    feats = [f for f in feats if f in df.columns]
    profiles = df.groupby("neighborhood")[feats].mean()
    X = StandardScaler().fit_transform(profiles.values)
    Z = linkage(X, method="ward", metric="euclidean")
    labels = fcluster(Z, t=k, criterion="maxclust").astype(int)
    return dict(zip(profiles.index.tolist(), labels.tolist()))


def _anomaly_flagged(
    features: pd.DataFrame,
    feats: list[str],
    threshold: float,
) -> pd.DataFrame:
    """
    Z-score anomaly detection with explicit feature list and threshold.
    Returns rows with at least FLAG_MIN_FEATURES features spiking above threshold.
    """
    present = [f for f in feats if f in features.columns]
    df = _fill_avgs(features[["neighborhood", "year_month"] + present].copy())

    z_cols: list[str] = []
    for feat in present:
        mu, sigma = df[feat].mean(), df[feat].std(ddof=0)
        col_z = f"{feat}_z"
        df[col_z] = 0.0 if sigma == 0 else (df[feat] - mu) / sigma
        z_cols.append(col_z)

    df["spike_count"] = (
        (df[z_cols].values > threshold).sum(axis=1).astype(int)
        if z_cols else 0
    )
    return (
        df[df["spike_count"] >= FLAG_MIN_FEATURES][["neighborhood", "year_month", "spike_count"]]
        .sort_values("spike_count", ascending=False)
        .reset_index(drop=True)
    )


def _spearman(a: pd.Series, b: pd.Series) -> float:
    """Spearman ρ between two Series aligned on their index. Ignores NaN pairs."""
    merged = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(merged) < 2:
        return float("nan")
    rho, _ = spearmanr(merged["a"], merged["b"])
    return round(float(rho), 3) # type: ignore


# Five checks ──────────────────────────────────────────────────────────────────

def _check_score_weights(features: pd.DataFrame) -> pd.DataFrame:
    """
    Vary 311/fire weight splits. Compare top-5 rankings and Spearman ρ vs baseline.
    """
    f311  = list(SCORE_FEATURES_311.keys())
    ffire = list(SCORE_FEATURES_FIRE.keys())

    variants = [
        ("60 / 40  (baseline)", 0.60, 0.40),
        ("80 / 20",             0.80, 0.20),
        ("50 / 50",             0.50, 0.50),
        ("311 only  (100 / 0)", 1.00, 0.00),
    ]

    baseline = _nbhd_score(features, f311, ffire, 0.60, 0.40)

    rows = []
    for label, w311, wfire in variants:
        scores = _nbhd_score(features, f311, ffire, w311, wfire)
        rows.append({
            "variant":              label,
            "top_5":                ", ".join(scores.head(5).index.tolist()),
            "spearman_vs_baseline": _spearman(baseline, scores),
        })

    return pd.DataFrame(rows)


def _check_feature_drop(features: pd.DataFrame) -> pd.DataFrame:
    """
    Drop each score feature in turn. Report top-5 overlap with baseline and Spearman ρ.
    """
    f311  = list(SCORE_FEATURES_311.keys())
    ffire = list(SCORE_FEATURES_FIRE.keys())

    baseline      = _nbhd_score(features, f311, ffire, 0.60, 0.40)
    baseline_top5 = set(baseline.head(5).index.tolist())

    rows = []
    for drop_feat in (f311 + ffire):
        new_311  = [f for f in f311  if f != drop_feat]
        new_fire = [f for f in ffire if f != drop_feat]
        scores   = _nbhd_score(features, new_311, new_fire, 0.60, 0.40)
        top5     = scores.head(5).index.tolist()
        rows.append({
            "dropped_feature":            drop_feat,
            "top5_overlap_with_baseline": len(set(top5) & baseline_top5),
            "spearman_vs_baseline":       _spearman(baseline, scores),
            "top_5":                      ", ".join(top5),
        })

    return pd.DataFrame(rows)


def _check_fire_off(features: pd.DataFrame) -> dict[str, object]:
    """
    Re-run score, cluster, and anomaly with fire features removed (311 only).
    """
    f311  = list(SCORE_FEATURES_311.keys())
    ffire = list(SCORE_FEATURES_FIRE.keys())

    # ── Score ─────────────────────────────────────────────────────────────────
    baseline_scores = _nbhd_score(features, f311, ffire, 0.60, 0.40)
    fireoff_scores  = _nbhd_score(features, f311, [],     1.00, 0.00)

    baseline_top5 = baseline_scores.head(5).index.tolist()
    fireoff_top5  = fireoff_scores.head(5).index.tolist()

    # ── Clustering ────────────────────────────────────────────────────────────
    bl_labels = _cluster_labels(features, CLUSTER_FEATURES,     N_CLUSTERS)
    fo_labels = _cluster_labels(features, CLUSTER_FEATURES_311, N_CLUSTERS)
    shared    = sorted(set(bl_labels) & set(fo_labels))
    cluster_ari = round(
        adjusted_rand_score([bl_labels[n] for n in shared], [fo_labels[n] for n in shared]),
        3,
    )

    # ── Anomaly ───────────────────────────────────────────────────────────────
    baseline_anom = _anomaly_flagged(features, ANOMALY_FEATURES,     2.0)
    fireoff_anom  = _anomaly_flagged(features, ANOMALY_FEATURES_311, 2.0)

    def _top(df: pd.DataFrame) -> str:
        if df.empty:
            return "none"
        r = df.iloc[0]
        return f"{r['neighborhood']} {r['year_month']} (score={int(r['spike_count'])})"

    return {
        "score": {
            "baseline_top5": baseline_top5,
            "fireoff_top5":  fireoff_top5,
            "top5_overlap":  len(set(baseline_top5) & set(fireoff_top5)),
            "spearman_rho":  _spearman(baseline_scores, fireoff_scores),
        },
        "cluster": {
            "ari": cluster_ari,
        },
        "anomaly": {
            "baseline_flagged": len(baseline_anom),
            "fireoff_flagged":  len(fireoff_anom),
            "top_baseline":     _top(baseline_anom),
            "top_fireoff":      _top(fireoff_anom),
        },
    }


def _check_cluster_k(features: pd.DataFrame) -> pd.DataFrame:
    """
    Cut the dendrogram at k=3, 4, 5. Report cluster sizes and ARI vs k=4 baseline.
    """
    baseline_labels = _cluster_labels(features, CLUSTER_FEATURES, N_CLUSTERS)
    neighborhoods   = sorted(baseline_labels.keys())
    bl              = [baseline_labels[n] for n in neighborhoods]

    rows = []
    for k in (3, 4, 5):
        lk    = [_cluster_labels(features, CLUSTER_FEATURES, k)[n] for n in neighborhoods]
        sizes = sorted(pd.Series(lk).value_counts().tolist(), reverse=True)
        ari   = 1.0 if k == N_CLUSTERS else round(adjusted_rand_score(bl, lk), 3)
        rows.append({
            "k":                  k,
            "cluster_sizes":      " / ".join(str(s) for s in sizes),
            "ari_vs_k4_baseline": ari,
            "note":               "baseline" if k == N_CLUSTERS else "",
        })

    return pd.DataFrame(rows)


def _check_anomaly_threshold(features: pd.DataFrame) -> pd.DataFrame:
    """
    Run anomaly detection at z=1.5, 2.0, 2.5. Compare flagged counts and top anomaly.
    """
    rows = []
    for threshold in (1.5, 2.0, 2.5):
        flagged = _anomaly_flagged(features, ANOMALY_FEATURES, threshold)
        top = (
            f"{flagged.iloc[0]['neighborhood']} {flagged.iloc[0]['year_month']}"
            if not flagged.empty else "none"
        )
        rows.append({
            "z_threshold":  threshold,
            "flagged_rows": len(flagged),
            "top_anomaly":  top,
            "note":         "baseline" if threshold == 2.0 else "",
        })

    return pd.DataFrame(rows)


# Public API ───────────────────────────────────────────────────────────────────

def run_robustness(features: pd.DataFrame) -> dict[str, object]:
    """
    Run all five robustness checks against the merged neighborhood-month table.

    Args:
        features: Merged neighborhood-month table from build_analysis_table.

    Returns:
        Dict with keys:
          "score_weights"      — DataFrame: top-5 and Spearman ρ per weight variant
          "feature_drop"       — DataFrame: top-5 overlap and ρ per dropped feature
          "fire_off"           — dict: score / cluster / anomaly sub-results
          "cluster_k"          — DataFrame: cluster sizes and ARI at k=3,4,5
          "anomaly_threshold"  — DataFrame: flagged counts and top anomaly at z=1.5,2.0,2.5
    """
    return {
        "score_weights":     _check_score_weights(features),
        "feature_drop":      _check_feature_drop(features),
        "fire_off":          _check_fire_off(features),
        "cluster_k":         _check_cluster_k(features),
        "anomaly_threshold": _check_anomaly_threshold(features),
    }


def build_report(results: dict[str, object]) -> str:
    """
    Format run_robustness() output as a markdown report.

    Args:
        results: Output of run_robustness().

    Returns:
        Markdown string suitable for saving as robustness_report.md.
    """
    lines: list[str] = [
        "# Robustness and Interpretation Report",
        "",
        f"**Generated:** {date.today().isoformat()}",
        "",
        "The analysis was re-run under small design variations to confirm that "
        "key findings do not depend on any single modelling choice.",
        "",
        "---",
        "",
    ]

    # 1. Score weight sensitivity ──────────────────────────────────────────────
    sw: pd.DataFrame = results["score_weights"]  # type: ignore[assignment]
    lines += [
        "## 1. Score weight sensitivity",
        "",
        "Baseline weights: 311 = 60 %, fire = 40 %.",
        "",
        "| Variant | Top 5 neighborhoods | Spearman ρ vs baseline |",
        "| ------- | ------------------- | ---------------------- |",
    ]
    for _, row in sw.iterrows():
        lines.append(f"| {row['variant']} | {row['top_5']} | {row['spearman_vs_baseline']} |")
    lines.append("")

    min_rho_sw = float(sw["spearman_vs_baseline"].min())
    if min_rho_sw >= 0.95:
        lines.append(f"Rankings are highly stable across all weight variants (min ρ = {min_rho_sw}).")
    elif min_rho_sw >= 0.80:
        lines.append(f"Rankings are broadly stable across weight variants (min ρ = {min_rho_sw}).")
    else:
        lines.append(f"Rankings show meaningful variation under weight changes (min ρ = {min_rho_sw}).")

    lines += ["", "---", ""]

    # 2. Score feature sensitivity ─────────────────────────────────────────────
    fd: pd.DataFrame = results["feature_drop"]  # type: ignore[assignment]
    lines += [
        "## 2. Score feature sensitivity",
        "",
        "One of the six score features is dropped at a time. "
        "Overlap = count of baseline top-5 neighborhoods still in the top 5.",
        "",
        "| Dropped feature | Top-5 overlap | Spearman ρ vs baseline | Top 5 neighborhoods |",
        "| --------------- | ------------- | ---------------------- | ------------------- |",
    ]
    for _, row in fd.iterrows():
        lines.append(
            f"| {row['dropped_feature']} | {row['top5_overlap_with_baseline']} / 5 | "
            f"{row['spearman_vs_baseline']} | {row['top_5']} |"
        )
    lines.append("")

    min_overlap = int(fd["top5_overlap_with_baseline"].min())
    min_rho_fd  = float(fd["spearman_vs_baseline"].min())
    if min_overlap >= 4 and min_rho_fd >= 0.90:
        lines.append(
            f"Top-5 rankings are robust to any single-feature removal "
            f"(min overlap {min_overlap}/5, min ρ = {min_rho_fd})."
        )
    else:
        lines.append(
            f"Some features have notable leverage on rankings "
            f"(min overlap {min_overlap}/5, min ρ = {min_rho_fd})."
        )

    lines += ["", "---", ""]

    # 3. Fire features removed ─────────────────────────────────────────────────
    fo: dict = results["fire_off"]  # type: ignore[assignment]
    lines += [
        "## 3. Effect of removing fire features",
        "",
        "### Scoring",
        "",
        "| | Top 5 neighborhoods |",
        "| --- | --- |",
        f"| Full features (60/40) | {', '.join(fo['score']['baseline_top5'])} |",
        f"| 311 only | {', '.join(fo['score']['fireoff_top5'])} |",
        "",
        f"Top-5 overlap: **{fo['score']['top5_overlap']} / 5**  |  "
        f"Spearman ρ vs baseline: **{fo['score']['spearman_rho']}**",
        "",
        "### Clustering",
        "",
        f"ARI between full-feature and 311-only clustering "
        f"(k = {N_CLUSTERS}): **{fo['cluster']['ari']}**",
        "",
    ]
    ari_cl = float(fo["cluster"]["ari"])
    if ari_cl >= 0.80:
        lines.append("Cluster structure is largely preserved without fire features.")
    elif ari_cl >= 0.60:
        lines.append(
            "Cluster structure changes moderately; fire features add some neighbourhood differentiation."
        )
    else:
        lines.append(
            "Cluster structure changes substantially; fire features materially affect groupings."
        )

    lines += [
        "",
        "### Anomaly detection",
        "",
        "| | Flagged rows (z ≥ 2.0) | Top anomaly |",
        "| --- | --- | --- |",
        f"| Full features | {fo['anomaly']['baseline_flagged']} | {fo['anomaly']['top_baseline']} |",
        f"| 311 only | {fo['anomaly']['fireoff_flagged']} | {fo['anomaly']['top_fireoff']} |",
        "",
        "---",
        "",
    ]

    # 4. Cluster k sensitivity ─────────────────────────────────────────────────
    ck: pd.DataFrame = results["cluster_k"]  # type: ignore[assignment]
    lines += [
        "## 4. Cluster k sensitivity",
        "",
        "Ward linkage dendrogram cut at k = 3, 4, 5. "
        "ARI is computed against the baseline (k = 4) assignment.",
        "",
        "| k | Cluster sizes | ARI vs k=4 baseline | Note |",
        "| - | ------------- | ------------------- | ---- |",
    ]
    for _, row in ck.iterrows():
        lines.append(
            f"| {int(row['k'])} | {row['cluster_sizes']} | {row['ari_vs_k4_baseline']} | {row['note']} |"
        )
    lines.append("")

    alt_ari = ck[ck["k"] != N_CLUSTERS]["ari_vs_k4_baseline"]
    min_ari_k = float(alt_ari.min()) if not alt_ari.empty else 1.0
    if min_ari_k >= 0.75:
        lines.append(f"Cluster structure is stable across k=3–5 (min ARI = {min_ari_k}).")
    else:
        lines.append(f"Cluster structure is sensitive to k choice (min ARI = {min_ari_k}).")

    lines += ["", "---", ""]

    # 5. Anomaly threshold sensitivity ─────────────────────────────────────────
    at: pd.DataFrame = results["anomaly_threshold"]  # type: ignore[assignment]
    lines += [
        "## 5. Anomaly threshold sensitivity",
        "",
        f"Z-score threshold varied. A row is flagged when ≥ {FLAG_MIN_FEATURES} features exceed the threshold.",
        "",
        "| z threshold | Flagged rows | Top anomaly | Note |",
        "| ----------- | ------------ | ----------- | ---- |",
    ]
    for _, row in at.iterrows():
        lines.append(
            f"| {row['z_threshold']} | {row['flagged_rows']} | {row['top_anomaly']} | {row['note']} |"
        )
    lines.append("")

    unique_tops = at["top_anomaly"].unique()
    if len(unique_tops) == 1:
        lines.append(
            f"The top anomaly ({unique_tops[0]}) is consistent across all thresholds tested."
        )
    else:
        lines.append("The top anomaly changes between thresholds; review threshold choice.")

    # Summary ──────────────────────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Score weight sensitivity**: min Spearman ρ = {min_rho_sw} across 311/fire weight variants.",
        f"- **Feature drop sensitivity**: min top-5 overlap = {min_overlap}/5 "
        f"when any single score feature is removed.",
        f"- **Fire removal — scoring**: Spearman ρ = {fo['score']['spearman_rho']} vs baseline; "
        f"top-5 overlap = {fo['score']['top5_overlap']}/5.",
        f"- **Fire removal — clustering**: ARI = {fo['cluster']['ari']} "
        f"({'structure largely preserved' if ari_cl >= 0.80 else 'some structural change'}).",
        f"- **Cluster k**: min ARI = {min_ari_k} across k=3–5.",
        "- **Anomaly threshold**: "
        + ("top anomaly unchanged across z=1.5–2.5." if len(unique_tops) == 1 else "top anomaly shifts with threshold."),
    ]

    return "\n".join(lines) + "\n"
