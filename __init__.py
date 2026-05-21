"""
__init__.py - Cookie Validator Package
"""

from config import CONFIG, ValidationStatus, CookieFormat, ValidationResult
from validator import CookieValidator
from advanced_validator import AdvancedValidator, WorkerPool, ResultsManager

__version__ = "1.0.0"
__author__ = "ginakania32-maker"

__all__ = [
    "CONFIG",
    "ValidationStatus",
    "CookieFormat",
    "ValidationResult",
    "CookieValidator",
    "AdvancedValidator",
    "WorkerPool",
    "ResultsManager",
]
