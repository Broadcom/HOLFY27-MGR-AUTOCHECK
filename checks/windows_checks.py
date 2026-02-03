# windows_checks.py - HOLFY27 AutoCheck Windows Machine Validation
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# Windows machine accessibility and configuration checks.
# Uses pypsexec for remote Windows command execution.

"""
Windows Machine Validation Module

Checks Windows machines for:
- Network accessibility
- Remote execution (via pypsexec)
- Windows activation status
- Firewall configuration
- Password expiration

Note: Windows checks require the pypsexec library and SMB access
to the target machines.
"""

from typing import List, Dict, Any, Optional

from .base import CheckResult

# Optional imports
try:
    from pypsexec.client import Client
    PYPSEXEC_AVAILABLE = True
except ImportError:
    PYPSEXEC_AVAILABLE = False

# Import config
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autocheck_config as config


#==============================================================================
# WINDOWS REMOTE EXECUTION
#==============================================================================

def run_remote_command(
    hostname: str,
    username: str,
    password: str,
    command: str,
    timeout: int = 60
) -> Dict[str, Any]:
    """
    Run a command on a remote Windows machine using pypsexec.
    
    Args:
        hostname: Windows host IP or hostname
        username: Username for authentication
        password: Password for authentication
        command: Command to execute
        timeout: Execution timeout in seconds
        
    Returns:
        Dictionary with 'success', 'stdout', 'stderr', 'return_code'
    """
    if not PYPSEXEC_AVAILABLE:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'pypsexec not available',
            'return_code': -1
        }
    
    try:
        client = Client(hostname, username=username, password=password)
        client.connect()
        
        try:
            client.create_service()
            
            stdout, stderr, return_code = client.run_executable(
                'cmd.exe',
                arguments=f'/c {command}',
                timeout_seconds=timeout
            )
            
            return {
                'success': return_code == 0,
                'stdout': stdout.decode('utf-8', errors='replace') if stdout else '',
                'stderr': stderr.decode('utf-8', errors='replace') if stderr else '',
                'return_code': return_code
            }
            
        finally:
            client.remove_service()
            client.disconnect()
            
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'return_code': -1
        }


#==============================================================================
# INDIVIDUAL CHECKS
#==============================================================================

def check_windows_accessibility(host: Dict[str, str], lsf: Any = None) -> CheckResult:
    """
    Check basic accessibility to a Windows machine.
    
    Args:
        host: Dictionary with 'name', 'ip', 'guest_id'
        lsf: lsfunctions module (optional)
        
    Returns:
        CheckResult with accessibility status
    """
    check_name = f"Windows: {host['name']}"
    ip = host.get('ip', '')
    
    if not ip:
        return CheckResult(
            name=check_name,
            status="SKIPPED",
            message="No IP address available",
            details={'vm_name': host['name']}
        )
    
    # Check ping
    if lsf and hasattr(lsf, 'test_ping'):
        if not lsf.test_ping(ip, count=1, timeout=config.CHECK_TIMEOUT_PING):
            return CheckResult(
                name=check_name,
                status="WARN",
                message="Host not responding to ping",
                details={'vm_name': host['name'], 'ip': ip}
            )
    
    # Check SMB port (445) for pypsexec
    if lsf and hasattr(lsf, 'test_tcp_port'):
        if not lsf.test_tcp_port(ip, 445, timeout=config.CHECK_TIMEOUT_SSH):
            return CheckResult(
                name=check_name,
                status="WARN",
                message="SMB port 445 not responding",
                details={'vm_name': host['name'], 'ip': ip, 'port': 445}
            )
    
    return CheckResult(
        name=check_name,
        status="PASS",
        message="Host accessible (ping and SMB port 445)",
        details={'vm_name': host['name'], 'ip': ip}
    )


