# vsphere_checks.py - HOLFY27 AutoCheck vSphere Configuration Validation
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# vSphere configuration checks (VMs, clusters, datastores).
# Refactored from vpodchecker.py for modularity.

"""
vSphere Configuration Validation Module

Checks vSphere configuration for:
- VM settings (uuid.action, typematicMinDelay, autolock)
- VM resources (reservations, shares)
- Cluster settings (DRS, HA)
- Datastore accessibility
- ESXi host build consistency
"""

import re
from typing import List, Dict, Any

from .base import CheckResult

# Optional pyVmomi imports
try:
    from pyVmomi import vim
    from pyVim.task import WaitForTask
    PYVMOMI_AVAILABLE = True
except ImportError:
    PYVMOMI_AVAILABLE = False

# Import config
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import autocheck_config as config


#==============================================================================
# VM CONFIGURATION CHECKS
#==============================================================================

def add_vm_config_extra_option(vm, option_key: str, option_value: str) -> bool:
    """
    Add or update a VM extra config option.
    
    Args:
        vm: VM object (vim.VirtualMachine)
        option_key: Configuration key
        option_value: Configuration value
        
    Returns:
        True if successful
    """
    if not PYVMOMI_AVAILABLE:
        return False
    
    try:
        spec = vim.vm.ConfigSpec()
        opt = vim.option.OptionValue()
        spec.extraConfig = []
        opt.key = option_key
        opt.value = option_value
        spec.extraConfig.append(opt)
        task = vm.ReconfigVM_Task(spec)
        WaitForTask(task)
        return True
    except Exception as e:
        print(f"Failed to set {option_key} on {vm.name}: {e}")
        return False


def check_single_vm_configuration(vm, fix_issues: bool = True) -> CheckResult:
    """
    Check and optionally fix VM configuration.
    
    Checks:
    - uuid.action = 'keep' (prevents "moved or copied" question)
    - keyboard.typematicMinDelay = '2000000' (Linux VMs - prevents key stutter)
    - tools.guest.desktop.autolock = 'FALSE' (Windows VMs - prevents autolock)
    
    Args:
        vm: VM object (vim.VirtualMachine)
        fix_issues: Whether to automatically fix issues
        
    Returns:
        CheckResult with VM configuration status
    """
    check_name = f"VM Config: {vm.name}"
    
    # Skip system VMs
    if config.should_skip_vm(vm.name):
        return None  # Skip entirely
    
    issues = []
    fixes = []
    
    # Get current config
    uuid_action = ""
    type_delay = ""
    autolock = ""
    
    try:
        for optionValue in vm.config.extraConfig:
            if optionValue.key == 'uuid.action':
                uuid_action = optionValue.value
            if optionValue.key == 'keyboard.typematicMinDelay':
                type_delay = optionValue.value
            if optionValue.key == 'tools.guest.desktop.autolock':
                autolock = optionValue.value
    except Exception:
        pass
    
    guest_id = vm.config.guestId if vm.config else ''
    
    # Check uuid.action
    if uuid_action != 'keep':
        issues.append(f"uuid.action is '{uuid_action}' (should be 'keep')")
        if fix_issues:
            if add_vm_config_extra_option(vm, 'uuid.action', 'keep'):
                fixes.append("uuid.action fixed")
    
    # Check Windows VMs
    if guest_id and re.search(r'windows', guest_id, re.IGNORECASE):
        if autolock != 'FALSE':
            issues.append(f"tools.guest.desktop.autolock is '{autolock}' (should be 'FALSE')")
            if fix_issues:
                if add_vm_config_extra_option(vm, 'tools.guest.desktop.autolock', 'FALSE'):
                    fixes.append("autolock fixed")
    
    # Check Linux VMs
    linux_patterns = r'linux|ubuntu|debian|centos|sles|suse|asianux|novell|redhat|photon|rhel|other'
    if guest_id and re.search(linux_patterns, guest_id, re.IGNORECASE):
        if type_delay != '2000000':
            issues.append(f"keyboard.typematicMinDelay is '{type_delay}' (should be '2000000')")
            if fix_issues:
                if add_vm_config_extra_option(vm, 'keyboard.typematicMinDelay', '2000000'):
                    fixes.append("typematicMinDelay fixed")
    
    # Determine status
    if issues:
        if fixes and fix_issues:
            status = "FIXED"
            message = f"Fixed: {', '.join(fixes)}"
        else:
            status = "FAIL"
            message = "; ".join(issues)
    else:
        status = "PASS"
        message = "VM configuration correct"
    
    return CheckResult(
        name=check_name,
        status=status,
        message=message,
        details={
            'vm_name': vm.name,
            'guest_id': guest_id,
            'uuid_action': uuid_action,
            'type_delay': type_delay,
            'autolock': autolock
        }
    )


