# HOLFY27-MGR-AUTOCHECK Check Modules
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# This package contains check modules for AutoCheck validation.

from .base import CheckResult, SslHost, ValidationReport, get_status_icon, get_status_class

# Import check modules for easy access
from . import ssl_checks
from . import license_checks
from . import ntp_checks
from . import linux_checks
from . import windows_checks
from . import url_checks
from . import vsphere_checks

__all__ = [
    # Base classes
    'CheckResult',
    'SslHost',
    'ValidationReport',
    'get_status_icon',
    'get_status_class',
    # Check modules
    'ssl_checks',
    'license_checks',
    'ntp_checks',
    'linux_checks',
    'windows_checks',
    'url_checks',
    'vsphere_checks',
]
