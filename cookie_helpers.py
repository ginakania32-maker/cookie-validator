"""
Helper utilities for cookie parsing, normalization, and authentication detection.
Production-ready helper functions with comprehensive type hints.
"""

import re
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from http.cookiejar import Cookie, CookieJar
import time

from config import CookieFormat, ValidationStatus, CONFIG


logger = logging.getLogger(__name__)


class CookieNormalizer:
    """Normalize and parse cookies from various formats."""
    
    @staticmethod
    def detect_format(file_path: str) -> CookieFormat:
        """
        Auto-detect cookie file format.
        
        Args:
            file_path: Path to cookie file
            
        Returns:
            CookieFormat enum value
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Check for JSON format
            if content.startswith('{') or content.startswith('['):
                try:
                    json.loads(content)
                    return CookieFormat.JSON
                except json.JSONDecodeError:
                    pass
            
            # Check for Netscape format
            if content.startswith('#'):
                return CookieFormat.NETSCAPE
            
            # Check for Netscape-style content
            lines = content.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        return CookieFormat.NETSCAPE
            
            return CookieFormat.UNKNOWN
        except Exception as e:
            logger.error(f"Error detecting format for {file_path}: {e}")
            return CookieFormat.UNKNOWN
    
    @staticmethod
    def parse_netscape(file_path: str) -> List[Dict[str, Any]]:
        """
        Parse Netscape cookies.txt format.
        
        Format:
        # domain flag path secure expiration name value
        
        Args:
            file_path: Path to Netscape cookies.txt
            
        Returns:
            List of cookie dictionaries
        """
        cookies = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) < 7:
                        logger.warning(f"Skipping malformed cookie line: {line}")
                        continue
                    
                    try:
                        cookie = {
                            'domain': parts[0],
                            'flag': parts[1],
                            'path': parts[2],
                            'secure': parts[3].lower() == 'true',
                            'expiration': int(parts[4]) if parts[4] else 0,
                            'name': parts[5],
                            'value': parts[6],
                        }
                        cookies.append(cookie)
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error parsing cookie: {e}")
                        continue
            
            logger.info(f"Parsed {len(cookies)} cookies from {file_path}")
            return cookies
        except Exception as e:
            logger.error(f"Error parsing Netscape cookies: {e}")
            return []
    
    @staticmethod
    def parse_json(file_path: str) -> List[Dict[str, Any]]:
        """
        Parse JSON cookie format from browser extensions.
        
        Args:
            file_path: Path to JSON cookies file
            
        Returns:
            List of cookie dictionaries
        """
        cookies = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both array and object formats
            if isinstance(data, list):
                cookies = data
            elif isinstance(data, dict):
                # Try to extract cookies from common keys
                for key in ['cookies', 'cookie', 'data', 'items']:
                    if key in data and isinstance(data[key], list):
                        cookies = data[key]
                        break
            
            logger.info(f"Parsed {len(cookies)} cookies from {file_path}")
            return cookies
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON cookies: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing JSON: {e}")
            return []
    
    @staticmethod
    def normalize_cookies(cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize cookie fields to standard format.
        
        Args:
            cookies: List of raw cookie dictionaries
            
        Returns:
            List of normalized cookies
        """
        normalized = []
        
        for cookie in cookies:
            normalized_cookie = {
                'domain': cookie.get('domain', ''),
                'path': cookie.get('path', '/'),
                'name': cookie.get('name', ''),
                'value': cookie.get('value', ''),
                'secure': cookie.get('secure', False),
                'httponly': cookie.get('httpOnly', cookie.get('httponly', False)),
                'expiration': cookie.get('expiration', cookie.get('expirationDate', 0)),
            }
            
            # Validate required fields
            if normalized_cookie['name'] and normalized_cookie['domain']:
                normalized.append(normalized_cookie)
        
        return normalized


class CookieJarBuilder:
    """Build httpx-compatible CookieJar from parsed cookies."""
    
    @staticmethod
    def build_from_dict(cookies: List[Dict[str, Any]]) -> CookieJar:
        """
        Build CookieJar from cookie dictionaries.
        
        Args:
            cookies: List of normalized cookie dictionaries
            
        Returns:
            CookieJar instance
        """
        jar = CookieJar()
        
        for cookie_dict in cookies:
            try:
                # Create http.cookiejar.Cookie
                cookie = Cookie(
                    version=0,
                    name=cookie_dict['name'],
                    value=cookie_dict['value'],
                    port=None,
                    port_specified=False,
                    domain=cookie_dict['domain'],
                    domain_specified=True,
                    domain_initial_dot=cookie_dict['domain'].startswith('.'),
                    path=cookie_dict['path'],
                    path_specified=True,
                    secure=cookie_dict.get('secure', False),
                    expires=cookie_dict.get('expiration'),
                    discard=False,
                    comment=None,
                    comment_url=None,
                    rest={},
                    rfc2109=False,
                )
                jar.set_cookie(cookie)
            except Exception as e:
                logger.warning(f"Error adding cookie {cookie_dict.get('name')}: {e}")
                continue
        
        logger.info(f"Built CookieJar with {len(jar)} cookies")
        return jar
    
    @staticmethod
    def build_from_file(file_path: str) -> Tuple[CookieJar, bool]:
        """
        Complete workflow: detect format, parse, normalize, and build jar.
        
        Args:
            file_path: Path to cookie file
            
        Returns:
            Tuple of (CookieJar, success_bool)
        """
        # Detect format
        fmt = CookieNormalizer.detect_format(file_path)
        logger.info(f"Detected format: {fmt.value}")
        
        # Parse based on format
        if fmt == CookieFormat.NETSCAPE:
            cookies = CookieNormalizer.parse_netscape(file_path)
        elif fmt == CookieFormat.JSON:
            cookies = CookieNormalizer.parse_json(file_path)
        else:
            logger.error(f"Unknown cookie format: {file_path}")
            return CookieJar(), False
        
        # Normalize
        normalized = CookieNormalizer.normalize_cookies(cookies)
        
        if not normalized:
            logger.error(f"No valid cookies found in {file_path}")
            return CookieJar(), False
        
        # Build jar
        jar = CookieJarBuilder.build_from_dict(normalized)
        return jar, True


