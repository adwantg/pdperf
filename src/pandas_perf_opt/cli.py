"""pdperf CLI - Pandas Performance Optimizer.

Commands:
    scan      Scan files for performance anti-patterns
    rules     List available rules
    explain   Show detailed explanation for a rule

Author: gadwant
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .analyzer import analyze_path_with_errors
from .config import load_config, apply_profile, list_profiles
from .reporting import format_text_with_errors, write_json_with_errors, write_sarif
from .rules import Severity, list_rules, get_rule


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdperf",
        description="Pandas Performance Optimizer - Static linter for pandas anti-patterns",
    )
    parser.add_argument("--version", action="version", version=f"pdperf {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # === scan command ===
    scan_parser = subparsers.add_parser("scan", help="Scan files for performance anti-patterns")
    scan_parser.add_argument("path", help="File or directory to scan")
    scan_parser.add_argument(
        "--format",
        choices=["json", "text", "sarif"],
        default="text",
        help="Output format (default: text)",
    )
    scan_parser.add_argument(
        "--out",
        help="Output file path (default: stdout for text, out/report.json for json)",
    )
    scan_parser.add_argument(
        "--select",
        help="Only check these rules (comma-separated, e.g., PPO001,PPO002)",
    )
    scan_parser.add_argument(
        "--ignore",
        help="Ignore these rules (comma-separated, e.g., PPO005)",
    )
    scan_parser.add_argument(
        "--severity-threshold",
        choices=["warn", "error"],
        default="warn",
        help="Minimum severity to report (default: warn)",
    )
    scan_parser.add_argument(
        "--fail-on",
        choices=["warn", "error", "none"],
        default="error",
        help="Exit with code 1 if findings at this level or above (default: error)",
    )
    scan_parser.add_argument(
        "--patch",
        metavar="FILE",
        help="Generate unified diff patch for auto-fixable rules (e.g., --patch fixes.diff)",
    )
    scan_parser.add_argument(
        "--fail-on-parse-error",
        action="store_true",
        help="Exit with code 2 if any files have syntax errors",
    )
    scan_parser.add_argument(
        "--min-confidence",
        choices=["high", "medium", "low"],
        default="low",
        help="Minimum confidence level to report (default: low = all)",
    )
    scan_parser.add_argument(
        "--profile",
        choices=list_profiles(),
        help="Use a predefined rule profile (etl, notebook)",
    )
    scan_parser.add_argument(
        "--baseline",
        metavar="FILE",
        help="Only report findings not in this baseline file",
    )
    scan_parser.add_argument(
        "--output-baseline",
        metavar="FILE",
        help="Generate baseline file for future comparisons",
    )

    # === rules command ===
    rules_parser = subparsers.add_parser("rules", help="List available rules")
    rules_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    # === explain command ===
    explain_parser = subparsers.add_parser("explain", help="Show detailed explanation for a rule")
    explain_parser.add_argument("rule_id", help="Rule ID (e.g., PPO001)")

    return parser


def parse_rule_list(rule_str: str | None) -> set[str] | None:
    """Parse a comma-separated rule list."""
    if not rule_str:
        return None
    return {r.strip().upper() for r in rule_str.split(",") if r.strip()}


def generate_patch(findings: list, source_files: dict[str, str]) -> str:
    """Generate unified diff for patchable findings.
    
    Currently supports:
    - PPO004: df[mask]['col'] = val -> df.loc[mask, 'col'] = val
    - PPO006: df.values -> df.to_numpy()
    """
    import difflib
    
    patches = []
    
    # Group findings by file
    findings_by_file: dict[str, list] = {}
    for f in findings:
        rule = get_rule(f.rule_id)
        if rule and rule.patchable:
            if f.path not in findings_by_file:
                findings_by_file[f.path] = []
            findings_by_file[f.path].append(f)
    
    for file_path, file_findings in findings_by_file.items():
        if file_path not in source_files:
            continue
            
        original_lines = source_files[file_path].splitlines(keepends=True)
        modified_lines = list(original_lines)
        
        # Sort findings by line in reverse order to avoid offset issues
        for finding in sorted(file_findings, key=lambda f: f.line, reverse=True):
            line_idx = finding.line - 1  # 0-indexed
            if line_idx >= len(modified_lines):
                continue
                
            line = modified_lines[line_idx]
            
            if finding.rule_id == "PPO006":
                # Replace .values with .to_numpy()
                if ".values" in line:
                    modified_lines[line_idx] = line.replace(".values", ".to_numpy()")
            
            # PPO004 is more complex - would need AST rewriting
            # For now, add a comment indicating the fix needed
            elif finding.rule_id == "PPO004":
                indent = len(line) - len(line.lstrip())
                comment = " " * indent + "# TODO (pdperf): Rewrite using .loc[mask, col] = val\n"
                if not modified_lines[line_idx].startswith(" " * indent + "# TODO (pdperf)"):
                    modified_lines.insert(line_idx, comment)
        
        if original_lines != modified_lines:
            diff = difflib.unified_diff(
                original_lines,
                modified_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
            patches.append("".join(diff))
    
    return "\n".join(patches)


def cmd_scan(args: argparse.Namespace) -> int:
    """Execute the scan command."""
    import json
    
    root = Path(args.path)
    if not root.exists():
        print(f"Error: Path does not exist: {args.path}", file=sys.stderr)
        return 2

    # Load config from pyproject.toml
    config = load_config()
    
    # Apply profile if specified
    if args.profile:
        config = apply_profile(config, args.profile)
        print(f"Using profile: {args.profile}")

    # Parse rule filters (CLI overrides config)
    selected = parse_rule_list(args.select) or config.select or None
    ignored = parse_rule_list(args.ignore) or config.ignore or set()

    # Collect source files for patching
    source_files = {}
    
    if root.is_file() and root.suffix == ".py":
        files = [root]
    elif root.is_dir():
        files = list(root.rglob("*.py"))
    else:
        files = []
    
    for file_path in files:
        try:
            source = file_path.read_text(encoding="utf-8")
            source_files[str(file_path)] = source
        except (OSError, UnicodeDecodeError):
            continue
    
    # Analyze with parse error tracking
    result = analyze_path_with_errors(root, selected, ignored)
    findings = result.findings
    parse_errors = result.parse_errors

    # Filter by severity threshold
    if args.severity_threshold == "error":
        findings = [f for f in findings if f.severity == Severity.ERROR]

    # Filter by minimum confidence
    confidence_order = {"high": 3, "medium": 2, "low": 1}
    min_conf = confidence_order.get(args.min_confidence, 1)
    findings = [f for f in findings if confidence_order.get(f.confidence.value, 1) >= min_conf]

    # Load baseline and filter if specified
    if args.baseline:
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            try:
                baseline_data = json.loads(baseline_path.read_text())
                baseline_set = {
                    (f["path"], f["line"], f["rule_id"])
                    for f in baseline_data.get("findings", [])
                }
                original_count = len(findings)
                findings = [
                    f for f in findings
                    if (f.path, f.line, f.rule_id) not in baseline_set
                ]
                print(f"Baseline: {original_count - len(findings)} existing findings filtered out")
            except Exception as e:
                print(f"Warning: Could not load baseline: {e}", file=sys.stderr)

    # Output baseline if requested
    if args.output_baseline:
        from .reporting import findings_to_dict
        baseline_path = Path(args.output_baseline)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(findings_to_dict(result.findings), indent=2))
        print(f"Generated baseline with {len(result.findings)} findings: {args.output_baseline}")

    # Generate patch if requested
    if args.patch:
        patch_content = generate_patch(findings, source_files)
        if patch_content:
            Path(args.patch).parent.mkdir(parents=True, exist_ok=True)
            Path(args.patch).write_text(patch_content)
            patchable_count = sum(1 for f in findings if get_rule(f.rule_id) and get_rule(f.rule_id).patchable)
            print(f"Generated patch for {patchable_count} findings: {args.patch}")
        else:
            print("No patchable findings found.")

    # Output results
    if args.format == "json":
        out_path = args.out or "out/report.json"
        write_json_with_errors(findings, parse_errors, out_path)
        print(f"Wrote {len(findings)} findings to {out_path}")
        if parse_errors:
            print(f"  (with {len(parse_errors)} parse errors)")
    elif args.format == "sarif":
        out_path = args.out or "out/report.sarif"
        write_sarif(findings, out_path)
        print(f"Wrote {len(findings)} findings to {out_path}")
        if parse_errors:
            print(f"Warning: {len(parse_errors)} files could not be parsed")
    else:
        output = format_text_with_errors(findings, parse_errors)
        if args.out:
            Path(args.out).write_text(output)
            print(f"Wrote report to {args.out}")
        else:
            print(output)

    # Check for parse errors first (exit 2)
    if args.fail_on_parse_error and parse_errors:
        return 2

    # Determine exit code based on findings
    if args.fail_on == "none":
        return 0
    elif args.fail_on == "error":
        has_errors = any(f.severity == Severity.ERROR for f in findings)
        return 1 if has_errors else 0
    else:  # fail_on == "warn"
        return 1 if findings else 0


def cmd_rules(args: argparse.Namespace) -> int:
    """Execute the rules command."""
    rules = list_rules()

    if args.format == "json":
        import json
        data = [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "severity": r.severity.value,
                "message": r.message,
                "suggested_fix": r.suggested_fix,
                "docs_url": r.docs_url,
                "patchable": r.patchable,
            }
            for r in rules
        ]
        print(json.dumps(data, indent=2))
    else:
        print("Available rules:\n")
        for r in rules:
            severity_icon = "⚠️" if r.severity == Severity.WARN else "❌"
            patch_icon = "🔧" if r.patchable else ""
            print(f"  {severity_icon} {r.rule_id}: {r.name} {patch_icon}")
            print(f"     {r.message}")
            print(f"     💡 {r.suggested_fix}")
            print()

    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    """Execute the explain command."""
    rule_id = args.rule_id.upper()
    rule = get_rule(rule_id)
    
    if rule is None:
        print(f"Error: Unknown rule '{rule_id}'", file=sys.stderr)
        print("\nAvailable rules:")
        for r in list_rules():
            print(f"  - {r.rule_id}: {r.name}")
        return 2
    
    # Header
    severity_icon = "⚠️" if rule.severity == Severity.WARN else "❌"
    patch_indicator = " (auto-fixable)" if rule.patchable else ""
    
    print(f"\n{severity_icon} {rule.rule_id}: {rule.name}{patch_indicator}")
    print("=" * 60)
    print(f"\n{rule.message}\n")
    print(f"💡 Suggested fix: {rule.suggested_fix}\n")
    
    if rule.explanation:
        print(rule.explanation.strip())
        print()
    
    if rule.docs_url:
        print(f"📖 Documentation: {rule.docs_url}")
    
    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        return cmd_scan(args)
    elif args.command == "rules":
        return cmd_rules(args)
    elif args.command == "explain":
        return cmd_explain(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())

