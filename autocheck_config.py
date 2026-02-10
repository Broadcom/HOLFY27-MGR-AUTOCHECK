# autocheck_config.py - HOLFY27 AutoCheck Configuration
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# Configuration constants and helpers for AutoCheck validation.

"""
AutoCheck Configuration Module

This module provides configuration constants, paths, and helper functions
for the AutoCheck validation system.
"""

import os
import datetime

#==============================================================================
# PATHS
#==============================================================================

# Home directories
HOME = '/home/holuser'
HOLROOT = f'{HOME}/hol'

# Configuration files
CONFIG_INI = '/tmp/config.ini'
CREDS_FILE = f'{HOME}/creds.txt'

# NFS-mounted console paths
LMCHOL_ROOT = '/lmchol/hol'
LMCHOL_HOME = '/lmchol/home/holuser'

# Output directories
OUTPUT_DIR = LMCHOL_HOME  # Reports written to console home
LOG_DIR = HOLROOT

#==============================================================================
# TIMEOUTS
#==============================================================================

# Overall AutoCheck timeout (minutes)
AUTOCHECK_TIMEOUT_MINUTES = 60

# Per-check timeouts (seconds)
CHECK_TIMEOUT_DEFAULT = 300  # 5 minutes
CHECK_TIMEOUT_SSH = 30
CHECK_TIMEOUT_URL = 15
CHECK_TIMEOUT_PING = 5
CHECK_TIMEOUT_SSL = 10
CHECK_TIMEOUT_VCENTER = 120

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 10

#==============================================================================
# EXPIRATION THRESHOLDS
#==============================================================================

# License/certificate expiration thresholds (months from today)
EXPIRATION_PASS_MONTHS = 9   # >= 9 months = PASS (green)
EXPIRATION_WARN_MONTHS = 3   # >= 3 months but < 9 = WARN (yellow)
                              # < 3 months = FAIL (red)

# Password expiration thresholds (days)
PASSWORD_EXPIRE_PASS_DAYS = 1095  # 3 years
PASSWORD_EXPIRE_WARN_DAYS = 730   # 2 years

#==============================================================================
# CHECK CATEGORIES
#==============================================================================

# Check categories and their display order
CHECK_CATEGORIES = [
    ('ssl_checks', 'SSL Certificate Checks'),
    ('license_checks', 'vSphere License Checks'),
    ('ntp_checks', 'NTP Configuration'),
    ('vm_config_checks', 'VM Configuration'),
    ('vm_resource_checks', 'VM Resources'),
    ('password_expiration_checks', 'Password Expiration'),
    ('linux_checks', 'Linux Machine Checks'),
    ('windows_checks', 'Windows Machine Checks'),
    ('url_checks', 'URL Accessibility'),
    ('vsphere_checks', 'vSphere Configuration'),
    ('inventory_checks', 'Inventory & Utilization'),
]

#==============================================================================
# SKIP PATTERNS
#==============================================================================

# VMs to skip during configuration checks (system VMs)
SKIP_VM_PATTERNS = [
    'vcf-services-platform-template-',    # VCF Services Platform Template VMs
    'SupervisorControlPlaneVM',           # Tanzu Supervisor Control Plane VMs
]

# Hosts to skip for certain checks
SKIP_HOST_PATTERNS = []

#==============================================================================
# DEFAULT CREDENTIALS
#==============================================================================

# Default usernames (passwords come from creds.txt)
DEFAULT_VCENTER_USER = 'administrator@vsphere.local'
DEFAULT_ESX_USER = 'root'
DEFAULT_NSX_USER = 'admin'
DEFAULT_LINUX_USER = 'root'

#==============================================================================
# HELPER FUNCTIONS
#==============================================================================

def get_output_path(lab_sku: str, extension: str) -> str:
    """
    Get the output file path for a given lab SKU and extension.
    
    Args:
        lab_sku: Lab SKU (e.g., 'HOL-2701')
        extension: File extension (e.g., 'html', 'json', 'log')
        
    Returns:
        Full path to output file
    """
    filename = f'autocheck-{lab_sku}.{extension}'
    return os.path.join(OUTPUT_DIR, filename)


def get_lab_year(lab_sku: str) -> str:
    """
    Extract the 2-digit lab year from the lab SKU.
    
    Supports formats:
    - Standard: HOL-2701, ATE-2705 -> '27'
    - BETA: BETA-901-TNDNS -> '27' (default)
    - Named: Discovery-Demo -> '27' (default)
    
    Args:
        lab_sku: Lab SKU string
        
    Returns:
        2-digit year string (e.g., '27')
    """
    import re
    
    default_year = '27'  # HOLFY27
    
    if not lab_sku or len(lab_sku) < 4:
        return default_year
    
    # Standard 4-digit pattern: PREFIX-XXYY
    match = re.search(r'-(\d{4})(?:\D|$)', lab_sku)
    if match:
        year_part = match.group(1)[:2]
        try:
            year_int = int(year_part)
            if 20 <= year_int <= 35:
                return year_part
        except ValueError:
            pass
    
    # Beta pattern: PREFIX-9XX
    match = re.search(r'-9\d{2}(?:\D|$)', lab_sku)
    if match:
        return default_year
    
    return default_year


def get_expiration_dates(lab_sku: str) -> tuple:
    """
    Calculate license/certificate expiration date range for the lab.
    
    Args:
        lab_sku: Lab SKU string
        
    Returns:
        Tuple of (min_exp_date, max_exp_date) as datetime.date objects
    """
    lab_year = get_lab_year(lab_sku)
    year = int(lab_year) + 2000
    
    # Licenses should expire between Dec 30 of lab year and Dec 31 of following year
    min_exp_date = datetime.date(year, 12, 30)
    max_exp_date = datetime.date(year + 1, 12, 31)
    
    return (min_exp_date, max_exp_date)


def get_months_until_expiration(exp_date: datetime.date) -> float:
    """
    Calculate months until expiration from today's date.
    
    Args:
        exp_date: Expiration date
        
    Returns:
        Approximate months until expiration (can be negative if expired)
    """
    today = datetime.date.today()
    days_until = (exp_date - today).days
    return days_until / 30.44  # Average days per month


def should_skip_vm(vm_name: str) -> bool:
    """
    Check if a VM should be skipped based on skip patterns.
    
    Args:
        vm_name: VM name to check
        
    Returns:
        True if VM should be skipped
    """
    for pattern in SKIP_VM_PATTERNS:
        if pattern in vm_name:
            return True
    return False
