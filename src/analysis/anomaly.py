from __future__ import annotations

import pandas as pd


def run_anomaly_detection(v1: pd.DataFrame) -> pd.DataFrame:
    """
    Identify unusual neighborhood-months based on the merged v1 feature table.

    Args:
        v1: Merged neighborhood-month table from build_v1_analysis_table.

    Returns:
        DataFrame with columns: neighborhood, year_month, anomaly_score,
        plus columns explaining why each row stands out.
        Sorted descending by anomaly_score.
    """
    raise NotImplementedError("Not Implemented")
