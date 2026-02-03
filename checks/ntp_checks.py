# ntp_checks.py - HOLFY27 AutoCheck NTP Configuration Validation
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# NTP configuration checks for ESXi hosts.
# Refactored from vpodchecker.py for modularity.

"""
NTP Configuration Validation Module

Checks NTP configuration on ESXi hosts:
- NTPD service running
- NTPD service set to start on boot
- NTP server configured
"""

from typing import List, Dict, Any

from .base import CheckResult


#==============================================================================
# NTP CHECKS
#==============================================================================

def get_ntp_config(esx_host) -> Dict[str, Any]:
    """
    Get NTP configuration for an ESXi host.
    
    Args:
        esx_host: ESXi host object (vim.HostSystem)
        
    Returns:
        Dictionary with NTP configuration details
    """
    ntp_data = {
        "hostname": esx_host.name,
        "running": False,
        "policy": "",
        "server": ""
    }
    
    try:
        for service in esx_host.config.service.service:
            if service.key == 'ntpd':
                ntp_data["running"] = service.running
                ntp_data["policy"] = service.policy
                if esx_host.config.dateTimeInfo.ntpConfig.server:
                    ntp_data["server"] = esx_host.config.dateTimeInfo.ntpConfig.server[0]
                break
    except Exception:
        pass
    
    return ntp_data


def check_single_host_ntp(host) -> CheckResult:
    """
    Check NTP configuration on a single ESXi host.
    
    Args:
        host: ESXi host object (vim.HostSystem)
        
    Returns:
        CheckResult with NTP status
    """
    ntp_config = get_ntp_config(host)
    check_name = f"NTP: {host.name}"
    
    issues = []
    
    if not ntp_config["running"]:
        issues.append("NTPD not running")
    
    if ntp_config["policy"] != "on":
        issues.append(f"NTPD policy is '{ntp_config['policy']}' (should be 'on')")
    
    if not ntp_config["server"]:
        issues.append("No NTP server configured")
    
    if issues:
        status = "WARN"
        message = "; ".join(issues)
    else:
        status = "PASS"
        message = f"NTP configured correctly (server: {ntp_config['server']})"
    
    return CheckResult(
        name=check_name,
        status=status,
        message=message,
        details=ntp_config
    )


def check_ntp_configuration(hosts: List) -> List[CheckResult]:
    """
    Check NTP configuration on all ESXi hosts.
    
    Args:
        hosts: List of ESXi host objects (vim.HostSystem)
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    if not hosts:
        results.append(CheckResult(
            name="NTP Checks",
            status="SKIPPED",
            message="No ESXi hosts to check"
        ))
        return results
    
    for host in hosts:
        try:
            result = check_single_host_ntp(host)
            results.append(result)
        except Exception as e:
            results.append(CheckResult(
                name=f"NTP: {host.name}",
                status="FAIL",
                message=f"Failed to check NTP: {e}"
            ))
    
    return results
