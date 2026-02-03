# autocheck_report.py - HOLFY27 AutoCheck Report Generation
# Version 1.0 - February 2026
# Author - HOL Core Team
#
# HTML and JSON report generation for AutoCheck validation results.

"""
AutoCheck Report Generation Module

Generates formatted reports from AutoCheck validation results:
- HTML report with styling and status indicators
- JSON report for machine processing
- Text log output
"""

import os
import json
import datetime
from typing import Dict, List, Any

from checks.base import CheckResult, ValidationReport, get_status_icon, get_status_class
import autocheck_config as config


#==============================================================================
# HTML REPORT GENERATION
#==============================================================================

def generate_html_report(report: ValidationReport, output_path: str):
    """
    Generate an HTML report from the validation results.
    
    Args:
        report: ValidationReport object with all check results
        output_path: Path to write the HTML file
    """
    html = generate_html_content(report)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(html)


def generate_html_content(report: ValidationReport) -> str:
    """
    Generate HTML content for the report.
    
    Args:
        report: ValidationReport object
        
    Returns:
        HTML string
    """
    summary = report.get_summary()
    
    # Status banner class
    if report.overall_status == 'FAIL':
        banner_class = 'banner-fail'
        banner_icon = '❌'
    elif report.overall_status == 'WARN':
        banner_class = 'banner-warn'
        banner_icon = '⚠️'
    else:
        banner_class = 'banner-pass'
        banner_icon = '✅'
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AutoCheck Report - {report.lab_sku}</title>
    <style>
        :root {{
            --pass-color: #16a34a;
            --fail-color: #dc2626;
            --warn-color: #ca8a04;
            --info-color: #2563eb;
            --skip-color: #6b7280;
            --fixed-color: #7c3aed;
        }}
        
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f1f5f9;
            color: #1e293b;
            line-height: 1.5;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            background: white;
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        h1 {{
            margin: 0 0 16px 0;
            color: #0f172a;
            font-size: 24px;
        }}
        
        .meta {{
            color: #64748b;
            font-size: 14px;
        }}
        
        .meta span {{
            margin-right: 24px;
        }}
        
        .banner {{
            padding: 16px 24px;
            border-radius: 8px;
            margin-bottom: 24px;
            font-weight: 600;
            font-size: 18px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .banner-pass {{
            background: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
        }}
        
        .banner-fail {{
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
        }}
        
        .banner-warn {{
            background: #fef3c7;
            color: #92400e;
            border: 1px solid #fcd34d;
        }}
        
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        
        .summary-card {{
            background: white;
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .summary-card .count {{
            font-size: 32px;
            font-weight: 700;
        }}
        
        .summary-card .label {{
            font-size: 12px;
            text-transform: uppercase;
            color: #64748b;
            margin-top: 4px;
        }}
        
        .summary-card.pass .count {{ color: var(--pass-color); }}
        .summary-card.fail .count {{ color: var(--fail-color); }}
        .summary-card.warn .count {{ color: var(--warn-color); }}
        .summary-card.info .count {{ color: var(--info-color); }}
        .summary-card.skip .count {{ color: var(--skip-color); }}
        
        section {{
            background: white;
            border-radius: 8px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        section h2 {{
            margin: 0;
            padding: 16px 24px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
            font-size: 16px;
            font-weight: 600;
            color: #334155;
        }}
        
        .check-list {{
            padding: 0;
            margin: 0;
            list-style: none;
        }}
        
        .check-item {{
            padding: 12px 24px;
            border-bottom: 1px solid #f1f5f9;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        
        .check-item:last-child {{
            border-bottom: none;
        }}
        
        .check-icon {{
            flex-shrink: 0;
            width: 24px;
            text-align: center;
        }}
        
        .check-content {{
            flex-grow: 1;
            min-width: 0;
        }}
        
        .check-name {{
            font-weight: 500;
            color: #1e293b;
        }}
        
        .check-message {{
            font-size: 14px;
            color: #64748b;
            margin-top: 2px;
        }}
        
        .check-status {{
            flex-shrink: 0;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .status-pass {{ background: #dcfce7; color: #166534; }}
        .status-fail {{ background: #fee2e2; color: #991b1b; }}
        .status-warn {{ background: #fef3c7; color: #92400e; }}
        .status-info {{ background: #dbeafe; color: #1e40af; }}
        .status-skipped {{ background: #f1f5f9; color: #475569; }}
        .status-fixed {{ background: #ede9fe; color: #5b21b6; }}
        
        .empty-section {{
            padding: 24px;
            text-align: center;
            color: #94a3b8;
        }}
        
        footer {{
            text-align: center;
            padding: 24px;
            color: #94a3b8;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>AutoCheck Report: {report.lab_sku}</h1>
            <div class="meta">
                <span>Generated: {report.timestamp}</span>
                <span>Expiration Window: {report.min_exp_date} to {report.max_exp_date}</span>
            </div>
        </header>
        
        <div class="banner {banner_class}">
            <span>{banner_icon}</span>
            <span>Overall Status: {report.overall_status}</span>
        </div>
        
        <div class="summary">
            <div class="summary-card pass">
                <div class="count">{summary['pass']}</div>
                <div class="label">Passed</div>
            </div>
            <div class="summary-card fail">
                <div class="count">{summary['fail']}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-card warn">
                <div class="count">{summary['warn']}</div>
                <div class="label">Warnings</div>
            </div>
            <div class="summary-card info">
                <div class="count">{summary['info']}</div>
                <div class="label">Info</div>
            </div>
            <div class="summary-card skip">
                <div class="count">{summary['skipped']}</div>
                <div class="label">Skipped</div>
            </div>
        </div>
'''
    
    # Add sections for each check category
    for category_id, category_name in config.CHECK_CATEGORIES:
        checks = getattr(report, category_id, [])
        
        if not checks:
            continue
        
        html += f'''
        <section>
            <h2>{category_name}</h2>
'''
        
        html += '            <ul class="check-list">\n'
        
        for check in checks:
            icon = get_status_icon(check.status)
            status_class = get_status_class(check.status)
            
            html += f'''                <li class="check-item">
                    <span class="check-icon">{icon}</span>
                    <div class="check-content">
                        <div class="check-name">{check.name}</div>
                        <div class="check-message">{check.message}</div>
                    </div>
                    <span class="check-status {status_class}">{check.status}</span>
                </li>
'''
        
        html += '            </ul>\n'
        html += '        </section>\n'
    
    # Footer
    html += f'''
        <footer>
            AutoCheck - HOLFY27 Lab Validation Tool | HOL Core Team
        </footer>
    </div>
</body>
</html>
'''
    
    return html


#==============================================================================
# JSON REPORT GENERATION
#==============================================================================

def generate_json_report(report: ValidationReport, output_path: str):
    """
    Generate a JSON report from the validation results.
    
    Args:
        report: ValidationReport object with all check results
        output_path: Path to write the JSON file
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(report.to_json())


#==============================================================================
# TEXT LOG GENERATION
#==============================================================================

def generate_text_log(report: ValidationReport, output_path: str):
    """
    Generate a text log from the validation results.
    
    Args:
        report: ValidationReport object with all check results
        output_path: Path to write the log file
    """
    lines = []
    summary = report.get_summary()
    
    lines.append('=' * 70)
    lines.append(f'AutoCheck Report: {report.lab_sku}')
    lines.append('=' * 70)
    lines.append(f'Generated: {report.timestamp}')
    lines.append(f'Expiration Window: {report.min_exp_date} to {report.max_exp_date}')
    lines.append(f'Overall Status: {report.overall_status}')
    lines.append('')
    lines.append(f'Summary: {summary["pass"]} passed, {summary["fail"]} failed, '
                 f'{summary["warn"]} warnings, {summary["info"]} info, '
                 f'{summary["skipped"]} skipped')
    lines.append('')
    
    # Add each category
    for category_id, category_name in config.CHECK_CATEGORIES:
        checks = getattr(report, category_id, [])
        
        if not checks:
            continue
        
        lines.append('-' * 70)
        lines.append(category_name)
        lines.append('-' * 70)
        
        for check in checks:
            lines.append(check.to_log_line())
        
        lines.append('')
    
    lines.append('=' * 70)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
