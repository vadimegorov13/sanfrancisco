"""
Utility to download San Francisco open data and load into MySQL.

Used Copilot to help generate this code.
"""

import time
from typing import Literal, Optional

import pandas as pd
import requests

from src.database.db_connector import DatabaseConnector
from src.utils.logger import FileLogger

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
  # Initialize logger
  logger = FileLogger(name=f'sf_data_{dataset_id}')
  logger.info(f'Starting data injection for dataset {dataset_id} into table {table_name}')
  logger.info(f'Parameters: select_columns={select_columns}, where_clause={where_clause}, if_exists={if_exists}, max_rows={max_rows}, start_offset={start_offset}')
  
  # Use SODA2 API endpoint
  base_url = f'https://data.sfgov.org/resource/{dataset_id}.json'
  all_records = []
  offset = start_offset

  logger.info(f'Downloading data from SF Open Data (dataset: {dataset_id})...', print_to_console=True)
  if start_offset > 0:
    logger.info(f'Starting from offset: {start_offset}', print_to_console=True)

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
          logger.info('Retry successful', print_to_console=True)
        break  # Success, exit retry loop
      except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        logger.error(f'Connection error at offset {offset}: {e}', exc_info=True)
        if attempt < 5:
          wait_time = attempt * 2  # 2s, 4s, 6s, 8s
          logger.warning(f'Retrying in {wait_time}s... (attempt {attempt}/5)', print_to_console=True)
          time.sleep(wait_time)
        else:
          logger.critical(f'Failed after 5 attempts at offset {offset}: {e}', print_to_console=True)
          break
      except Exception as e:
        logger.error(f'Unexpected error at offset {offset}: {e}', exc_info=True, print_to_console=True)
        break
    
    # If request failed after retries
    if records is None:
      if offset == 0:
        logger.error(f'First request failed for dataset {dataset_id}. Check dataset_id or API availability.', print_to_console=True)
      else:
        logger.error(f'Request failed at offset {offset} after retries')
      break

    # Validate response
    if not isinstance(records, list):
      logger.error(f'Invalid response format at offset {offset}. Expected list, got {type(records)}', print_to_console=True)
      break
    
    if len(records) == 0:
      print(f'No more data - received 0 records at offset {offset}')
      break

    all_records.extend(records)
    logger.info(f'Offset {offset}: Downloaded {len(records)} records | Total: {len(all_records)}', print_to_console=True)

    # Check if hit the max rows limit
    if max_rows and len(all_records) >= max_rows:
      all_records = all_records[:max_rows]
      logger.info(f'Reached max_rows limit of {max_rows}', print_to_console=True)
      break

    # Check if on the last page - must be BEFORE incrementing offset
    if len(records) < MAX_SF_API_PAGE_SIZE:
      logger.info(f'Last page reached - received {len(records)} records (less than {MAX_SF_API_PAGE_SIZE})', print_to_console=True)
      break

    offset += MAX_SF_API_PAGE_SIZE
    time.sleep(1)  # Delay between requests

  if len(all_records) == 0:
    logger.critical('No records downloaded - raising ValueError')
    raise ValueError('No records downloaded')

  logger.info(f'\nTotal downloaded: {len(all_records)} records', print_to_console=True)

  # Convert to DataFrame
  df = pd.DataFrame(all_records)

  print(f'DataFrame shape: {df.shape}')
  print(f'Columns: {list(df.columns)}')

  # Convert geometry columns to JSON strings
  import json
  for col in df.columns:
    # Check if column contains dict or list objects
    if df[col].dtype == 'object':
      sample = df[col].dropna().head(1)
      if not sample.empty and isinstance(sample.iloc[0], (dict, list)):
        logger.info(f"Converting column '{col}' with dict/list objects to JSON string", print_to_console=True)
        df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)

  # Log column information before database write
  logger.info('DataFrame columns and types:')
  for col, dtype in df.dtypes.items():
    logger.info(f'  - {col}: {dtype}')

  logger.info(f"\nLoading data into table '{table_name}'...", print_to_console=True)

  # Use DatabaseConnector for MySQL connection
  try:
    with DatabaseConnector() as db:
      # Check if db.engine is available
      if db.engine is None:
        logger.critical('Database connection not established')
        raise RuntimeError('Database connection not established.')

      # Load data to MySQL in chunks
      logger.info(f'Writing {len(df)} rows to MySQL in chunks of 5000')
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

    logger.info(f"Successfully loaded {row_count} rows into '{table_name}'", print_to_console=True)
  except Exception as e:
    logger.critical(f'MySQL error while loading data into {table_name}: {e}', exc_info=True)
    raise

  if show_sample:
    # Get sample data
    query = f'SELECT * FROM {table_name} LIMIT 5'
    df = db.query(query)

    print('\nSample data:')
    print(df.head())

  # Print log file location
  log_path = logger.get_log_file_path()
  print(f'\n📝 Log file written to: {log_path}')
  logger.info('Data injection completed successfully')

  return

def inject_311_cases():
  inject_sf_dataset_to_mysql_db(
    dataset_id='vw6y-z8j6',
    table_name='sf_311_cases',
    if_exists='replace',
    show_sample=True,
  )