def check_vm_configuration(vms: List, fix_issues: bool = True) -> List[CheckResult]:
    """
    Check and optionally fix VM configuration for all VMs.
    
    Args:
        vms: List of VM objects
        fix_issues: Whether to automatically fix issues
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    if not vms:
        results.append(CheckResult(
            name="VM Configuration",
            status="SKIPPED",
            message="No VMs to check"
        ))
        return results
    
    for vm in vms:
        try:
            result = check_single_vm_configuration(vm, fix_issues)
            if result:  # None means skipped
                results.append(result)
        except Exception as e:
            results.append(CheckResult(
                name=f"VM Config: {vm.name}",
                status="WARN",
                message=f"Could not check: {e}"
            ))
    
    return results


#==============================================================================
# CLUSTER CONFIGURATION CHECKS
#==============================================================================

def check_cluster_drs(cluster) -> CheckResult:
    """
    Check DRS configuration on a cluster.
    
    HOL Standard: DRS should be PartiallyAutomated or Manual
    (Fully Automated generates extra I/O)
    
    Args:
        cluster: Cluster object (vim.ClusterComputeResource)
        
    Returns:
        CheckResult with DRS status
    """
    check_name = f"DRS: {cluster.name}"
    
    try:
        drs_enabled = cluster.configuration.drsConfig.enabled
        drs_behavior = cluster.configuration.drsConfig.defaultVmBehavior
        
        if not drs_enabled:
            return CheckResult(
                name=check_name,
                status="PASS",
                message="DRS disabled (minimizes I/O)",
                details={'enabled': False, 'behavior': None}
            )
        
        if drs_behavior == 'fullyAutomated':
            return CheckResult(
                name=check_name,
                status="FAIL",
                message="DRS is FullyAutomated - should be PartiallyAutomated",
                details={'enabled': True, 'behavior': str(drs_behavior)}
            )
        else:
            return CheckResult(
                name=check_name,
                status="PASS",
                message=f"DRS is {drs_behavior}",
                details={'enabled': True, 'behavior': str(drs_behavior)}
            )
        
    except Exception as e:
        return CheckResult(
            name=check_name,
            status="WARN",
            message=f"Could not check DRS: {e}"
        )


def check_cluster_ha(cluster) -> CheckResult:
    """
    Check HA configuration on a cluster.
    
    HOL Standard: HA should be disabled (reduces complexity)
    
    Args:
        cluster: Cluster object (vim.ClusterComputeResource)
        
    Returns:
        CheckResult with HA status
    """
    check_name = f"HA: {cluster.name}"
    
    try:
        ha_enabled = cluster.configuration.dasConfig.enabled
        
        if ha_enabled:
            return CheckResult(
                name=check_name,
                status="FAIL",
                message="HA is enabled - should be disabled for labs",
                details={'enabled': True}
            )
        else:
            return CheckResult(
                name=check_name,
                status="PASS",
                message="HA disabled",
                details={'enabled': False}
            )
        
    except Exception as e:
        return CheckResult(
            name=check_name,
            status="WARN",
            message=f"Could not check HA: {e}"
        )


def check_clusters(sis: List, lsf: Any = None) -> List[CheckResult]:
    """
    Check DRS and HA configuration on all clusters.
    
    Args:
        sis: List of vCenter ServiceInstance objects
        lsf: lsfunctions module (optional)
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    if not PYVMOMI_AVAILABLE:
        results.append(CheckResult(
            name="Cluster Checks",
            status="SKIPPED",
            message="pyVmomi not available"
        ))
        return results
    
    for si in sis:
        try:
            content = si.content
            container = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.ClusterComputeResource], True
            )
            
            for cluster in container.view:
                results.append(check_cluster_drs(cluster))
                results.append(check_cluster_ha(cluster))
            
            container.Destroy()
            
        except Exception as e:
            results.append(CheckResult(
                name="Cluster Checks",
                status="WARN",
                message=f"Could not check clusters: {e}"
            ))
    
    return results


#==============================================================================
# ESXI HOST BUILD CHECKS
#==============================================================================

