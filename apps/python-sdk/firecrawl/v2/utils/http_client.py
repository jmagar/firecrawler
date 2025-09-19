"""
HTTP client utilities for v2 API.
"""

import time
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urlunparse, urljoin
import requests
from .get_version import get_version

version = get_version()

class HttpClient:
    """HTTP client with retry logic and error handling."""
    
    def __init__(self, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = self._normalize_base_url(api_url)

    @staticmethod
    def _normalize_base_url(api_url: str) -> str:
        """Ensure the base API URL includes a scheme and host."""
        if not api_url:
            raise ValueError("API URL cannot be empty")

        parsed = urlparse(api_url)

        # Already well-formed with scheme and host
        if parsed.scheme and parsed.netloc:
            return api_url.rstrip('/')

        # Handle inputs that urlparse misclassifies as a scheme (e.g. "localhost:3000")
        if parsed.scheme and not parsed.netloc:
            candidate = f"{parsed.scheme}:{parsed.path}".lstrip('/')
            if not candidate:
                raise ValueError(f"Invalid API URL '{api_url}': missing hostname")

            host, path = candidate, ''
            if '/' in candidate:
                host, remainder = candidate.split('/', 1)
                path = f"/{remainder}"

            scheme = 'http' if host.startswith(('localhost', '127.', '0.0.0.0')) else 'https'
            normalized = urlunparse((scheme, host, path, '', parsed.query, ''))
            return normalized.rstrip('/')

        # Handle protocol-relative URLs (e.g. //api.example.com)
        if api_url.startswith('//'):
            normalized = f"https:{api_url}"
            parsed = urlparse(normalized)
            if parsed.netloc:
                return normalized.rstrip('/')
            raise ValueError(f"Invalid API URL '{api_url}': missing hostname")

        # Reject relative paths like /foo/bar early
        if api_url.startswith('/'):
            raise ValueError(
                f"Invalid API URL '{api_url}': expected hostname, got relative path"
            )

        # Treat strings without scheme (e.g. localhost:3000 or api.example.com)
        if not parsed.scheme and not parsed.netloc and parsed.path:
            host_path = parsed.path
            host, path = host_path, ''
            if '/' in host_path:
                host, remainder = host_path.split('/', 1)
                path = f"/{remainder}"

            if not host:
                raise ValueError(f"Invalid API URL '{api_url}': missing hostname")

            scheme = 'http' if host.startswith(('localhost', '127.', '0.0.0.0')) else 'https'
            normalized = urlunparse((scheme, host, path, '', parsed.query, ''))
            return normalized.rstrip('/')

        raise ValueError(
            f"Invalid API URL '{api_url}': expected absolute URL with scheme"
        )

    def _build_url(self, endpoint: str) -> str:
        base = urlparse(self.api_url)
        ep = urlparse(endpoint)

        # Absolute or protocol-relative (has netloc)
        if ep.netloc:
            # Different host: keep path/query but force base host/scheme (no token leakage)
            path = ep.path or "/"
            if (ep.hostname or "") != (base.hostname or ""):
                return urlunparse((base.scheme or "https", base.netloc, path, "", ep.query, ""))
            # Same host: normalize scheme to base
            return urlunparse((base.scheme or "https", base.netloc, path, "", ep.query, ""))

        # Relative (including leading slash or not)
        base_str = self.api_url if self.api_url.endswith("/") else f"{self.api_url}/"
        # Guard protocol-relative like //host/path slipping through as “relative”
        if endpoint.startswith("//"):
            ep2 = urlparse(f"https:{endpoint}")
            path = ep2.path or "/"
            return urlunparse((base.scheme or "https", base.netloc, path, "", ep2.query, ""))
        return urljoin(base_str, endpoint)
    
    def _prepare_headers(self, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        """Prepare headers for API requests."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }
        
        if idempotency_key:
            headers['x-idempotency-key'] = idempotency_key
            
        return headers
    
    def post(
        self,
        endpoint: str,
        data: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        retries: int = 3,
        backoff_factor: float = 0.5
    ) -> requests.Response:
        """Make a POST request with retry logic."""
        if headers is None:
            headers = self._prepare_headers()

        data['origin'] = f'python-sdk@{version}'
            
        url = self._build_url(endpoint)
        
        last_exception = None
        
        for attempt in range(retries):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=timeout
                )

                if response.status_code == 502:
                    if attempt < retries - 1:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                
                return response
                
            except requests.RequestException as e:
                last_exception = e
                if attempt == retries - 1:
                    raise e
                time.sleep(backoff_factor * (2 ** attempt))
        
        # This should never be reached due to the exception handling above
        raise last_exception or Exception("Unexpected error in POST request")
    
    def get(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        retries: int = 3,
        backoff_factor: float = 0.5
    ) -> requests.Response:
        """Make a GET request with retry logic."""
        if headers is None:
            headers = self._prepare_headers()

        url = self._build_url(endpoint)
        
        last_exception = None
        
        for attempt in range(retries):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout
                )
                
                if response.status_code == 502:
                    if attempt < retries - 1:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                
                return response
                
            except requests.RequestException as e:
                last_exception = e
                if attempt == retries - 1:
                    raise e
                time.sleep(backoff_factor * (2 ** attempt))
        
        # This should never be reached due to the exception handling above
        raise last_exception or Exception("Unexpected error in GET request")
    
    def delete(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        retries: int = 3,
        backoff_factor: float = 0.5
    ) -> requests.Response:
        """Make a DELETE request with retry logic."""
        if headers is None:
            headers = self._prepare_headers()
            
        url = self._build_url(endpoint)
        
        last_exception = None
        
        for attempt in range(retries):
            try:
                response = requests.delete(
                    url,
                    headers=headers,
                    timeout=timeout
                )
                
                if response.status_code == 502:
                    if attempt < retries - 1:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                
                return response
                
            except requests.RequestException as e:
                last_exception = e
                if attempt == retries - 1:
                    raise e
                time.sleep(backoff_factor * (2 ** attempt))
        
        # This should never be reached due to the exception handling above
        raise last_exception or Exception("Unexpected error in DELETE request")
