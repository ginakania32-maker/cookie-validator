"""
Configuration module for DigitalOcean Cookie Validator.
Centralized settings for API endpoints, timeouts, headers, and validation rules.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict
from pathlib import Path
from enum import Enum


class ValidationStatus(Enum):
    """Validation status enumeration."""
    VALID = "VALID"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMIT = "RATE_LIMIT"
    CAPTCHA = "CAPTCHA"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    ERROR = "ERROR"


class CookieFormat(Enum):
    """Supported cookie formats."""
    NETSCAPE = "netscape"
    JSON = "json"
    UNKNOWN = "unknown"


@dataclass
class AppConfig:
    """Application configuration."""
    
    # Base settings
    BASE_URL: str = "https://cloud.digitalocean.com"
    TIMEOUT: int = 15
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    MAX_WORKERS: int = 10
    QUEUE_SIZE: int = 100
    
    # Paths
    PROJECT_ROOT: Path = field(default_factory=lambda: Path(__file__).parent)
    LOGS_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "logs")
    RESULTS_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "results")
    VALID_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "valid")
    INVALID_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "invalid")
    EXPIRED_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "expired")
    HELPERS_DIR: Path = field(default_factory=lambda: Path(__file__).parent / "helpers")
    
    # Create directories on init
    def __post_init__(self):
        for dir_path in [self.LOGS_DIR, self.RESULTS_DIR, self.VALID_DIR, 
                        self.INVALID_DIR, self.EXPIRED_DIR]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    # API Endpoints (priority order)
    AUTH_ENDPOINTS: List[str] = field(default_factory=lambda: [
        "/v2/account",
        "/v2/auth",
        "/api/account",
        "/v2/projects",
        "/v2/droplets",
        "/account/",
        "/settings/",
        "/api/v2/account",
    ])
    
    # Auth detection patterns
    AUTH_INDICATORS: List[str] = field(default_factory=lambda: [
        "account",
        "droplet",
        "project",
        "floating_ip",
        "database",
        "kubernetes",
        "app",
        "cdn",
    ])
    
    EXPIRED_INDICATORS: List[str] = field(default_factory=lambda: [
        "sign in",
        "login",
        "authenticate",
        "session expired",
        "please log in",
    ])
    
    INVALID_INDICATORS: List[str] = field(default_factory=lambda: [
        "unauthorized",
        "not authenticated",
        "access denied",
    ])
    
    # Browser headers (realistic fingerprint)
    DEFAULT_HEADERS: Dict[str, str] = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    })
    
    # Cookie file patterns
    COOKIE_PATTERNS: List[str] = field(default_factory=lambda: [
        "cookies.txt",
        "*.txt",
        "*.json",
    ])
    
    # Enable debug mode
    DEBUG: bool = False
    VERBOSE: bool = False
    SAVE_RESPONSE_HTML: bool = True
    
    # Proxy & rotation
    ENABLE_PROXY_ROTATION: bool = True
    ENABLE_USER_AGENT_ROTATION: bool = True
    
    # Rate limit detection
    RATE_LIMIT_STATUS_CODES: List[int] = field(default_factory=lambda: [429, 503])
    RATE_LIMIT_HEADERS: List[str] = field(default_factory=lambda: [
        "X-RateLimit-Limit",
        "Retry-After",
        "X-Rate-Limit",
    ])


@dataclass
class ValidationResult:
    """Result of a validation operation."""
    cookie_file: str
    status: ValidationStatus
    response_code: int = 0
    response_reason: str = ""
    endpoint_tested: str = ""
    response_body: str = ""
    error_message: str = ""
    timestamp: str = ""
    redirect_url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    detected_email: str = ""
    
    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "cookie_file": self.cookie_file,
            "status": self.status.value,
            "response_code": self.response_code,
            "response_reason": self.response_reason,
            "endpoint_tested": self.endpoint_tested,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
            "redirect_url": self.redirect_url,
        }


# Global config instance
CONFIG = AppConfig()
