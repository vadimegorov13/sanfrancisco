"""
Utility to download San Francisco open data and load into MySQL.
"""

import time
from typing import Literal, Optional

import pandas as pd
import requests

from src.database.db_connector import DatabaseConnector


def download_sf_dataset_to_mysql(
    dataset_id: str,
    table_name: str,
    select_columns: str = '*',
    where_clause: Optional[str] = None,
    if_exists: Literal['fail', 'replace', 'append'] = 'fail',
    page_size: int = 1000,
    max_rows: Optional[int] = None,
    show_sample: bool = False,
):
  """
  Download complete dataset from San Francisco Open Data API and load into MySQL.
  Handles pagination automatically to download all rows.

  Args:
    dataset_id: SF dataset ID (e.g., 'vw6y-z8j6' for 311 cases)
    table_name: Name of the MySQL table to create/insert into
    select_columns: Comma-separated column names or '*' for all
    where_clause: Optional WHERE clause for filtering (SoQL format)
    if_exists: What to do if table exists ('fail', 'replace', 'append')
    page_size: Rows per page (max 1000 for SF API)
    max_rows: Limit on total rows to download
    show_sample: If True, print sample of downloaded data

  Returns: nothing
  """
  # Use SODA2 API endpoint
  base_url = f'https://data.sfgov.org/resource/{dataset_id}.json'
  all_records = []
  offset = 0

  print(f'Downloading data from SF Open Data (dataset: {dataset_id})...')

  while True:
    # Build request parameters using SoQL query parameters
    params = {
        '$limit': page_size,
        '$offset': offset,
        '$select': select_columns,
        '$where': where_clause,
    }

    # Make request
    try:
      response = requests.get(base_url, params, timeout=60)
      response.raise_for_status()
      records = response.json()
    except Exception as e:
      print(f'Error at offset {offset}: {e}')
      if offset == 0:
        print('First request failed. Check dataset_id or API availability.')
      break

    # Validate response
    if not records or not isinstance(records, list):
      print(f'No more data at offset {offset}')
      break

    all_records.extend(records)
    print(f'Downloaded {len(records)} records')

    # Check if hit the max rows limit
    if max_rows and len(all_records) >= max_rows:
      all_records = all_records[:max_rows]
      print(f'Reached max_rows limit of {max_rows}')
      break

    # Check if on the last page
    if len(records) < page_size:
      print('Last page reached')
      break

    offset += page_size
    time.sleep(0.5)  # Small delay to not get rate-limited

  if all_records == []:
    raise ValueError('No records downloaded')

  print(f'\nTotal downloaded: {len(all_records)} records')

  # Convert to DataFrame
  df = pd.DataFrame(all_records)

  print(f'DataFrame shape: {df.shape}')
  print(f'Columns: {list(df.columns)}')

  print(f"\nLoading data into table '{table_name}'...")

  # Use DatabaseConnector for MySQL connection
  with DatabaseConnector() as db:
    # Check if db.engine is available
    if db.engine is None:
      raise RuntimeError('Database connection not established.')

    # Load data to MySQL in chunks
    df.to_sql(
        name=table_name,
        con=db.engine,
        if_exists=if_exists,
        index=False,
        chunksize=5000,
        method='multi',
    )

    # Get row count from database
    query = f'SELECT COUNT(*) as count FROM {table_name}'
    result = db.query(query)
    row_count = result['count'].iloc[0] if not result.empty else 0

  print(f"Successfully loaded {row_count} rows into '{table_name}'")

  if show_sample:
    # Get sample data
    query = f'SELECT * FROM {table_name} LIMIT 5'
    df = db.query(query)

    print('\nSample data:')
    print(df.head())

  return
