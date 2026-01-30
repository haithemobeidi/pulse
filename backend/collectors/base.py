"""
Base Collector Class

All data collectors inherit from BaseCollector and implement the collect() method
to gather system information for a specific snapshot.
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Base class for all system data collectors"""

    def __init__(self, db):
        """
        Initialize collector with database connection.

        Args:
            db: Database instance for storing collected data
        """
        self.db = db
        self.name = self.__class__.__name__

    @abstractmethod
    def collect(self, snapshot_id: int) -> bool:
        """
        Collect system data and store in database for snapshot.

        Args:
            snapshot_id: ID of snapshot to associate data with

        Returns:
            True if collection succeeded, False otherwise
        """
        pass

    def _safe_execute(self, func, *args, **kwargs) -> Optional[any]:
        """
        Safely execute function with error handling and logging.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result from function or None if error occurs
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"{self.name} error: {e}")
            return None

    def log_info(self, message: str):
        """Log info message"""
        logger.info(f"[{self.name}] {message}")

    def log_warning(self, message: str):
        """Log warning message"""
        logger.warning(f"[{self.name}] {message}")

    def log_error(self, message: str):
        """Log error message"""
        logger.error(f"[{self.name}] {message}")
