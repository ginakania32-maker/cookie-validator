"""
Core validator module for cookie validation.
Single cookie validation with proper error handling.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime
from http.cookiejar import CookieJar

import httpx

from config import CONFIG, ValidationStatus, ValidationResult
from helpers.cookie_helpers import (
    CookieJarBuilder,
    AuthenticationDetector,
    EndpointDiscoverer,
)
from helpers.http_client import (
    UserAgentRotator,
    ProxyRotator,
    HeaderBuilder,
    RetryConfig,
)


logger = logging.getLogger(__name__)


class CookieValidator:
    """Main cookie validator using httpx async client."""
    
    def __init__(
        self,
        timeout: int = CONFIG.TIMEOUT,
        max_retries: int = CONFIG.MAX_RETRIES,
        proxies: Optional[list] = None,
        debug: bool = CONFIG.DEBUG,
    ):
        """
        Initialize validator.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts
            proxies: List of proxy URLs
            debug: Enable debug mode
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.debug = debug
        
        self.ua_rotator = UserAgentRotator()
        self.proxy_rotator = ProxyRotator(proxies) if proxies else ProxyRotator()
        self.retry_config = RetryConfig(max_retries=max_retries)
    
    async def validate(self, cookie_file: str) -> ValidationResult:
        """
        Validate a single cookie file.
        
        Args:
            cookie_file: Path to cookie file
            
        Returns:
            ValidationResult object
        """
        result = ValidationResult(
            cookie_file=cookie_file,
            status=ValidationStatus.ERROR,
            timestamp=datetime.now().isoformat(),
        )
        
        try:
            # Load and build cookie jar
            jar, success = CookieJarBuilder.build_from_file(cookie_file)
            
            if not success:
                result.status = ValidationStatus.ERROR
                result.error_message = "Failed to parse cookies"
                logger.error(f"{cookie_file}: Failed to parse cookies")
                return result
            
            # Get endpoints to test
            endpoints = EndpointDiscoverer.get_endpoints()
            
            # Try each endpoint
            for endpoint in endpoints:
                result = await self._test_endpoint(cookie_file, jar, endpoint)
                
                if result.status == ValidationStatus.VALID:
                    logger.info(f"Found valid endpoint: {endpoint}")
                    break
                
                if result.status == ValidationStatus.RATE_LIMIT:
                    logger.warning(f"Rate limited at {endpoint}")
                    break
            
            return result
        
        except Exception as e:
            logger.error(f"Validation error for {cookie_file}: {e}", exc_info=True)
            result.status = ValidationStatus.ERROR
            result.error_message = str(e)
            return result
    
    async def _test_endpoint(
        self,
        cookie_file: str,
        jar: CookieJar,
        endpoint: str
    ) -> ValidationResult:
        """
        Test a specific endpoint.
        
        Args:
            cookie_file: Cookie file name
            jar: CookieJar with cookies
            endpoint: API endpoint to test
            
        Returns:
            ValidationResult
        """
        result = ValidationResult(
            cookie_file=cookie_file,
            status=ValidationStatus.ERROR,
            endpoint_tested=endpoint,
            timestamp=datetime.now().isoformat(),
        )
        
        url = f"{CONFIG.BASE_URL}{endpoint}"
        
        logger.debug(f"Testing endpoint: {url}")
        
        for attempt in range(self.max_retries):
            try:
                # Build client
                client = await self._build_client(jar)
                
                async with client:
                    # Make request
                    response = await client.get(
                        url,
                        follow_redirects=True,
                        timeout=self.timeout,
                    )
                    
                    # Store result info
                    result.response_code = response.status_code
                    result.response_reason = response.reason_phrase or ""
                    result.response_body = response.text[:500]  # First 500 chars
                    result.headers = dict(response.headers)
                    
                    # Get final URL (after redirects)
                    if response.url:
                        result.redirect_url = str(response.url)
                    
                    # Detect status
                    result.status = AuthenticationDetector.get_validation_status(
                        response.status_code,
                        response.text,
                        dict(response.headers),
                        result.redirect_url,
                    )
                    
                    # Try to detect email
                    result.detected_email = AuthenticationDetector.detect_email(response.text)
                    
                    # Save response if debug and failed
                    if self.debug and result.status != ValidationStatus.VALID:
                        await self._save_debug_response(cookie_file, endpoint, response)
                    
                    logger.info(
                        f"{cookie_file} - {endpoint}: {result.status.value} "
                        f"({response.status_code})"
                    )
                    
                    return result
            
            except httpx.TimeoutException:
                logger.warning(f"Timeout on {endpoint} (attempt {attempt + 1})")
                result.error_message = "Request timeout"
                continue
            
            except httpx.RequestError as e:
                logger.warning(f"Request error on {endpoint}: {e}")
                result.error_message = str(e)
                continue
            
            except Exception as e:
                logger.error(f"Unexpected error on {endpoint}: {e}")
                result.error_message = str(e)
                continue
            
            finally:
                # Add backoff delay before retry
                if attempt < self.max_retries - 1:
                    delay = self.retry_config.get_backoff_delay(attempt)
                    await asyncio.sleep(delay)
        
        result.status = ValidationStatus.ERROR
        return result
    
    async def _build_client(self, jar: CookieJar) -> httpx.AsyncClient:
        """
        Build httpx AsyncClient with cookies and headers.
        
        Args:
            jar: CookieJar with cookies
            
        Returns:
            Configured AsyncClient
        """
        # Get headers
        user_agent = self.ua_rotator.get_next()
        headers = HeaderBuilder.build_headers(user_agent=user_agent)
        
        # Get proxy if enabled
        proxy = None
        if CONFIG.ENABLE_PROXY_ROTATION and self.proxy_rotator.has_proxies():
            proxy = self.proxy_rotator.get_next()
        
        # Create client
        client = httpx.AsyncClient(
            cookies=jar,
            headers=headers,
            proxy=proxy,
            verify=True,
            follow_redirects=True,
            timeout=self.timeout,
        )
        
        return client
    
    async def _save_debug_response(
        self,
        cookie_file: str,
        endpoint: str,
        response: httpx.Response
    ):
        """
        Save response for debugging.
        
        Args:
            cookie_file: Cookie file name
            endpoint: Endpoint tested
            response: Response object
        """
        if not CONFIG.SAVE_RESPONSE_HTML:
            return
        
        try:
            # Create debug filename
            safe_endpoint = endpoint.replace('/', '_')
            filename = f"{CONFIG.RESULTS_DIR}/debug_{safe_endpoint}_{response.status_code}.html"
            
            # Save response
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"<!-- Cookie: {cookie_file} -->\n")
                f.write(f"<!-- Status: {response.status_code} -->\n")
                f.write(f"<!-- URL: {response.url} -->\n")
                f.write(f"<!-- Headers: {dict(response.headers)} -->\n\n")
                f.write(response.text)
            
            logger.debug(f"Saved debug response: {filename}")
        
        except Exception as e:
            logger.warning(f"Error saving debug response: {e}")
