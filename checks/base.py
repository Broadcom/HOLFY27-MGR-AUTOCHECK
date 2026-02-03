# base.py - HOLFY27 AutoCheck Base Classes
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# Shared dataclasses and utilities for AutoCheck validation modules.
# Refactored from vpodchecker.py for reuse across check modules.

"""
Base classes for AutoCheck validation.

This module provides the core data structures used by all check modules:
- CheckResult: Result of a single validation check
- SslHost: SSL host information for certificate checks
- ValidationReport: Complete validation report aggregating all checks
"""

import datetime
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


#==============================================================================
# CHECK RESULT
#==============================================================================

@dataclass
class CheckResult:
    """
    Result of a single validation check.
    
    Attributes:
        name: Human-readable name of the check
        status: Result status - one of PASS, FAIL, WARN, INFO, SKIPPED, FIXED
        message: Descriptive message about the result
        details: Optional dictionary with additional structured data
        
    Status meanings:
        - PASS: Check passed successfully
        - FAIL: Check failed - requires action
        - WARN: Check passed with warnings - should be reviewed
        - INFO: Informational only - no pass/fail determination
        - SKIPPED: Check was skipped (e.g., not applicable)
        - FIXED: Issue was found and automatically fixed
    """
    name: str
    status: str  # PASS, FAIL, WARN, INFO, SKIPPED, FIXED
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    
    def is_pass(self) -> bool:
        """Check if this result is a pass (PASS or FIXED)"""
        return self.status in ('PASS', 'FIXED')
    
    def is_fail(self) -> bool:
        """Check if this result is a failure"""
        return self.status == 'FAIL'
    
    def is_warn(self) -> bool:
        """Check if this result is a warning"""
        return self.status == 'WARN'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_log_line(self) -> str:
        """Format as a log line"""
        return f"{self.status}: {self.name} - {self.message}"


#==============================================================================
# SSL HOST
#==============================================================================

@dataclass
class SslHost:
    """
    SSL host information for certificate validation.
    
    Attributes:
        name: Hostname or IP address
        port: TCP port number (default 443)
        certname: Certificate Common Name (CN)
        issuer: Certificate issuer information
        ssl_exp_date: Certificate expiration date
        days_to_expire: Days until certificate expires
    """
    name: str
    port: int = 443
    certname: str = ""
    issuer: str = ""
    ssl_exp_date: Optional[datetime.date] = None
    days_to_expire: int = 0
    
    def is_expired(self) -> bool:
        """Check if certificate is expired"""
        return self.days_to_expire < 0
    
    def expires_soon(self, days: int = 90) -> bool:
        """Check if certificate expires within specified days"""
        return 0 <= self.days_to_expire < days


#==============================================================================
# VALIDATION REPORT
#==============================================================================

