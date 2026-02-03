# linux_checks.py - HOLFY27 AutoCheck Linux Machine Validation
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# Linux machine accessibility and configuration checks.

"""
Linux Machine Validation Module

Checks Linux machines for:
- SSH accessibility
- Password expiration
- Time synchronization
- DNS resolution
"""

import datetime
import re
from typing import List, Dict, Any, Optional

from .base import CheckResult

# Import config for thresholds
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autocheck_config as config


#==============================================================================
# SSH ACCESSIBILITY CHECKS
#==============================================================================

def check_ssh_access(hostname: str, lsf: Any = None) -> CheckResult:
    """
    Check SSH accessibility to a Linux host.
    
    Args:
        hostname: Hostname or IP address
        lsf: lsfunctions module
        
    Returns:
        CheckResult with SSH accessibility status
    """
    check_name = f"SSH: {hostname}"
    
    if not lsf:
        return CheckResult(
            name=check_name,
            status="SKIPPED",
            message="lsfunctions not available"
        )
    
    # Check ping first
    if not lsf.test_ping(hostname, count=1, timeout=config.CHECK_TIMEOUT_PING):
        return CheckResult(
            name=check_name,
            status="WARN",
            message="Host not responding to ping",
            details={'hostname': hostname}
        )
    
    # Check SSH port
    if not lsf.test_tcp_port(hostname, 22, timeout=config.CHECK_TIMEOUT_SSH):
        return CheckResult(
            name=check_name,
            status="WARN",
            message="SSH port 22 not responding",
            details={'hostname': hostname, 'port': 22}
        )
    
    # Try SSH command
    password = lsf.get_password()
    result = lsf.ssh('hostname', f'root@{hostname}', password)
    
    if result.returncode == 0:
        return CheckResult(
            name=check_name,
            status="PASS",
            message="SSH accessible with root credentials",
            details={'hostname': hostname, 'user': 'root'}
        )
    else:
        return CheckResult(
            name=check_name,
            status="FAIL",
            message="SSH authentication failed",
            details={'hostname': hostname, 'user': 'root', 'error': result.stderr}
        )


