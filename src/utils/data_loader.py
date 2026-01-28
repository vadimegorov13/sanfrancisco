"""
Utility to download San Francisco open data and load into MySQL.

Used Copilot to help generate this code.
"""

import time
from typing import Literal, Optional

import pandas as pd
import requests

from src.database.db_connector import DatabaseConnector

MAX_SF_API_PAGE_SIZE = 1000

def inject_sf_dataset_to_mysql_db(
  dataset_id: str,
  table_name: str,
  select_columns: str = '*',
  where_clause: Optional[str] = None,
  if_exists: Literal['fail', 'replace', 'append'] = 'fail',
  max_rows: Optional[int] = None,
  start_offset: int = 0,
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
    max_rows: Limit on total rows to download
    start_offset: Starting offset for pagination (default: 0)
    show_sample: If True, print sample of downloaded data

  Returns: nothing
  """
  # Use SODA2 API endpoint
  base_url = f'https://data.sfgov.org/resource/{dataset_id}.json'
  all_records = []
  offset = start_offset

  print(f'Downloading data from SF Open Data (dataset: {dataset_id})...')
  if start_offset > 0:
    print(f'Starting from offset: {start_offset}')

  while True:
    # Build request parameters using SoQL query parameters
    params = {
      '$limit': MAX_SF_API_PAGE_SIZE,
      '$offset': offset,
      '$select': select_columns,
      '$where': where_clause,
    }

    # Make request with retry logic
    records = None
    for attempt in range(1, 6):  # Attempts 1, 2, 3, 4, 5
      try:
        response = requests.get(base_url, params=params, timeout=120)
        response.raise_for_status()
        records = response.json()
        if attempt > 1:
          print('Retry successful')
        break  # Success, exit retry loop
      except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        if attempt < 5:
          wait_time = attempt * 2  # 2s, 4s, 6s, 8s
          print(f'Connection error at offset {offset}, retrying in {wait_time}s... (attempt {attempt}/5)')
          time.sleep(wait_time)
        else:
          print(f'Failed after 5 attempts at offset {offset}: {e}')
          break
      except Exception as e:
        print(f'Error at offset {offset}: {e}')
        break
    
    # If request failed after retries
    if records is None:
      if offset == 0:
        print('First request failed. Check dataset_id or API availability.')
      break

    # Validate response
    if not isinstance(records, list):
      print(f'Invalid response format at offset {offset}')
      break
    
    if len(records) == 0:
      print(f'No more data - received 0 records at offset {offset}')
      break

    all_records.extend(records)
    print(f'Offset {offset}: Downloaded {len(records)} records | Total: {len(all_records)}')

    # Check if hit the max rows limit
    if max_rows and len(all_records) >= max_rows:
      all_records = all_records[:max_rows]
      print(f'Reached max_rows limit of {max_rows}')
      break

    # Check if on the last page - must be BEFORE incrementing offset
    if len(records) < MAX_SF_API_PAGE_SIZE:
      print(f'Last page reached - received {len(records)} records (less than {MAX_SF_API_PAGE_SIZE})')
      break

    offset += MAX_SF_API_PAGE_SIZE
    time.sleep(1)  # Delay between requests

  if len(all_records) == 0:
    raise ValueError('No records downloaded')

  print(f'\nTotal downloaded: {len(all_records)} records')

  # Convert to DataFrame
  df = pd.DataFrame(all_records)

  print(f'DataFrame shape: {df.shape}')
  print(f'Columns: {list(df.columns)}')

  # Convert geometry columns to JSON strings
  import json
  for col in df.columns:
    # Check if column contains dict objects (geometry data)
    if df[col].dtype == 'object':
      sample = df[col].dropna().head(1)
      if not sample.empty and isinstance(sample.iloc[0], dict):
        if 'type' in sample.iloc[0] and 'coordinates' in sample.iloc[0]:
          print(f"Converting geometry column '{col}' to JSON string")
          df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, dict) else x)

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
      index=True,
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

def inject_311_cases():
  inject_sf_dataset_to_mysql_db(
    dataset_id='vw6y-z8j6',
    table_name='sf_311_cases',
    if_exists='replace',
    show_sample=True,
  )