@dataclass
class ValidationReport:
    """
    Complete validation report aggregating all check results.
    
    Attributes:
        lab_sku: Lab SKU (e.g., 'HOL-2701')
        timestamp: Report generation timestamp
        min_exp_date: Minimum acceptable expiration date for licenses/certs
        max_exp_date: Maximum expiration date for licenses/certs
        
        Check result lists:
        - ssl_checks: SSL certificate validation results
        - license_checks: vSphere license validation results
        - ntp_checks: NTP configuration check results
        - vm_config_checks: VM configuration check results
        - vm_resource_checks: VM resource (reservations/shares) check results
        - password_expiration_checks: Password expiration check results
        - linux_checks: Linux VM accessibility check results
        - windows_checks: Windows VM check results
        - url_checks: URL/bookmark check results
        - vsphere_checks: vSphere configuration check results
        - inventory_checks: VM inventory and utilization results
        
        overall_status: Aggregate status (PASS, WARN, FAIL)
    """
    lab_sku: str
    timestamp: str = ""
    min_exp_date: str = ""
    max_exp_date: str = ""
    
    # Check result lists
    ssl_checks: List[CheckResult] = field(default_factory=list)
    license_checks: List[CheckResult] = field(default_factory=list)
    ntp_checks: List[CheckResult] = field(default_factory=list)
    vm_config_checks: List[CheckResult] = field(default_factory=list)
    vm_resource_checks: List[CheckResult] = field(default_factory=list)
    password_expiration_checks: List[CheckResult] = field(default_factory=list)
    linux_checks: List[CheckResult] = field(default_factory=list)
    windows_checks: List[CheckResult] = field(default_factory=list)
    url_checks: List[CheckResult] = field(default_factory=list)
    vsphere_checks: List[CheckResult] = field(default_factory=list)
    inventory_checks: List[CheckResult] = field(default_factory=list)
    
    overall_status: str = "PASS"
    
    def __post_init__(self):
        """Set timestamp if not provided"""
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().isoformat()
    
    def get_all_checks(self) -> List[CheckResult]:
        """Get all check results as a single list"""
        return (
            self.ssl_checks +
            self.license_checks +
            self.ntp_checks +
            self.vm_config_checks +
            self.vm_resource_checks +
            self.password_expiration_checks +
            self.linux_checks +
            self.windows_checks +
            self.url_checks +
            self.vsphere_checks +
            self.inventory_checks
        )
    
    def calculate_overall_status(self) -> str:
        """
        Calculate and set overall status based on all check results.
        
        Returns:
            - 'FAIL' if any check has FAIL status
            - 'WARN' if any check has WARN status (and no FAILs)
            - 'PASS' otherwise
        """
        all_checks = self.get_all_checks()
        
        if any(c.status == 'FAIL' for c in all_checks):
            self.overall_status = "FAIL"
        elif any(c.status == 'WARN' for c in all_checks):
            self.overall_status = "WARN"
        else:
            self.overall_status = "PASS"
        
        return self.overall_status
    
    def get_summary(self) -> Dict[str, int]:
        """
        Get summary counts of check results by status.
        
        Returns:
            Dictionary with counts: {'pass': N, 'fail': N, 'warn': N, 'info': N, 'skipped': N}
        """
        all_checks = self.get_all_checks()
        
        return {
            'pass': sum(1 for c in all_checks if c.status in ('PASS', 'FIXED')),
            'fail': sum(1 for c in all_checks if c.status == 'FAIL'),
            'warn': sum(1 for c in all_checks if c.status == 'WARN'),
            'info': sum(1 for c in all_checks if c.status == 'INFO'),
            'skipped': sum(1 for c in all_checks if c.status == 'SKIPPED'),
            'total': len(all_checks)
        }
    
    def to_dict(self) -> Dict:
        """Convert report to dictionary"""
        result = {
            'lab_sku': self.lab_sku,
            'timestamp': self.timestamp,
            'min_exp_date': self.min_exp_date,
            'max_exp_date': self.max_exp_date,
            'overall_status': self.overall_status,
            'summary': self.get_summary(),
            'ssl_checks': [c.to_dict() for c in self.ssl_checks],
            'license_checks': [c.to_dict() for c in self.license_checks],
            'ntp_checks': [c.to_dict() for c in self.ntp_checks],
            'vm_config_checks': [c.to_dict() for c in self.vm_config_checks],
            'vm_resource_checks': [c.to_dict() for c in self.vm_resource_checks],
            'password_expiration_checks': [c.to_dict() for c in self.password_expiration_checks],
            'linux_checks': [c.to_dict() for c in self.linux_checks],
            'windows_checks': [c.to_dict() for c in self.windows_checks],
            'url_checks': [c.to_dict() for c in self.url_checks],
            'vsphere_checks': [c.to_dict() for c in self.vsphere_checks],
            'inventory_checks': [c.to_dict() for c in self.inventory_checks],
        }
        return result
    
    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string"""
        return json.dumps(self.to_dict(), indent=indent, default=str)


#==============================================================================
# UTILITY FUNCTIONS
#==============================================================================

def get_status_icon(status: str) -> str:
    """
    Get emoji icon for a status.
    
    Args:
        status: Check status string
        
    Returns:
        Emoji character representing the status
    """
    icons = {
        'PASS': '✅',
        'FAIL': '❌',
        'WARN': '⚠️',
        'INFO': 'ℹ️',
        'SKIPPED': '⏭️',
        'FIXED': '🔧',
    }
    return icons.get(status, '❓')


def get_status_class(status: str) -> str:
    """
    Get CSS class for a status.
    
    Args:
        status: Check status string
        
    Returns:
        CSS class name for styling
    """
    classes = {
        'PASS': 'status-pass',
        'FAIL': 'status-fail',
        'WARN': 'status-warn',
        'INFO': 'status-info',
        'SKIPPED': 'status-skipped',
        'FIXED': 'status-fixed',
    }
    return classes.get(status, 'status-unknown')
