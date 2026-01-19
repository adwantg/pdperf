"""Report rendering (JSON, text, SARIF).

Provides deterministic output formats for CI/pre-commit integration.

Author: gadwant
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .analyzer import Finding, ParseError


def findings_to_dict(findings: list["Finding"], version: str = "0.1.0") -> dict:
    """Convert findings to a dictionary for JSON serialization.
    
    The output schema is versioned for tooling stability:
    - schema_version: "1.0" — incremented on breaking changes
    - Deterministic ordering: path → line → col → rule_id
    """
    return {
        "schema_version": "1.0",
        "tool": "pdperf",
        "tool_version": version,
        "total_findings": len(findings),
        "findings": [f.to_dict() for f in sorted(findings, key=lambda x: (x.path, x.line, x.col, x.rule_id))],
    }


def findings_to_dict_with_errors(
    findings: list["Finding"],
    parse_errors: list["ParseError"],
    version: str = "0.1.0"
) -> dict:
    """Convert findings and parse errors to a dictionary for JSON serialization."""
    return {
        "schema_version": "1.0",
        "tool": "pdperf",
        "tool_version": version,
        "total_findings": len(findings),
        "total_parse_errors": len(parse_errors),
        "findings": [f.to_dict() for f in sorted(findings, key=lambda x: (x.path, x.line, x.col, x.rule_id))],
        "parse_errors": [e.to_dict() for e in sorted(parse_errors, key=lambda x: x.path)],
    }


def write_json(findings: list["Finding"], out_path: str, version: str = "0.1.0") -> None:
    """Write findings to a JSON file."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = findings_to_dict(findings, version)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True))


def write_json_with_errors(
    findings: list["Finding"],
    parse_errors: list["ParseError"],
    out_path: str,
    version: str = "0.1.0"
) -> None:
    """Write findings and parse errors to a JSON file."""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = findings_to_dict_with_errors(findings, parse_errors, version)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True))


def format_text(findings: list["Finding"]) -> str:
    """Format findings as human-readable text."""
    if not findings:
        return "No issues found."

    lines = []
    sorted_findings = sorted(findings, key=lambda x: (x.path, x.line, x.col, x.rule_id))

    current_path = None
    for f in sorted_findings:
        if f.path != current_path:
            if current_path is not None:
                lines.append("")
            lines.append(f"📄 {f.path}")
            current_path = f.path

        severity_icon = "⚠️" if f.severity.value == "warn" else "❌"
        lines.append(f"  {severity_icon} {f.line}:{f.col} [{f.rule_id}] {f.message}")
        lines.append(f"     💡 {f.suggested_fix}")

    return "\n".join(lines)


def format_text_with_errors(findings: list["Finding"], parse_errors: list["ParseError"]) -> str:
    """Format findings and parse errors as human-readable text."""
    lines = []

    # Format parse errors first
    if parse_errors:
        lines.append("⚠️  Parse Errors (files skipped):")
        for err in sorted(parse_errors, key=lambda x: x.path):
            lines.append(f"   🚫 {err.path}:{err.line}:{err.col} — {err.message}")
        lines.append("")

    # Format findings
    if not findings and not parse_errors:
        return "No issues found."
    elif not findings:
        return "\n".join(lines) + "\nNo performance issues found."

    sorted_findings = sorted(findings, key=lambda x: (x.path, x.line, x.col, x.rule_id))

    current_path = None
    for f in sorted_findings:
        if f.path != current_path:
            if current_path is not None:
                lines.append("")
            lines.append(f"📄 {f.path}")
            current_path = f.path

        severity_icon = "⚠️" if f.severity.value == "warn" else "❌"
        lines.append(f"  {severity_icon} {f.line}:{f.col} [{f.rule_id}] {f.message}")
        lines.append(f"     💡 {f.suggested_fix}")

    return "\n".join(lines)


def write_sarif(findings: list["Finding"], out_path: str, version: str = "0.1.0") -> None:
    """Write findings in SARIF format for GitHub Security integration."""
    rules = {}
    results = []

    for f in findings:
        if f.rule_id not in rules:
            rules[f.rule_id] = {
                "id": f.rule_id,
                "shortDescription": {"text": f.message},
                "helpUri": f"https://pdperf.dev/rules/{f.rule_id}",
                "properties": {
                    "severity": f.severity.value,
                }
            }

        results.append({
            "ruleId": f.rule_id,
            "level": "warning" if f.severity.value == "warn" else "error",
            "message": {"text": f.message},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.path},
                    "region": {
                        "startLine": f.line,
                        "startColumn": f.col + 1,  # SARIF uses 1-based columns
                    }
                }
            }],
            "fixes": [{
                "description": {"text": f.suggested_fix}
            }]
        })

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "pdperf",
                    "version": version,
                    "informationUri": "https://github.com/adwantg/pdperf",
                    "rules": list(rules.values())
                }
            },
            "results": results
        }]
    }

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(sarif, indent=2))

