# license_checks.py - HOLFY27 AutoCheck vSphere License Validation
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# vSphere license expiration and assignment checks.
# Refactored from vpodchecker.py for modularity.

"""
vSphere License Validation Module

Checks vSphere licenses for:
- Valid (non-evaluation) license keys
- Expiration dates against HOL standards
- Proper assignment to assets
"""

import datetime
from typing import List, Any

from .base import CheckResult

# Import config for thresholds
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autocheck_config as config


#==============================================================================
# LICENSE CHECKS
#==============================================================================

def get_license_expiration_status(exp_date: datetime.date) -> tuple:
    """
    Determine license status based on months until expiration.
    
    Args:
        exp_date: License expiration date
        
    Returns:
        Tuple of (status, message) where status is PASS/WARN/FAIL
        
    Status rules:
        - PASS (green): >= 9 months from now
        - WARN (yellow): < 9 months but >= 3 months from now
        - FAIL (red): < 3 months from now
    """
    months_until = config.get_months_until_expiration(exp_date)
    
    if months_until >= config.EXPIRATION_PASS_MONTHS:
        status = "PASS"
        message = f"License valid - expires {exp_date} (>= 9 months)"
    elif months_until >= config.EXPIRATION_WARN_MONTHS:
        status = "WARN"
        message = f"License expiring soon - expires {exp_date} (< 9 months)"
    else:
        status = "FAIL"
        message = f"License expiring critically soon - expires {exp_date} (< 3 months)"
    
    return status, message


def mask_license_key(license_key: str) -> str:
    """
    Mask a license key for display (show first and last 5 chars).
    
    Args:
        license_key: Full license key
        
    Returns:
        Masked license key
    """
    if len(license_key) > 10:
        return license_key[:5] + "-****-****-****-" + license_key[-5:]
    return license_key


def check_single_license(
    license_key: str,
    license_name: str,
    entity_name: str,
    exp_date: datetime.date = None
) -> CheckResult:
    """
    Check a single license.
    
    Args:
        license_key: License key string
        license_name: Human-readable license name
        entity_name: Entity the license is assigned to
        exp_date: Expiration date (None if no expiration)
        
    Returns:
        CheckResult with license status
    """
    check_name = f"License: {license_name}"
    
    # Check for evaluation license
    if license_key == '00000-00000-00000-00000-00000':
        return CheckResult(
            name=check_name,
            status="FAIL",
            message="Evaluation license detected - requires production license",
            details={
                'license_key': license_key,
                'entity': entity_name
            }
        )
    
    # Check expiration
    if exp_date:
        status, message = get_license_expiration_status(exp_date)
        return CheckResult(
            name=check_name,
            status=status,
            message=message,
            details={
                'license_key': mask_license_key(license_key),
                'entity': entity_name,
                'expiration': str(exp_date)
            }
        )
    else:
        # Non-expiring license
        if 'NSX for vShield Endpoint' in license_name:
            # Expected for vShield Endpoint
            status = "WARN"
            message = "Non-expiring license (expected for vShield Endpoint)"
        else:
            status = "FAIL"
            message = "Non-expiring license detected - requires dated license"
        
        return CheckResult(
            name=check_name,
            status=status,
            message=message,
            details={
                'license_key': mask_license_key(license_key),
                'entity': entity_name,
                'expiration': "Never"
            }
        )


def check_licenses(
    sis: List[Any],
    min_exp_date: datetime.date,
    max_exp_date: datetime.date
) -> List[CheckResult]:
    """
    Check vSphere licenses across all connected vCenters.
    
    Args:
        sis: List of vCenter ServiceInstance objects
        min_exp_date: Minimum acceptable expiration date
        max_exp_date: Maximum acceptable expiration date
        
    Returns:
        List of CheckResult objects
    """
    results = []
    license_keys_checked = set()
    
    for si in sis:
        try:
            lic_mgr = si.content.licenseManager
            lic_assignment_mgr = lic_mgr.licenseAssignmentManager
            
            # Get assigned licenses
            try:
                assets = lic_assignment_mgr.QueryAssignedLicenses()
            except Exception as e:
                results.append(CheckResult(
                    name="License Query",
                    status="FAIL",
                    message=f"Failed to query assigned licenses: {e}"
                ))
                continue
            
            for asset in assets:
                license_key = asset.assignedLicense.licenseKey
                license_name = asset.assignedLicense.name
                entity_name = asset.entityDisplayName
                
                # Skip duplicates
                if license_key in license_keys_checked:
                    continue
                license_keys_checked.add(license_key)
                
                # Get expiration date
                exp_date = None
                for prop in asset.assignedLicense.properties:
                    if prop.key == 'expirationDate':
                        exp_date = prop.value
                        break
                
                # Convert to date if needed
                if exp_date and hasattr(exp_date, 'date'):
                    exp_date = exp_date.date()
                elif exp_date and not isinstance(exp_date, datetime.date):
                    exp_date = None
                
                result = check_single_license(
                    license_key,
                    license_name,
                    entity_name,
                    exp_date
                )
                results.append(result)
            
            # Check for unassigned licenses
            for lic in lic_mgr.licenses:
                if lic.licenseKey in license_keys_checked:
                    continue
                
                if not lic.used and lic.licenseKey != '00000-00000-00000-00000-00000':
                    license_keys_checked.add(lic.licenseKey)
                    
                    # Get expiration date
                    exp_date = None
                    for prop in lic.properties:
                        if prop.key == 'expirationDate':
                            exp_date = prop.value
                            break
                    
                    if exp_date and hasattr(exp_date, 'date'):
                        exp_date = exp_date.date()
                    
                    exp_msg = f" - expires {exp_date}" if exp_date else " - no expiration date"
                    
                    results.append(CheckResult(
                        name=f"License: {lic.name}",
                        status="WARN",
                        message=f"Unassigned license - should be removed{exp_msg}",
                        details={
                            'license_key': mask_license_key(lic.licenseKey),
                            'used': False
                        }
                    ))
        
        except Exception as e:
            results.append(CheckResult(
                name="License Check",
                status="FAIL",
                message=f"Could not check licenses: {e}"
            ))
    
    return results
