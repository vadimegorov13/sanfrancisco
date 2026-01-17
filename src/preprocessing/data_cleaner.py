"""
Basic data cleaning functions.

TODO: implement something when needed
"""

import pandas as pd


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
	"""
	Handle missing values.

	TODO
	"""

	return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
	"""
	Remove duplicate rows.

	TODO
	"""

	return df.drop_duplicates()


def detect_outliers_iqr(df: pd.DataFrame) -> pd.Series:
	"""
	Detect outliers.

	TODO
	"""

	return pd.Series([False] * len(df))