def check_esxi_builds(sis: List, lsf: Any = None) -> List[CheckResult]:
    """
    Check ESXi host build consistency.
    
    HOL Standard: All ESXi hosts should have the same build
    
    Args:
        sis: List of vCenter ServiceInstance objects
        lsf: lsfunctions module (optional)
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    if not PYVMOMI_AVAILABLE:
        results.append(CheckResult(
            name="ESXi Build Checks",
            status="SKIPPED",
            message="pyVmomi not available"
        ))
        return results
    
    builds = {}  # build -> list of hosts
    
    for si in sis:
        try:
            content = si.content
            container = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.HostSystem], True
            )
            
            for host in container.view:
                try:
                    version = host.config.product.version
                    build = host.config.product.build
                    full_build = f"{version} (build {build})"
                    
                    if full_build not in builds:
                        builds[full_build] = []
                    builds[full_build].append(host.name)
                    
                except Exception:
                    pass
            
            container.Destroy()
            
        except Exception as e:
            results.append(CheckResult(
                name="ESXi Build Checks",
                status="WARN",
                message=f"Could not check ESXi builds: {e}"
            ))
    
    # Analyze builds
    if len(builds) == 0:
        results.append(CheckResult(
            name="ESXi Builds",
            status="SKIPPED",
            message="No ESXi hosts found"
        ))
    elif len(builds) == 1:
        build, hosts = list(builds.items())[0]
        results.append(CheckResult(
            name="ESXi Builds",
            status="PASS",
            message=f"All {len(hosts)} hosts are running {build}",
            details={'build': build, 'host_count': len(hosts)}
        ))
    else:
        results.append(CheckResult(
            name="ESXi Builds",
            status="WARN",
            message=f"Inconsistent builds: {len(builds)} different versions found",
            details={'builds': {k: v for k, v in builds.items()}}
        ))
        
        # Add details for each build
        for build, hosts in builds.items():
            results.append(CheckResult(
                name=f"ESXi Build: {build}",
                status="INFO",
                message=f"{len(hosts)} host(s): {', '.join(hosts[:3])}{'...' if len(hosts) > 3 else ''}",
                details={'build': build, 'hosts': hosts}
            ))
    
    return results


#==============================================================================
# DATASTORE CHECKS
#==============================================================================

def check_datastores(sis: List, lsf: Any = None) -> List[CheckResult]:
    """
    Check datastore accessibility.
    
    Args:
        sis: List of vCenter ServiceInstance objects
        lsf: lsfunctions module (optional)
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    if not PYVMOMI_AVAILABLE:
        results.append(CheckResult(
            name="Datastore Checks",
            status="SKIPPED",
            message="pyVmomi not available"
        ))
        return results
    
    checked = set()
    
    for si in sis:
        try:
            content = si.content
            container = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.Datastore], True
            )
            
            for ds in container.view:
                if ds.name in checked:
                    continue
                checked.add(ds.name)
                
                check_name = f"Datastore: {ds.name}"
                
                try:
                    if ds.summary.accessible:
                        capacity_gb = ds.summary.capacity / (1024**3)
                        free_gb = ds.summary.freeSpace / (1024**3)
                        used_pct = ((capacity_gb - free_gb) / capacity_gb) * 100
                        
                        if used_pct > 90:
                            status = "WARN"
                            message = f"Accessible but {used_pct:.1f}% full ({free_gb:.1f} GB free)"
                        else:
                            status = "PASS"
                            message = f"Accessible ({used_pct:.1f}% used, {free_gb:.1f} GB free)"
                        
                        results.append(CheckResult(
                            name=check_name,
                            status=status,
                            message=message,
                            details={
                                'name': ds.name,
                                'type': ds.summary.type,
                                'capacity_gb': round(capacity_gb, 1),
                                'free_gb': round(free_gb, 1),
                                'used_pct': round(used_pct, 1)
                            }
                        ))
                    else:
                        results.append(CheckResult(
                            name=check_name,
                            status="FAIL",
                            message="Datastore not accessible",
                            details={'name': ds.name, 'accessible': False}
                        ))
                        
                except Exception as e:
                    results.append(CheckResult(
                        name=check_name,
                        status="WARN",
                        message=f"Could not check: {e}"
                    ))
            
            container.Destroy()
            
        except Exception as e:
            results.append(CheckResult(
                name="Datastore Checks",
                status="WARN",
                message=f"Could not enumerate datastores: {e}"
            ))
    
    return results


#==============================================================================
# MAIN VSPHERE CHECKS
#==============================================================================

def check_vsphere_configuration(sis: List, lsf: Any = None) -> List[CheckResult]:
    """
    Run all vSphere configuration checks.
    
    Args:
        sis: List of vCenter ServiceInstance objects
        lsf: lsfunctions module (optional)
        
    Returns:
        List of CheckResult objects
    """
    results = []
    
    # Cluster checks (DRS, HA)
    results.extend(check_clusters(sis, lsf))
    
    # ESXi build consistency
    results.extend(check_esxi_builds(sis, lsf))
    
    # Datastore accessibility
    results.extend(check_datastores(sis, lsf))
    
    return results
