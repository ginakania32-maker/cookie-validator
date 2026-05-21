"""
Logger configuration with colored output and formatting.
"""

import logging
import sys
from typing import Optional
from pathlib import Path


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colored output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[41m',   # Red background
        'RESET': '\033[0m',       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        if record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]
            reset = self.COLORS['RESET']
            record.levelname = f"{color}{record.levelname}{reset}"
            record.name = f"{color}{record.name}{reset}"
        
        return super().format(record)


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
    verbose: bool = False
) -> logging.Logger:
    """
    Setup logger with console and optional file handlers.
    
    Args:
        name: Logger name
        log_file: Optional log file path
        level: Logging level
        verbose: Enable debug output
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if verbose:
        level = logging.DEBUG
    
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    formatter = ColoredFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        
        file_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)


# Status indicators for terminal output
class StatusIndicators:
    """Terminal output indicators."""
    
    VALID = '\033[32m[VALID]\033[0m'
    INVALID = '\033[31m[INVALID]\033[0m'
    EXPIRED = '\033[33m[EXPIRED]\033[0m'
    FORBIDDEN = '\033[31m[FORBIDDEN]\033[0m'
    RATE_LIMIT = '\033[35m[RATE_LIMIT]\033[0m'
    CAPTCHA = '\033[34m[CAPTCHA]\033[0m'
    LOGIN_REQUIRED = '\033[33m[LOGIN_REQUIRED]\033[0m'
    ERROR = '\033[91m[ERROR]\033[0m'
    TESTING = '\033[36m[TESTING]\033[0m'
    PROCESSING = '\033[36m[PROCESSING]\033[0m'
    SUCCESS = '\033[32m[SUCCESS]\033[0m'
    
    @staticmethod
    def get_indicator(status: str) -> str:
        """Get indicator for status."""
        status_map = {
            'VALID': StatusIndicators.VALID,
            'INVALID': StatusIndicators.INVALID,
            'EXPIRED': StatusIndicators.EXPIRED,
            'FORBIDDEN': StatusIndicators.FORBIDDEN,
            'RATE_LIMIT': StatusIndicators.RATE_LIMIT,
            'CAPTCHA': StatusIndicators.CAPTCHA,
            'LOGIN_REQUIRED': StatusIndicators.LOGIN_REQUIRED,
            'ERROR': StatusIndicators.ERROR,
        }
        return status_map.get(status, f'[{status}]')
