#!/usr/bin/env python3
# autocheck.py - HOLFY27 AutoCheck Main Orchestrator
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# Main entry point for AutoCheck lab validation.

"""
AutoCheck - HOLFY27 Lab Validation Tool

This tool validates lab configuration against HOL standards. It runs a series
of checks and generates HTML/JSON reports.

Usage:
    python3 autocheck.py [options]

Options:
    --report-only    Don't fix issues, just report
    --json           Output results as JSON
    --html FILE      Generate HTML report to specified file
    --verbose        Verbose output
    --skip-vsphere   Skip vSphere checks
    --skip-linux     Skip Linux machine checks
    --skip-windows   Skip Windows machine checks
"""

import sys
import os
import argparse
import datetime
import logging

# Add hol directory for imports
sys.path.insert(0, '/home/holuser/hol')

# Add parent directory for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import configuration
import autocheck_config as config

# Import base classes
from checks.base import CheckResult, ValidationReport

# Import lsfunctions
try:
    import lsfunctions as lsf
    LSF_AVAILABLE = True
except ImportError:
    LSF_AVAILABLE = False
    print('Warning: lsfunctions not available - some checks will be skipped')

# Import check modules
try:
    from checks import ssl_checks
    SSL_CHECKS_AVAILABLE = True
except ImportError:
    SSL_CHECKS_AVAILABLE = False

try:
    from checks import license_checks
    LICENSE_CHECKS_AVAILABLE = True
except ImportError:
    LICENSE_CHECKS_AVAILABLE = False

try:
    from checks import ntp_checks
    NTP_CHECKS_AVAILABLE = True
except ImportError:
    NTP_CHECKS_AVAILABLE = False

try:
    from checks import linux_checks
    LINUX_CHECKS_AVAILABLE = True
except ImportError:
    LINUX_CHECKS_AVAILABLE = False

try:
    from checks import windows_checks
    WINDOWS_CHECKS_AVAILABLE = True
except ImportError:
    WINDOWS_CHECKS_AVAILABLE = False

try:
    from checks import url_checks
    URL_CHECKS_AVAILABLE = True
except ImportError:
    URL_CHECKS_AVAILABLE = False

try:
    from checks import vsphere_checks
    VSPHERE_CHECKS_AVAILABLE = True
except ImportError:
    VSPHERE_CHECKS_AVAILABLE = False

try:
    import autocheck_report
    REPORT_AVAILABLE = True
except ImportError:
    REPORT_AVAILABLE = False

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


#==============================================================================
# MAIN ORCHESTRATOR
#==============================================================================