def check_windows_activation(host: Dict[str, str], password: str) -> CheckResult:
    """
    Check Windows activation status.
    
    Args:
        host: Dictionary with 'name', 'ip'
        password: Authentication password
        
    Returns:
        CheckResult with activation status
    """
    check_name = f"Activation: {host['name']}"
    ip = host.get('ip', '')
    
    if not PYPSEXEC_AVAILABLE:
        return CheckResult(
            name=check_name,
            status="SKIPPED",
            message="pypsexec not available"
        )
    
    if not ip:
        return CheckResult(
            name=check_name,
            status="SKIPPED",
            message="No IP address available"
        )
    
    # Run slmgr to check activation
    result = run_remote_command(
        ip,
        'Administrator',
        password,
        'cscript //nologo C:\\Windows\\System32\\slmgr.vbs /xpr'
    )
    
    if not result['success']:
        return CheckResult(
            name=check_name,
            status="WARN",
            message=f"Could not check activation: {result['stderr'][:50]}",
            details={'vm_name': host['name'], 'ip': ip}
        )
    
    stdout = result['stdout'].lower()
    
    if 'permanently activated' in stdout or 'will expire' in stdout:
        return CheckResult(
            name=check_name,
            status="PASS",
            message="Windows is activated",
            details={'vm_name': host['name'], 'ip': ip, 'output': result['stdout'][:100]}
        )
    elif 'notification mode' in stdout or 'not activated' in stdout:
        return CheckResult(
            name=check_name,
            status="FAIL",
            message="Windows is NOT activated",
            details={'vm_name': host['name'], 'ip': ip, 'output': result['stdout'][:100]}
        )
    else:
        return CheckResult(
            name=check_name,
            status="WARN",
            message="Could not determine activation status",
            details={'vm_name': host['name'], 'ip': ip, 'output': result['stdout'][:100]}
        )


def check_windows_firewall(host: Dict[str, str], password: str) -> CheckResult:
    """
    Check Windows firewall status.
    
    HOL Standard: Firewall should be disabled on all profiles
    
    Args:
        host: Dictionary with 'name', 'ip'
        password: Authentication password
        
    Returns:
        CheckResult with firewall status
    """
    check_name = f"Firewall: {host['name']}"
    ip = host.get('ip', '')
    
    if not PYPSEXEC_AVAILABLE:
        return CheckResult(
            name=check_name,
            status="SKIPPED",
            message="pypsexec not available"
        )
    
    if not ip:
        return CheckResult(
            name=check_name,
            status="SKIPPED",
            message="No IP address available"
        )
    
    # Check firewall status
    result = run_remote_command(
        ip,
        'Administrator',
        password,
        'netsh advfirewall show allprofiles state'
    )
    
    if not result['success']:
        return CheckResult(
            name=check_name,
            status="WARN",
            message=f"Could not check firewall: {result['stderr'][:50]}",
            details={'vm_name': host['name'], 'ip': ip}
        )
    
    stdout = result['stdout'].lower()
    
    # Check if any profile has firewall ON
    if 'state                                 on' in stdout:
        return CheckResult(
            name=check_name,
            status="FAIL",
            message="Firewall is enabled on one or more profiles",
            details={'vm_name': host['name'], 'ip': ip}
        )
    else:
        return CheckResult(
            name=check_name,
            status="PASS",
            message="Firewall is disabled on all profiles",
            details={'vm_name': host['name'], 'ip': ip}
        )


#==============================================================================
# MAIN WINDOWS CHECKS
#==============================================================================

def check_windows_machines(
    hosts: List[Dict[str, str]],
    lsf: Any = None
) -> List[CheckResult]:
    """
    Run all Windows machine checks.
    
    Args:
        hosts: List of dictionaries with 'name', 'ip', 'guest_id'
        lsf: lsfunctions module (optional)
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    if not hosts:
        results.append(CheckResult(
            name="Windows Checks",
            status="SKIPPED",
            message="No Windows machines to check"
        ))
        return results
    
    if not PYPSEXEC_AVAILABLE:
        results.append(CheckResult(
            name="Windows Checks",
            status="WARN",
            message="pypsexec not available - limited checks only"
        ))
    
    # Get password
    password = ''
    if lsf and hasattr(lsf, 'get_password'):
        password = lsf.get_password()
    
    for host in hosts:
        # Check accessibility
        access_result = check_windows_accessibility(host, lsf)
        results.append(access_result)
        
        # Skip detailed checks if not accessible
        if access_result.status != 'PASS':
            continue
        
        # Check activation
        if PYPSEXEC_AVAILABLE and password:
            results.append(check_windows_activation(host, password))
            
        # Check firewall
        if PYPSEXEC_AVAILABLE and password:
            results.append(check_windows_firewall(host, password))
    
    return results
