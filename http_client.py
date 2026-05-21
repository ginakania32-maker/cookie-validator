"""
HTTP client utilities with proxy rotation, user-agent rotation, and retry handling.
"""

import random
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass


logger = logging.getLogger(__name__)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    
    def to_httpx_format(self) -> str:
        """Convert to httpx proxy format."""
        if self.username and self.password:
            scheme, rest = self.url.split('://', 1)
            return f"{scheme}://{self.username}:{self.password}@{rest}"
        return self.url


class UserAgentRotator:
    """Rotate user agents."""
    
    def __init__(self, user_agents: Optional[List[str]] = None):
        """
        Initialize rotator.
        
        Args:
            user_agents: List of user agents (uses defaults if None)
        """
        self.user_agents = user_agents or USER_AGENTS
        self.current_index = 0
    
    def get_next(self) -> str:
        """Get next user agent."""
        ua = random.choice(self.user_agents)
        logger.debug(f"Using user agent: {ua[:50]}...")
        return ua
    
    def get_random(self) -> str:
        """Get random user agent."""
        return self.get_next()


class ProxyRotator:
    """Rotate proxies."""
    
    def __init__(self, proxies: Optional[List[str]] = None):
        """
        Initialize proxy rotator.
        
        Args:
            proxies: List of proxy URLs
        """
        self.proxies = proxies or []
        self.current_index = 0
    
    def get_next(self) -> Optional[str]:
        """Get next proxy."""
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_index % len(self.proxies)]
        self.current_index += 1
        logger.debug(f"Using proxy: {proxy[:30]}...")
        return proxy
    
    def add_proxy(self, proxy: str):
        """Add proxy to rotation."""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
    
    def has_proxies(self) -> bool:
        """Check if proxies are configured."""
        return len(self.proxies) > 0


class HeaderBuilder:
    """Build realistic browser headers."""
    
    @staticmethod
    def build_headers(
        user_agent: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Build realistic headers.
        
        Args:
            user_agent: Custom user agent
            extra_headers: Additional headers to merge
            
        Returns:
            Dictionary of headers
        """
        from config import CONFIG
        
        headers = CONFIG.DEFAULT_HEADERS.copy()
        
        if user_agent:
            headers['User-Agent'] = user_agent
        else:
            headers['User-Agent'] = random.choice(USER_AGENTS)
        
        if extra_headers:
            headers.update(extra_headers)
        
        return headers


class RetryConfig:
    """Retry configuration."""
    
    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        status_forcelist: Optional[List[int]] = None
    ):
        """
        Initialize retry config.
        
        Args:
            max_retries: Maximum number of retries
            backoff_factor: Exponential backoff factor
            status_forcelist: HTTP status codes to retry on
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist or [429, 500, 502, 503, 504]
    
    def should_retry(self, status_code: int, attempt: int) -> bool:
        """
        Determine if request should be retried.
        
        Args:
            status_code: HTTP status code
            attempt: Current attempt number (0-indexed)
            
        Returns:
            True if should retry
        """
        if attempt >= self.max_retries:
            return False
        
        return status_code in self.status_forcelist
    
    def get_backoff_delay(self, attempt: int) -> float:
        """
        Get backoff delay for attempt.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        return self.backoff_factor * (2 ** attempt)