class AutoCheck:
    """
    Main AutoCheck orchestrator class.
    
    Coordinates all check modules and generates reports.
    """
    
    def __init__(self, args):
        """
        Initialize AutoCheck with command-line arguments.
        
        Args:
            args: Parsed argparse arguments
        """
        self.args = args
        self.fix_issues = not args.report_only
        self.verbose = args.verbose
        self.report = None
        self.start_time = datetime.datetime.now()
        
        # Lab info
        self.lab_sku = 'HOL-UNKNOWN'
        self.labtype = 'HOL'
        self.min_exp_date = None
        self.max_exp_date = None
        
        # vSphere connections
        self.sis = []  # ServiceInstance list
        
    def log(self, message: str, level: str = 'info'):
        """
        Log a message.
        
        Args:
            message: Message to log
            level: Log level (debug, info, warning, error)
        """
        if self.verbose or level != 'debug':
            getattr(logger, level)(message)
        
        # Also write to lsfunctions log if available
        if LSF_AVAILABLE:
            lsf.write_output(f'[AutoCheck] {message}')
    
    def initialize(self) -> bool:
        """
        Initialize AutoCheck - load configuration and connect to vSphere.
        
        Returns:
            True if initialization succeeded
        """
        self.log('Initializing AutoCheck...', 'info')
        
        # Initialize lsfunctions
        if LSF_AVAILABLE:
            try:
                lsf.init(router=False)
                self.lab_sku = lsf.lab_sku
                self.labtype = lsf.labtype
                self.log(f'Lab SKU: {self.lab_sku}', 'info')
                self.log(f'Lab Type: {self.labtype}', 'info')
            except Exception as e:
                self.log(f'Failed to initialize lsfunctions: {e}', 'error')
                return False
        
        # Calculate expiration dates
        self.min_exp_date, self.max_exp_date = config.get_expiration_dates(self.lab_sku)
        self.log(f'Expiration window: {self.min_exp_date} to {self.max_exp_date}', 'info')
        
        # Initialize report
        self.report = ValidationReport(
            lab_sku=self.lab_sku,
            min_exp_date=str(self.min_exp_date),
            max_exp_date=str(self.max_exp_date)
        )
        
        # Connect to vCenters if not skipping vSphere checks
        if not self.args.skip_vsphere and LSF_AVAILABLE:
            self._connect_vcenters()
        
        return True
    
    def _connect_vcenters(self):
        """Connect to all vCenters defined in config.ini"""
        if not LSF_AVAILABLE:
            return
        
        try:
            if lsf.config.has_option('RESOURCES', 'vCenters'):
                vcenters = lsf.config.get('RESOURCES', 'vCenters').split('\n')
                lsf.connect_vcenters(vcenters)
                self.sis = lsf.sis
                self.log(f'Connected to {len(self.sis)} vCenter(s)', 'info')
        except Exception as e:
            self.log(f'Failed to connect to vCenters: {e}', 'warning')
    
    def _disconnect_vcenters(self):
        """Disconnect from all vCenters"""
        if LSF_AVAILABLE and self.sis:
            try:
                lsf.disconnect_vcenters()
                self.log('Disconnected from vCenters', 'info')
            except Exception:
                pass
    
    def run_ssl_checks(self):
        """Run SSL certificate checks"""
        self.log('Running SSL certificate checks...', 'info')
        
        if not SSL_CHECKS_AVAILABLE:
            self.report.ssl_checks.append(CheckResult(
                name='SSL Checks',
                status='SKIPPED',
                message='SSL check module not available'
            ))
            return
        
        try:
            urls = self._get_urls_from_config()
            esxi_hosts = self._get_esxi_hosts_from_config()
            
            # Add ESXi hosts as HTTPS URLs
            for host in esxi_hosts:
                urls.append(f'https://{host}')
            
            results = ssl_checks.check_ssl_certificates(
                urls, 
                self.min_exp_date,
                lsf if LSF_AVAILABLE else None
            )
            self.report.ssl_checks.extend(results)
            
            self.log(f'SSL checks complete: {len(results)} certificates checked', 'info')
            
        except Exception as e:
            self.log(f'SSL checks failed: {e}', 'error')
            self.report.ssl_checks.append(CheckResult(
                name='SSL Checks',
                status='FAIL',
                message=f'Check failed with error: {e}'
            ))
    
    def run_license_checks(self):
        """Run vSphere license checks"""
        self.log('Running license checks...', 'info')
        
        if not LICENSE_CHECKS_AVAILABLE:
            self.report.license_checks.append(CheckResult(
                name='License Checks',
                status='SKIPPED',
                message='License check module not available'
            ))
            return
        
        if not self.sis:
            self.report.license_checks.append(CheckResult(
                name='License Checks',
                status='SKIPPED',
                message='No vCenter connections available'
            ))
            return
        
        try:
            results = license_checks.check_licenses(
                self.sis,
                self.min_exp_date,
                self.max_exp_date
            )
            self.report.license_checks.extend(results)
            
            self.log(f'License checks complete: {len(results)} licenses checked', 'info')
            
        except Exception as e:
            self.log(f'License checks failed: {e}', 'error')
            self.report.license_checks.append(CheckResult(
                name='License Checks',
                status='FAIL',
                message=f'Check failed with error: {e}'
            ))
    
    def run_ntp_checks(self):
        """Run NTP configuration checks"""
        self.log('Running NTP checks...', 'info')
        
        if not NTP_CHECKS_AVAILABLE:
            self.report.ntp_checks.append(CheckResult(
                name='NTP Checks',
                status='SKIPPED',
                message='NTP check module not available'
            ))
            return
        
        if not self.sis:
            self.report.ntp_checks.append(CheckResult(
                name='NTP Checks',
                status='SKIPPED',
                message='No vCenter connections available'
            ))
            return
        
        try:
            hosts = lsf.get_all_hosts() if LSF_AVAILABLE else []
            results = ntp_checks.check_ntp_configuration(hosts)
            self.report.ntp_checks.extend(results)
            
            self.log(f'NTP checks complete: {len(results)} hosts checked', 'info')
            
        except Exception as e:
            self.log(f'NTP checks failed: {e}', 'error')
            self.report.ntp_checks.append(CheckResult(
                name='NTP Checks',
                status='FAIL',
                message=f'Check failed with error: {e}'
            ))
    
    def run_vm_config_checks(self):
        """Run VM configuration checks"""
        self.log('Running VM configuration checks...', 'info')
        
        if not VSPHERE_CHECKS_AVAILABLE:
            self.report.vm_config_checks.append(CheckResult(
                name='VM Config Checks',
                status='SKIPPED',
                message='vSphere check module not available'
            ))
            return
        
        if not self.sis:
            self.report.vm_config_checks.append(CheckResult(
                name='VM Config Checks',
                status='SKIPPED',
                message='No vCenter connections available'
            ))
            return
        
        try:
            vms = lsf.get_all_vms() if LSF_AVAILABLE else []
            results = vsphere_checks.check_vm_configuration(vms, self.fix_issues)
            self.report.vm_config_checks.extend(results)
            
            self.log(f'VM config checks complete: {len(results)} VMs checked', 'info')
            
        except Exception as e:
            self.log(f'VM config checks failed: {e}', 'error')
            self.report.vm_config_checks.append(CheckResult(
                name='VM Config Checks',
                status='FAIL',
                message=f'Check failed with error: {e}'
            ))
    
    def run_url_checks(self):
        """Run URL accessibility checks"""
        self.log('Running URL checks...', 'info')
        
        if not URL_CHECKS_AVAILABLE:
            self.report.url_checks.append(CheckResult(
                name='URL Checks',
                status='SKIPPED',
                message='URL check module not available'
            ))
            return
        
        try:
            urls = self._get_urls_from_config()
            results = url_checks.check_urls(urls, lsf if LSF_AVAILABLE else None)
            self.report.url_checks.extend(results)
            
            self.log(f'URL checks complete: {len(results)} URLs checked', 'info')
            
        except Exception as e:
            self.log(f'URL checks failed: {e}', 'error')
            self.report.url_checks.append(CheckResult(
                name='URL Checks',
                status='FAIL',
                message=f'Check failed with error: {e}'
            ))
    
    def run_linux_checks(self):
        """Run Linux machine checks"""
        if self.args.skip_linux:
            self.log('Skipping Linux checks (--skip-linux)', 'info')
            return
        
        self.log('Running Linux machine checks...', 'info')
        
        if not LINUX_CHECKS_AVAILABLE:
            self.report.linux_checks.append(CheckResult(
                name='Linux Checks',
                status='SKIPPED',
                message='Linux check module not available'
            ))
            return
        
        try:
            # Get Linux hosts from config and L2 VMs
            linux_hosts = self._get_linux_hosts()
            results = linux_checks.check_linux_machines(
                linux_hosts,
                lsf if LSF_AVAILABLE else None
            )
            self.report.linux_checks.extend(results)
            
            self.log(f'Linux checks complete: {len(results)} machines checked', 'info')
            
        except Exception as e:
            self.log(f'Linux checks failed: {e}', 'error')
            self.report.linux_checks.append(CheckResult(
                name='Linux Checks',
                status='FAIL',
                message=f'Check failed with error: {e}'
            ))
    
    def run_windows_checks(self):
        """Run Windows machine checks"""
        if self.args.skip_windows:
            self.log('Skipping Windows checks (--skip-windows)', 'info')
            return
        
        self.log('Running Windows machine checks...', 'info')
        
        if not WINDOWS_CHECKS_AVAILABLE:
            self.report.windows_checks.append(CheckResult(
                name='Windows Checks',
                status='SKIPPED',
                message='Windows check module not available'
            ))
            return
        
        try:
            windows_hosts = self._get_windows_hosts()
            if not windows_hosts:
                self.report.windows_checks.append(CheckResult(
                    name='Windows Checks',
                    status='INFO',
                    message='No Windows machines to check'
                ))
                return
            
            results = windows_checks.check_windows_machines(
                windows_hosts,
                lsf if LSF_AVAILABLE else None
            )
            self.report.windows_checks.extend(results)
            
            self.log(f'Windows checks complete: {len(results)} machines checked', 'info')
            
        except Exception as e:
            self.log(f'Windows checks failed: {e}', 'error')
            self.report.windows_checks.append(CheckResult(
                name='Windows Checks',
                status='FAIL',
                message=f'Check failed with error: {e}'
            ))
    
    def run_vsphere_checks(self):
        """Run vSphere configuration checks (DRS, HA, datastores)"""
        if self.args.skip_vsphere:
            self.log('Skipping vSphere checks (--skip-vsphere)', 'info')
            return
        
        self.log('Running vSphere configuration checks...', 'info')
        
        if not VSPHERE_CHECKS_AVAILABLE:
            self.report.vsphere_checks.append(CheckResult(
                name='vSphere Checks',
                status='SKIPPED',
                message='vSphere check module not available'
            ))
            return
        
        if not self.sis:
            self.report.vsphere_checks.append(CheckResult(
                name='vSphere Checks',
                status='SKIPPED',
                message='No vCenter connections available'
            ))
            return
        
        try:
            results = vsphere_checks.check_vsphere_configuration(
                self.sis,
                lsf if LSF_AVAILABLE else None
            )
            self.report.vsphere_checks.extend(results)
            
            self.log(f'vSphere checks complete: {len(results)} items checked', 'info')
            
        except Exception as e:
            self.log(f'vSphere checks failed: {e}', 'error')
            self.report.vsphere_checks.append(CheckResult(
                name='vSphere Checks',
                status='FAIL',
                message=f'Check failed with error: {e}'
            ))
    
    def run_password_checks(self):
        """Run password expiration checks"""
        self.log('Running password expiration checks...', 'info')
        
        if not LINUX_CHECKS_AVAILABLE:
            self.report.password_expiration_checks.append(CheckResult(
                name='Password Checks',
                status='SKIPPED',
                message='Linux check module not available'
            ))
            return
        
        try:
            results = linux_checks.check_password_expirations(lsf if LSF_AVAILABLE else None)
            self.report.password_expiration_checks.extend(results)
            
            self.log(f'Password checks complete: {len(results)} accounts checked', 'info')
            
        except Exception as e:
            self.log(f'Password checks failed: {e}', 'error')
            self.report.password_expiration_checks.append(CheckResult(
                name='Password Checks',
                status='FAIL',
                message=f'Check failed with error: {e}'
            ))
    
    def _get_urls_from_config(self) -> list:
        """Get URLs from config.ini"""
        urls = []
        if not LSF_AVAILABLE:
            return urls
        
        try:
            # URLs from RESOURCES section
            if lsf.config.has_option('RESOURCES', 'URLs'):
                urls_raw = lsf.config.get('RESOURCES', 'URLs').split('\n')
                for entry in urls_raw:
                    if not entry or entry.strip().startswith('#'):
                        continue
                    url = entry.split(',')[0].strip()
                    if url:
                        urls.append(url)
            
            # NSX managers from VCF section
            if lsf.config.has_section('VCF'):
                if lsf.config.has_option('VCF', 'vcfnsxmgr'):
                    nsx_raw = lsf.config.get('VCF', 'vcfnsxmgr').split('\n')
                    for entry in nsx_raw:
                        if not entry or entry.strip().startswith('#'):
                            continue
                        hostname = entry.split(':')[0].strip()
                        if hostname:
                            urls.append(f'https://{hostname}')
            
            # VRA URLs from VCFFINAL section
            if lsf.config.has_section('VCFFINAL'):
                if lsf.config.has_option('VCFFINAL', 'vraurls'):
                    vra_raw = lsf.config.get('VCFFINAL', 'vraurls').split('\n')
                    for entry in vra_raw:
                        if not entry or entry.strip().startswith('#'):
                            continue
                        url = entry.split(',')[0].strip()
                        if url:
                            urls.append(url)
                            
        except Exception as e:
            self.log(f'Error reading URLs from config: {e}', 'warning')
        
        return urls
    
    def _get_esxi_hosts_from_config(self) -> list:
        """Get ESXi hosts from config.ini"""
        hosts = []
        if not LSF_AVAILABLE:
            return hosts
        
        try:
            if lsf.config.has_option('RESOURCES', 'ESXiHosts'):
                hosts_raw = lsf.config.get('RESOURCES', 'ESXiHosts').split('\n')
                for entry in hosts_raw:
                    if not entry or entry.strip().startswith('#'):
                        continue
                    hostname = entry.split(':')[0].strip()
                    if hostname:
                        hosts.append(hostname)
        except Exception as e:
            self.log(f'Error reading ESXi hosts from config: {e}', 'warning')
        
        return hosts
    
    def _get_linux_hosts(self) -> list:
        """Get Linux hosts to check from config and L2 VMs"""
        hosts = []
        
        # Get ESXi hosts (they're Linux-based)
        hosts.extend(self._get_esxi_hosts_from_config())
        
        # Get vCenters (VCSA is Linux-based)
        if LSF_AVAILABLE:
            try:
                if lsf.config.has_option('RESOURCES', 'vCenters'):
                    vc_raw = lsf.config.get('RESOURCES', 'vCenters').split('\n')
                    for entry in vc_raw:
                        if not entry or entry.strip().startswith('#'):
                            continue
                        hostname = entry.split(':')[0].strip()
                        if hostname:
                            hosts.append(hostname)
            except Exception:
                pass
        
        return hosts
    
    def _get_windows_hosts(self) -> list:
        """Get Windows hosts to check from L2 VMs"""
        windows_hosts = []
        
        if not LSF_AVAILABLE or not self.sis:
            return windows_hosts
        
        try:
            vms = lsf.get_all_vms()
            for vm in vms:
                try:
                    guest_id = vm.config.guestId if vm.config else ''
                    if guest_id and 'windows' in guest_id.lower():
                        # Get IP address
                        if vm.guest and vm.guest.ipAddress:
                            windows_hosts.append({
                                'name': vm.name,
                                'ip': vm.guest.ipAddress,
                                'guest_id': guest_id
                            })
                except Exception:
                    pass
        except Exception as e:
            self.log(f'Error getting Windows hosts: {e}', 'warning')
        
        return windows_hosts
    
    def generate_reports(self):
        """Generate HTML and JSON reports"""
        self.log('Generating reports...', 'info')
        
        # Calculate overall status
        self.report.calculate_overall_status()
        
        # Generate JSON output if requested
        if self.args.json:
            print(self.report.to_json())
        
        # Generate HTML report
        html_path = self.args.html or config.get_output_path(self.lab_sku, 'html')
        json_path = config.get_output_path(self.lab_sku, 'json')
        
        if REPORT_AVAILABLE:
            try:
                autocheck_report.generate_html_report(self.report, html_path)
                self.log(f'HTML report written to: {html_path}', 'info')
                
                autocheck_report.generate_json_report(self.report, json_path)
                self.log(f'JSON report written to: {json_path}', 'info')
            except Exception as e:
                self.log(f'Failed to generate reports: {e}', 'error')
        else:
            # Fallback: write basic JSON
            try:
                with open(json_path, 'w') as f:
                    f.write(self.report.to_json())
                self.log(f'JSON report written to: {json_path}', 'info')
            except Exception as e:
                self.log(f'Failed to write JSON report: {e}', 'error')
    
    def run(self) -> int:
        """
        Run all AutoCheck validations.
        
        Returns:
            Exit code (0 for success, 1 for failure)
        """
        self.log('=' * 60, 'info')
        self.log('AutoCheck - HOLFY27 Lab Validation', 'info')
        self.log('=' * 60, 'info')
        
        # Initialize
        if not self.initialize():
            return 1
        
        try:
            # Run all checks
            self.run_ssl_checks()
            self.run_license_checks()
            self.run_ntp_checks()
            self.run_vm_config_checks()
            self.run_url_checks()
            self.run_linux_checks()
            self.run_windows_checks()
            self.run_vsphere_checks()
            self.run_password_checks()
            
            # Generate reports
            self.generate_reports()
            
            # Print summary
            summary = self.report.get_summary()
            elapsed = datetime.datetime.now() - self.start_time
            
            self.log('=' * 60, 'info')
            self.log(f'AutoCheck Complete - {self.report.overall_status}', 'info')
            self.log(f'Summary: {summary["pass"]} passed, {summary["fail"]} failed, '
                    f'{summary["warn"]} warnings', 'info')
            self.log(f'Elapsed time: {elapsed}', 'info')
            self.log('=' * 60, 'info')
            
            # Return exit code
            return 0 if self.report.overall_status != 'FAIL' else 1
            
        finally:
            # Cleanup
            self._disconnect_vcenters()


#==============================================================================
# MAIN
#==============================================================================

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description='HOLFY27 AutoCheck - Lab Validation Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--report-only',
        action='store_true',
        help="Don't fix issues, just report"
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON to stdout'
    )
    
    parser.add_argument(
        '--html',
        type=str,
        metavar='FILE',
        help='Generate HTML report to specified file'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--skip-vsphere',
        action='store_true',
        help='Skip vSphere checks'
    )
    
    parser.add_argument(
        '--skip-linux',
        action='store_true',
        help='Skip Linux machine checks'
    )
    
    parser.add_argument(
        '--skip-windows',
        action='store_true',
        help='Skip Windows machine checks'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_args()
    autocheck = AutoCheck(args)
    return autocheck.run()


if __name__ == '__main__':
    sys.exit(main())