def check_linux_machines(hosts: List[str], lsf: Any = None) -> List[CheckResult]:
    """
    Check SSH accessibility for all Linux hosts.
    
    Args:
        hosts: List of hostnames
        lsf: lsfunctions module
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    if not hosts:
        results.append(CheckResult(
            name="Linux Checks",
            status="SKIPPED",
            message="No Linux hosts to check"
        ))
        return results
    
    for hostname in hosts:
        result = check_ssh_access(hostname, lsf)
        results.append(result)
    
    return results


#==============================================================================
# PASSWORD EXPIRATION CHECKS
#==============================================================================

def get_password_expiration_days(hostname: str, username: str, lsf: Any) -> Optional[int]:
    """
    Get password expiration days for a Linux user account.
    
    Uses the chage command to get password expiration info.
    
    Args:
        hostname: Hostname to check
        username: Username to check
        lsf: lsfunctions module
        
    Returns:
        Days until expiration (None if never expires, negative if expired)
    """
    try:
        password = lsf.get_password()
        cmd = f'chage -l {username} 2>/dev/null | grep "Password expires"'
        result = lsf.ssh(cmd, f'root@{hostname}', password)
        
        if result.returncode != 0 or not result.stdout:
            return None
        
        output = result.stdout.strip()
        
        if 'never' in output.lower():
            return None  # Password never expires
        
        # Parse date from output like "Password expires : Dec 31, 2029"
        match = re.search(r':\s*(.+)$', output)
        if match:
            date_str = match.group(1).strip()
            
            if 'never' in date_str.lower():
                return None
            
            # Try to parse the date
            for fmt in ['%b %d, %Y', '%Y-%m-%d', '%d/%m/%Y']:
                try:
                    exp_date = datetime.datetime.strptime(date_str, fmt).date()
                    days_until = (exp_date - datetime.date.today()).days
                    return days_until
                except ValueError:
                    continue
        
        return None
        
    except Exception:
        return None


def check_single_password_expiration(
    hostname: str,
    username: str,
    lsf: Any
) -> CheckResult:
    """
    Check password expiration for a single user on a host.
    
    Args:
        hostname: Hostname to check
        username: Username to check
        lsf: lsfunctions module
        
    Returns:
        CheckResult with password expiration status
    """
    check_name = f"Password: {hostname} ({username})"
    
    try:
        days = get_password_expiration_days(hostname, username, lsf)
        
        if days is None:
            return CheckResult(
                name=check_name,
                status="PASS",
                message="Password never expires",
                details={'hostname': hostname, 'username': username, 'expires': 'never'}
            )
        
        if days < 0:
            return CheckResult(
                name=check_name,
                status="FAIL",
                message=f"Password EXPIRED {abs(days)} days ago",
                details={'hostname': hostname, 'username': username, 'days': days}
            )
        
        if days >= config.PASSWORD_EXPIRE_PASS_DAYS:  # 3 years
            return CheckResult(
                name=check_name,
                status="PASS",
                message=f"Expires in {days} days ({days // 365} years)",
                details={'hostname': hostname, 'username': username, 'days': days}
            )
        
        if days >= config.PASSWORD_EXPIRE_WARN_DAYS:  # 2 years
            return CheckResult(
                name=check_name,
                status="PASS",
                message=f"Expires in {days} days ({days // 365} years)",
                details={'hostname': hostname, 'username': username, 'days': days}
            )
        
        return CheckResult(
            name=check_name,
            status="FAIL",
            message=f"Expires in {days} days - TOO SOON",
            details={'hostname': hostname, 'username': username, 'days': days}
        )
        
    except Exception as e:
        return CheckResult(
            name=check_name,
            status="WARN",
            message=f"Could not check: {str(e)[:40]}",
            details={'hostname': hostname, 'username': username, 'error': str(e)}
        )


def check_password_expirations(lsf: Any = None) -> List[CheckResult]:
    """
    Check password expiration for all configured hosts and users.
    
    Checks:
    - ESXi hosts: root user
    - vCenter servers: root, administrator@vsphere.local
    - NSX managers: admin, root, audit
    - SDDC Manager: vcf, backup, root
    
    Args:
        lsf: lsfunctions module
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    if not lsf:
        return [CheckResult(
            name="Password Expiration Checks",
            status="SKIPPED",
            message="lsfunctions not available"
        )]
    
    # Get ESXi hosts
    esxi_hosts = []
    try:
        if lsf.config.has_option('RESOURCES', 'ESXiHosts'):
            hosts_raw = lsf.config.get('RESOURCES', 'ESXiHosts').split('\n')
            for entry in hosts_raw:
                if not entry or entry.strip().startswith('#'):
                    continue
                hostname = entry.split(':')[0].strip()
                if hostname:
                    esxi_hosts.append(hostname)
    except Exception:
        pass
    
    # Check ESXi hosts
    for hostname in esxi_hosts:
        result = check_single_password_expiration(hostname, 'root', lsf)
        results.append(result)
    
    # Get vCenter servers
    vcenters = []
    try:
        if lsf.config.has_option('RESOURCES', 'vCenters'):
            vcenters_raw = lsf.config.get('RESOURCES', 'vCenters').split('\n')
            for entry in vcenters_raw:
                if not entry or entry.strip().startswith('#'):
                    continue
                parts = entry.split(':')
                hostname = parts[0].strip()
                if hostname:
                    vcenters.append(hostname)
    except Exception:
        pass
    
    # Check vCenter servers
    for hostname in vcenters:
        result = check_single_password_expiration(hostname, 'root', lsf)
        results.append(result)
    
    # Get NSX managers
    nsx_managers = []
    try:
        if lsf.config.has_section('VCF') and lsf.config.has_option('VCF', 'vcfnsxmgr'):
            nsx_raw = lsf.config.get('VCF', 'vcfnsxmgr').split('\n')
            for entry in nsx_raw:
                if not entry or entry.strip().startswith('#'):
                    continue
                hostname = entry.split(':')[0].strip()
                if hostname:
                    nsx_managers.append(hostname)
    except Exception:
        pass
    
    # Check NSX managers
    for hostname in nsx_managers:
        for user in ['root', 'admin']:
            result = check_single_password_expiration(hostname, user, lsf)
            results.append(result)
    
    # Get SDDC Manager
    sddc_managers = []
    try:
        if lsf.config.has_section('VCF') and lsf.config.has_option('VCF', 'sddcmanager'):
            sddc_raw = lsf.config.get('VCF', 'sddcmanager').split('\n')
            for entry in sddc_raw:
                if not entry or entry.strip().startswith('#'):
                    continue
                hostname = entry.split(':')[0].strip()
                if hostname:
                    sddc_managers.append(hostname)
    except Exception:
        pass
    
    # Also look for sddcmanager in URLs
    try:
        if lsf.config.has_option('RESOURCES', 'URLs'):
            urls_raw = lsf.config.get('RESOURCES', 'URLs').split('\n')
            for entry in urls_raw:
                if 'sddcmanager' in entry.lower():
                    url = entry.split(',')[0].strip()
                    if '://' in url:
                        hostname = url.split('://')[1].split('/')[0].split(':')[0]
                        if hostname and hostname not in sddc_managers:
                            sddc_managers.append(hostname)
    except Exception:
        pass
    
    # Check SDDC managers
    for hostname in sddc_managers:
        for user in ['vcf', 'root', 'backup']:
            result = check_single_password_expiration(hostname, user, lsf)
            results.append(result)
    
    return results


