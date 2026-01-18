"""
Database connection for MySQL.
"""

import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()


class DatabaseConnector:
  """
  Simple MySQL database connector using SQLAlchemy.
  """

  def __init__(self):
    self.engine = None

  def connect(self):
    """
    Connect to MySQL database.
    """

    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '3306')
    database = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')

    # Create SQLAlchemy engine
    connection_string = f'mysql+pymysql://{user}:{password}@{host}:{port}/{database}'
    self.engine = create_engine(connection_string)

    print(f'Connected to database: {database}')
    return self

  def disconnect(self):
    """
    Close database connection.
    """

    if self.engine:
      self.engine.dispose()

  def query(self, sql: str) -> pd.DataFrame:
    """
    Execute query and return DataFrame.
    """

    if self.engine is None:
      raise RuntimeError('Database connection not established.')

    return pd.read_sql(sql, self.engine)

  def __enter__(self):
    return self.connect()

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.disconnect()