class AuthenticationDetector:
    """Detect authentication status from responses."""
    
    @staticmethod
    def is_authenticated(
        status_code: int,
        response_text: str,
        response_headers: Dict[str, str]
    ) -> bool:
        """
        Detect if response indicates authentication.
        
        Args:
            status_code: HTTP status code
            response_text: Response body text
            response_headers: Response headers
            
        Returns:
            True if authenticated, False otherwise
        """
        # Check status codes
        if status_code == 401 or status_code == 403:
            return False
        
        if status_code >= 400:
            return False
        
        # Check for auth indicators in response
        response_lower = response_text.lower()
        for indicator in CONFIG.AUTH_INDICATORS:
            if indicator in response_lower:
                return True
        
        # Check for API response patterns
        try:
            if 'application/json' in response_headers.get('content-type', '').lower():
                data = json.loads(response_text)
                if isinstance(data, dict) and any(
                    k in data for k in ['account', 'data', 'user', 'droplets', 'projects']
                ):
                    return True
        except json.JSONDecodeError:
            pass
        
        return False
    
    @staticmethod
    def get_validation_status(
        status_code: int,
        response_text: str,
        response_headers: Dict[str, str],
        redirect_url: Optional[str] = None
    ) -> ValidationStatus:
        """
        Determine validation status from response characteristics.
        
        Args:
            status_code: HTTP status code
            response_text: Response body text
            response_headers: Response headers
            redirect_url: Redirect URL if applicable
            
        Returns:
            ValidationStatus enum value
        """
        response_lower = response_text.lower()
        
        # Check for rate limit
        if status_code in CONFIG.RATE_LIMIT_STATUS_CODES:
            for header in CONFIG.RATE_LIMIT_HEADERS:
                if header in response_headers:
                    return ValidationStatus.RATE_LIMIT
            if 'rate limit' in response_lower:
                return ValidationStatus.RATE_LIMIT
        
        # Check for CAPTCHA
        if any(x in response_lower for x in ['captcha', 'challenge', 'verify']):
            return ValidationStatus.CAPTCHA
        
        # Check for login required
        if redirect_url and '/login' in redirect_url.lower():
            return ValidationStatus.EXPIRED
        
        if any(x in response_lower for x in CONFIG.EXPIRED_INDICATORS):
            return ValidationStatus.EXPIRED
        
        # Check for forbidden
        if status_code == 403:
            return ValidationStatus.FORBIDDEN
        
        # Check for unauthorized
        if status_code == 401:
            return ValidationStatus.INVALID
        
        # Check for invalid indicators
        if any(x in response_lower for x in CONFIG.INVALID_INDICATORS):
            return ValidationStatus.INVALID
        
        # Check for authenticated
        if AuthenticationDetector.is_authenticated(status_code, response_text, response_headers):
            return ValidationStatus.VALID
        
        # Default
        if status_code == 200:
            return ValidationStatus.VALID
        
        return ValidationStatus.ERROR
    
    @staticmethod
    def detect_email(response_text: str) -> Optional[str]:
        """
        Attempt to detect email from response.
        
        Args:
            response_text: Response body text
            
        Returns:
            Email string or None
        """
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        matches = re.findall(email_pattern, response_text)
        return matches[0] if matches else None


class EndpointDiscoverer:
    """Discover authenticated endpoints based on API patterns."""
    
    @staticmethod
    def get_endpoints() -> List[str]:
        """
        Get list of endpoints to test in priority order.
        
        Returns:
            List of endpoint paths
        """
        return CONFIG.AUTH_ENDPOINTS
    
    @staticmethod
    def build_full_url(endpoint: str) -> str:
        """
        Build full URL from endpoint path.
        
        Args:
            endpoint: Endpoint path
            
        Returns:
            Full URL
        """
        return f"{CONFIG.BASE_URL}{endpoint}"


class FileScanner:
    """Scan directories for cookie files."""
    
    @staticmethod
    def scan_recursive(directory: str) -> List[str]:
        """
        Recursively scan directory for cookie files.
        
        Args:
            directory: Directory path
            
        Returns:
            List of cookie file paths
        """
        cookie_files = []
        dir_path = Path(directory)
        
        if not dir_path.exists():
            logger.error(f"Directory not found: {directory}")
            return []
        
        # Match patterns
        patterns = CONFIG.COOKIE_PATTERNS
        
        for pattern in patterns:
            matches = dir_path.rglob(pattern)
            cookie_files.extend([str(f) for f in matches if f.is_file()])
        
        # Remove duplicates and sort
        cookie_files = sorted(set(cookie_files))
        
        logger.info(f"Found {len(cookie_files)} cookie files in {directory}")
        return cookie_files
