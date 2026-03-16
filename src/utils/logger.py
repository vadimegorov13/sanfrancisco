"""
Logger utility for writing application logs to file.

Provides structured logging with timestamps and error tracking.
"""

import logging
from datetime import datetime
from pathlib import Path


class FileLogger:
  """
  Custom logger that writes to a file in the logs directory.
  """

  def __init__(self, name: str = 'app', log_dir: str = 'logs'):
    """
    Initialize the file logger.

    Args:
      name: Name of the logger (used in log file naming)
      log_dir: Directory to store log files (relative to project root)
    """
    self.name = name
    self.log_dir = Path(log_dir)
    
    # Create logs directory if it doesn't exist
    self.log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create log file with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    self.log_file = self.log_dir / f'{name}_{timestamp}.log'
    
    # Set up logger
    self.logger = logging.getLogger(name)
    self.logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    self.logger.handlers = []
    
    # Create file handler
    file_handler = logging.FileHandler(self.log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Create console handler (optional - for debugging)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    
    # Create formatter
    formatter = logging.Formatter(
      '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
      datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    self.logger.addHandler(file_handler)
    self.logger.addHandler(console_handler)
    
    # Log initialization
    self.logger.info(f'Logger initialized - writing to {self.log_file}')
  
  def debug(self, message: str, print_to_console: bool = False):
    """
    Log debug message.
    
    Args:
      message: Debug message to log
      print_to_console: If True, also print to console
    """
    self.logger.debug(message)
    if print_to_console:
      print(message)
  
  def info(self, message: str, print_to_console: bool = False):
    """
    Log info message.
    
    Args:
      message: Info message to log
      print_to_console: If True, also print to console
    """
    self.logger.info(message)
    if print_to_console:
      print(message)
  
  def warning(self, message: str, print_to_console: bool = False):
    """
    Log warning message.
    
    Args:
      message: Warning message to log
      print_to_console: If True, also print to console
    """
    self.logger.warning(message)
    if print_to_console:
      print(message)
  
  def error(self, message: str, exc_info: bool = False, print_to_console: bool = False):
    """
    Log error message.
    
    Args:
      message: Error message to log
      exc_info: If True, include exception traceback
      print_to_console: If True, also print to console
    """
    self.logger.error(message, exc_info=exc_info)
    if print_to_console:
      print(message)
  
  def critical(self, message: str, exc_info: bool = False, print_to_console: bool = False):
    """
    Log critical message.
    
    Args:
      message: Critical message to log
      exc_info: If True, include exception traceback
      print_to_console: If True, also print to console
    """
    self.logger.critical(message, exc_info=exc_info)
    if print_to_console:
      print(message)
  
  def get_log_file_path(self) -> Path:
    """Get the path to the current log file."""
    return self.log_file
  
  def read_log(self) -> str:
    """
    Read and return the entire log file contents.
    
    Returns:
      String containing all log contents
    """
    try:
      with open(self.log_file, 'r', encoding='utf-8') as f:
        return f.read()
    except Exception as e:
      return f'Error reading log file: {e}'
