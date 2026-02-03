# ssl_checks.py - HOLFY27 AutoCheck SSL Certificate Validation
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# SSL certificate expiration and validity checks.
# Refactored from vpodchecker.py for modularity.

"""
SSL Certificate Validation Module

Checks SSL certificates for all HTTPS endpoints defined in config.ini.
Validates expiration dates against HOL standards.
"""

import datetime
import socket
from typing import List, Optional, Any

from .base import CheckResult, SslHost

# Optional imports with graceful fallback
try:
    import OpenSSL
    import ssl
    SSL_AVAILABLE = True
except ImportError:
    SSL_AVAILABLE = False

# Import config for thresholds
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autocheck_config as config


#==============================================================================
# SSL CERTIFICATE CHECKS
#==============================================================================

def get_ssl_host_from_url(url: str) -> SslHost:
    """
    Extract hostname and port from URL.
    
    Args:
        url: URL string (e.g., 'https://vcenter.local:443/ui')
        
    Returns:
        SslHost object with name and port
    """
    # Remove protocol prefix
    if '://' in url:
        url = url.split('://')[1]
    
    # Remove path
    if '/' in url:
        url = url.split('/')[0]
    
    # Extract port if present
    if ':' in url:
        parts = url.split(':')
        name = parts[0]
        try:
            port = int(parts[1])
        except ValueError:
            port = 443
    else:
        name = url
        port = 443
    
    return SslHost(name=name, port=port)


def get_cert_expiration(ssl_cert) -> datetime.date:
    """
    Get SSL certificate expiration date.
    
    Args:
        ssl_cert: OpenSSL X509 certificate object
        
    Returns:
        Expiration date
    """
    x509info = ssl_cert.get_notAfter()
    exp_day = int(x509info[6:8].decode("utf-8"))
    exp_month = int(x509info[4:6].decode("utf-8"))
    exp_year = int(x509info[:4].decode("utf-8"))
    return datetime.date(exp_year, exp_month, exp_day)


def check_single_certificate(host: SslHost, lsf: Any = None) -> CheckResult:
    """
    Check a single SSL certificate.
    
    Args:
        host: SslHost object with hostname and port
        lsf: lsfunctions module (optional)
        
    Returns:
        CheckResult with certificate status
    """
    check_name = f"SSL: {host.name}:{host.port}"
    
    # Check if host is reachable
    if lsf and hasattr(lsf, 'test_tcp_port'):
        if not lsf.test_tcp_port(host.name, host.port, timeout=config.CHECK_TIMEOUT_SSL):
            return CheckResult(
                name=check_name,
                status='WARN',
                message='Host not reachable',
                details={'host': host.name, 'port': host.port}
            )
    
    try:
        # Get certificate
        cert = ssl.get_server_certificate((host.name, host.port), timeout=config.CHECK_TIMEOUT_SSL)
        x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
        
        # Extract certificate info
        subject = x509.get_subject()
        host.certname = subject.CN or "Unknown"
        
        issuer = x509.get_issuer()
        if issuer.OU or issuer.O:
            host.issuer = f"OU={issuer.OU or ''} O={issuer.O or ''}"
        else:
            host.issuer = "Self-Signed"
        
        # Get expiration date
        host.ssl_exp_date = get_cert_expiration(x509)
        
        # Calculate days/months until expiration
        today = datetime.date.today()
        days_until = (host.ssl_exp_date - today).days
        host.days_to_expire = days_until
        months_until = days_until / 30.44
        
        # Determine status based on thresholds
        if months_until >= config.EXPIRATION_PASS_MONTHS:
            status = "PASS"
            message = f"Certificate valid - expires {host.ssl_exp_date} (>= 9 months)"
        elif months_until >= config.EXPIRATION_WARN_MONTHS:
            status = "WARN"
            message = f"Certificate expires soon - expires {host.ssl_exp_date} (< 9 months)"
        else:
            # Check if it's an external host (be more lenient)
            if is_external_host(host.name):
                status = "WARN"
                message = f"External certificate expires soon - expires {host.ssl_exp_date}"
            else:
                status = "FAIL"
                message = f"Certificate expires critically soon - expires {host.ssl_exp_date} (< 3 months)"
        
        return CheckResult(
            name=check_name,
            status=status,
            message=message,
            details={
                'host': host.name,
                'port': host.port,
                'certname': host.certname,
                'expiration': str(host.ssl_exp_date),
                'days_to_expire': host.days_to_expire,
                'issuer': host.issuer
            }
        )
        
    except socket.timeout:
        return CheckResult(
            name=check_name,
            status='WARN',
            message='Connection timed out',
            details={'host': host.name, 'port': host.port, 'error': 'timeout'}
        )
    except socket.gaierror as e:
        return CheckResult(
            name=check_name,
            status='WARN',
            message=f'DNS resolution failed: {e}',
            details={'host': host.name, 'port': host.port, 'error': str(e)}
        )
    except Exception as e:
        # Be lenient with external hosts
        if is_external_host(host.name):
            status = "WARN"
            message = f"External host check failed (expected): {e}"
        else:
            status = "FAIL"
            message = f"Could not check certificate: {e}"
        
        return CheckResult(
            name=check_name,
            status=status,
            message=message,
            details={'host': host.name, 'port': host.port, 'error': str(e)}
        )


def is_external_host(hostname: str) -> bool:
    """
    Check if hostname is an external (internet) host.
    
    Args:
        hostname: Hostname to check
        
    Returns:
        True if hostname appears to be external
    """
    external_patterns = [
        'vmware.com',
        'broadcom.com',
        'github.com',
        'google.com',
    ]
    
    hostname_lower = hostname.lower()
    for pattern in external_patterns:
        if pattern in hostname_lower:
            return True
    
    return False


def should_skip_url(url: str, lsf: Any = None) -> bool:
    """
    Check if URL should be skipped (e.g., external URLs when proxy is active).
    
    Args:
        url: URL to check
        lsf: lsfunctions module (optional)
        
    Returns:
        True if URL should be skipped
    """
    if lsf and hasattr(lsf, 'check_proxy'):
        try:
            if lsf.check_proxy(url):
                return True
        except Exception:
            pass
    
    return False


def check_ssl_certificates(
    urls: List[str],
    min_exp_date: datetime.date,
    lsf: Any = None
) -> List[CheckResult]:
    """
    Check SSL certificates for all HTTPS URLs.
    
    Args:
        urls: List of URLs to check
        min_exp_date: Minimum acceptable expiration date
        lsf: lsfunctions module (optional)
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    # Check if SSL libraries are available
    if not SSL_AVAILABLE:
        results.append(CheckResult(
            name="SSL Check",
            status="SKIPPED",
            message="OpenSSL not available - install pyOpenSSL"
        ))
        return results
    
    # Track checked hosts to avoid duplicates
    checked_hosts = set()
    
    for url in urls:
        # Only check HTTPS URLs
        if not url.lower().startswith('https'):
            continue
        
        # Skip external URLs if using proxy
        if should_skip_url(url, lsf):
            continue
        
        # Extract host info
        host = get_ssl_host_from_url(url)
        
        # Skip duplicates
        host_key = f"{host.name}:{host.port}"
        if host_key in checked_hosts:
            continue
        checked_hosts.add(host_key)
        
        # Check the certificate
        result = check_single_certificate(host, lsf)
        results.append(result)
    
    return results