#==============================================================================
# TIME SYNCHRONIZATION CHECKS
#==============================================================================

def check_time_sync(hostname: str, lsf: Any = None) -> CheckResult:
    """
    Check time synchronization on a Linux host.
    
    Args:
        hostname: Hostname to check
        lsf: lsfunctions module
        
    Returns:
        CheckResult with time sync status
    """
    check_name = f"Time: {hostname}"
    
    if not lsf:
        return CheckResult(
            name=check_name,
            status="SKIPPED",
            message="lsfunctions not available"
        )
    
    try:
        password = lsf.get_password()
        
        # Get remote time
        result = lsf.ssh('date +%s', f'root@{hostname}', password)
        
        if result.returncode != 0:
            return CheckResult(
                name=check_name,
                status="WARN",
                message="Could not get remote time",
                details={'hostname': hostname, 'error': result.stderr}
            )
        
        remote_time = int(result.stdout.strip())
        local_time = int(datetime.datetime.now().timestamp())
        
        # Calculate delta
        delta_seconds = abs(remote_time - local_time)
        
        if delta_seconds <= 60:  # Within 1 minute
            return CheckResult(
                name=check_name,
                status="PASS",
                message=f"Time synchronized (delta: {delta_seconds}s)",
                details={'hostname': hostname, 'delta_seconds': delta_seconds}
            )
        elif delta_seconds <= 300:  # Within 5 minutes
            return CheckResult(
                name=check_name,
                status="WARN",
                message=f"Time slightly off (delta: {delta_seconds}s)",
                details={'hostname': hostname, 'delta_seconds': delta_seconds}
            )
        else:
            return CheckResult(
                name=check_name,
                status="FAIL",
                message=f"Time significantly off (delta: {delta_seconds}s)",
                details={'hostname': hostname, 'delta_seconds': delta_seconds}
            )
        
    except Exception as e:
        return CheckResult(
            name=check_name,
            status="WARN",
            message=f"Could not check time: {e}",
            details={'hostname': hostname, 'error': str(e)}
        )
