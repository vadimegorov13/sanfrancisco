"""
Database connection for MySQL.
"""

import os
import pandas as pd
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

class DatabaseConnector:
    """
    Simple MySQL database connector.
    """
    
    def __init__(self):
        self.connection = None
        
    def connect(self):
        """
        Connect to MySQL database.
        """
        self.connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD')
        )
        print(f"Connected to database: {os.getenv('DB_NAME')}")
        return self
    
    def disconnect(self):
        """
        Close database connection.
        """
        if self.connection:
            self.connection.close()
    
    def query(self, sql: str) -> pd.DataFrame:
        """
        Execute query and return DataFrame.
        """
        return pd.read_sql(sql, self.connection)
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
