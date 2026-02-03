# url_checks.py - HOLFY27 AutoCheck URL Accessibility Validation
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# URL accessibility and response validation checks.

"""
URL Accessibility Validation Module

Checks URLs defined in config.ini for:
- HTTP/HTTPS accessibility
- Expected response content (optional)
- Response time
"""

import time
from typing import List, Dict, Any, Optional

from .base import CheckResult

# Optional imports
try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Import config
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autocheck_config as config


#==============================================================================
# URL CHECKS
#==============================================================================

def parse_url_entry(entry: str) -> Dict[str, str]:
    """
    Parse a URL entry from config.ini.
    
    Entries can have format:
    - "https://host/path"
    - "https://host/path,Description"
    - "https://host/path,Description,expected_text"
    
    Args:
        entry: URL entry string from config.ini
        
    Returns:
        Dictionary with 'url', 'description', 'expected_text' keys
    """
    parts = entry.split(',')
    
    result = {
        'url': parts[0].strip(),
        'description': '',
        'expected_text': ''
    }
    
    if len(parts) > 1:
        result['description'] = parts[1].strip()
    
    if len(parts) > 2:
        result['expected_text'] = parts[2].strip()
    
    return result


def check_single_url(
    url: str,
    description: str = '',
    expected_text: str = '',
    lsf: Any = None
) -> CheckResult:
    """
    Check accessibility of a single URL.
    
    Args:
        url: URL to check
        description: Human-readable description
        expected_text: Optional text expected in response
        lsf: lsfunctions module (optional)
        
    Returns:
        CheckResult with URL accessibility status
    """
    # Use description if provided, otherwise use URL
    check_name = f"URL: {description}" if description else f"URL: {url}"
    
    if not REQUESTS_AVAILABLE:
        return CheckResult(
            name=check_name,
            status="SKIPPED",
            message="requests library not available"
        )
    
    # Use lsfunctions test_url if available
    if lsf and hasattr(lsf, 'test_url'):
        try:
            start_time = time.time()
            accessible = lsf.test_url(
                url,
                expected_text=expected_text if expected_text else None,
                verify_ssl=False,
                timeout=config.CHECK_TIMEOUT_URL
            )
            elapsed = time.time() - start_time
            
            if accessible:
                return CheckResult(
                    name=check_name,
                    status="PASS",
                    message=f"Accessible ({elapsed:.2f}s)",
                    details={
                        'url': url,
                        'response_time': round(elapsed, 2),
                        'expected_text': expected_text or None
                    }
                )
            else:
                return CheckResult(
                    name=check_name,
                    status="FAIL",
                    message="Not accessible or expected text not found",
                    details={
                        'url': url,
                        'expected_text': expected_text or None
                    }
                )
                
        except Exception as e:
            return CheckResult(
                name=check_name,
                status="FAIL",
                message=f"Check failed: {e}",
                details={'url': url, 'error': str(e)}
            )
    
    # Fallback to direct requests
    try:
        session = requests.Session()
        session.trust_env = False  # Ignore proxy environment vars
        
        start_time = time.time()
        response = session.get(
            url,
            verify=False,
            timeout=config.CHECK_TIMEOUT_URL,
            proxies=None,
            allow_redirects=True
        )
        elapsed = time.time() - start_time
        
        if response.status_code != 200:
            return CheckResult(
                name=check_name,
                status="FAIL",
                message=f"HTTP {response.status_code}",
                details={
                    'url': url,
                    'status_code': response.status_code,
                    'response_time': round(elapsed, 2)
                }
            )
        
        if expected_text and expected_text not in response.text:
            return CheckResult(
                name=check_name,
                status="FAIL",
                message=f"Expected text not found: '{expected_text[:30]}...'",
                details={
                    'url': url,
                    'expected_text': expected_text,
                    'response_time': round(elapsed, 2)
                }
            )
        
        return CheckResult(
            name=check_name,
            status="PASS",
            message=f"Accessible ({elapsed:.2f}s)",
            details={
                'url': url,
                'status_code': response.status_code,
                'response_time': round(elapsed, 2)
            }
        )
        
    except requests.exceptions.Timeout:
        return CheckResult(
            name=check_name,
            status="FAIL",
            message=f"Timeout after {config.CHECK_TIMEOUT_URL}s",
            details={'url': url, 'error': 'timeout'}
        )
    except requests.exceptions.ConnectionError as e:
        return CheckResult(
            name=check_name,
            status="FAIL",
            message="Connection refused or host unreachable",
            details={'url': url, 'error': str(e)}
        )
    except Exception as e:
        return CheckResult(
            name=check_name,
            status="FAIL",
            message=f"Check failed: {e}",
            details={'url': url, 'error': str(e)}
        )


def check_urls(url_entries: List[str], lsf: Any = None) -> List[CheckResult]:
    """
    Check accessibility for all URLs.
    
    Args:
        url_entries: List of URL entries (can include description and expected text)
        lsf: lsfunctions module (optional)
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    if not url_entries:
        results.append(CheckResult(
            name="URL Checks",
            status="SKIPPED",
            message="No URLs to check"
        ))
        return results
    
    checked_urls = set()
    
    for entry in url_entries:
        if not entry or entry.strip().startswith('#'):
            continue
        
        parsed = parse_url_entry(entry)
        url = parsed['url']
        
        # Skip duplicates
        if url in checked_urls:
            continue
        checked_urls.add(url)
        
        # Skip non-HTTP URLs
        if not url.lower().startswith('http'):
            continue
        
        result = check_single_url(
            url,
            parsed['description'],
            parsed['expected_text'],
            lsf
        )
        results.append(result)
    
    return results
