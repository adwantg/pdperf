"""AST-based analyzer with complete rule detection.

Implements PPO001-PPO010 detection using Python AST traversal.

Author: gadwant
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .rules import Severity, Confidence, get_rule


@dataclass(frozen=True)
class Finding:
    """A detected performance anti-pattern."""
    rule_id: str
    message: str
    path: str
    line: int
    col: int
    severity: Severity
    suggested_fix: str
    confidence: Confidence = Confidence.HIGH
    confidence_reason: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule_id": self.rule_id,
            "path": self.path,
            "line": self.line,
            "col": self.col,
            "severity": self.severity.value,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "confidence": self.confidence.value,
            "confidence_reason": self.confidence_reason,
        }


@dataclass(frozen=True)
class ParseError:
    """A file that could not be parsed due to syntax error."""
    path: str
    line: int
    col: int
    message: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "line": self.line,
            "col": self.col,
            "message": self.message,
        }


@dataclass
class AnalysisResult:
    """Result of analyzing one or more files."""
    findings: list[Finding] = field(default_factory=list)
    parse_errors: list[ParseError] = field(default_factory=list)


class PandasPerfVisitor(ast.NodeVisitor):
    """AST visitor that detects pandas performance anti-patterns."""

    def __init__(self, path: str, selected_rules: set[str] | None = None, ignored_rules: set[str] | None = None):
        self.path = path
        self.findings: list[Finding] = []
        self.selected_rules = selected_rules
        self.ignored_rules = ignored_rules or set()
        # Track loop context for detecting patterns inside loops
        self._loop_stack: list[ast.AST] = []
        # Track variable assignments for concat/append detection
        self._assignments_in_loop: dict[str, list[ast.Assign]] = {}

    def _should_check(self, rule_id: str) -> bool:
        """Check if a rule should be applied."""
        if rule_id in self.ignored_rules:
            return False
        if self.selected_rules is not None and rule_id not in self.selected_rules:
            return False
        return True

    def _add_finding(self, rule_id: str, node: ast.AST, confidence_reason: str = "") -> None:
        """Add a finding for the given rule and AST node."""
        rule = get_rule(rule_id)
        if rule is None:
            return
        
        # Generate confidence reason if not provided
        if not confidence_reason:
            confidence_reason = self._generate_confidence_reason(rule_id, node)
        
        self.findings.append(Finding(
            rule_id=rule.rule_id,
            message=rule.message,
            path=self.path,
            line=getattr(node, "lineno", 1),
            col=getattr(node, "col_offset", 0),
            severity=rule.severity,
            suggested_fix=rule.suggested_fix,
            confidence=rule.confidence,
            confidence_reason=confidence_reason,
        ))

    def _generate_confidence_reason(self, rule_id: str, node: ast.AST) -> str:
        """Generate a confidence reason based on the detection context."""
        in_loop = "inside loop" if self._in_loop() else "at module level"
        reasons = {
            "PPO001": f"iterrows()/itertuples() detected {in_loop}",
            "PPO002": f"apply(axis=1) pattern {in_loop}",
            "PPO003": f"concat/append {in_loop} — O(n²) pattern",
            "PPO004": "chained subscript assignment df[x][y] = val",
            "PPO005": f"reset_index/set_index {in_loop}",
            "PPO006": ".values attribute access detected",
            "PPO007": "groupby().apply() pattern detected",
            "PPO008": f"string method on subscript {in_loop}",
            "PPO009": f"groupby() {in_loop} — likely invariant",
            "PPO010": f"sort_values() {in_loop} — O(n log n) per iteration",
        }
        return reasons.get(rule_id, f"AST pattern match for {rule_id}")

    def _in_loop(self) -> bool:
        """Check if we're currently inside a loop."""
        return len(self._loop_stack) > 0

    # =========================================================================
    # Loop context tracking
    # =========================================================================
    def visit_For(self, node: ast.For) -> None:
        # PPO001: Check if iterating over iterrows/itertuples
        if self._should_check("PPO001"):
            if isinstance(node.iter, ast.Call):
                if isinstance(node.iter.func, ast.Attribute):
                    if node.iter.func.attr in ("iterrows", "itertuples"):
                        self._add_finding("PPO001", node.iter)

        # Enter loop context
        self._loop_stack.append(node)
        self.generic_visit(node)
        self._loop_stack.pop()

    def visit_While(self, node: ast.While) -> None:
        # Enter loop context
        self._loop_stack.append(node)
        self.generic_visit(node)
        self._loop_stack.pop()

    # =========================================================================
    # PPO002: apply(axis=1)
    # =========================================================================
    def visit_Call(self, node: ast.Call) -> None:
        # PPO002: Check for df.apply(..., axis=1)
        if self._should_check("PPO002"):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "apply":
                for kw in node.keywords:
                    if kw.arg == "axis":
                        # Check if axis=1 (row-wise)
                        if isinstance(kw.value, ast.Constant) and kw.value.value == 1:
                            self._add_finding("PPO002", node)
                            break
                        # Also check for axis='columns' (equivalent to axis=1)
                        if isinstance(kw.value, ast.Constant) and kw.value.value == "columns":
                            self._add_finding("PPO002", node)
                            break

        # PPO003: Check for concat/append in loop
        if self._should_check("PPO003") and self._in_loop():
            # Check for pd.concat() or concat()
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "concat":
                    self._add_finding("PPO003", node)
                elif node.func.attr == "append":
                    # df.append() is deprecated but still used
                    self._add_finding("PPO003", node)
            elif isinstance(node.func, ast.Name) and node.func.id == "concat":
                self._add_finding("PPO003", node)

        # PPO005: Check for reset_index/set_index in loop
        if self._should_check("PPO005") and self._in_loop():
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("reset_index", "set_index"):
                    self._add_finding("PPO005", node)

        # PPO007: Check for groupby().apply()
        if self._should_check("PPO007"):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "apply":
                # Check if this is a chained call on groupby()
                if isinstance(node.func.value, ast.Call):
                    if isinstance(node.func.value.func, ast.Attribute):
                        if node.func.value.func.attr == "groupby":
                            self._add_finding("PPO007", node)

        # PPO009: Check for groupby() inside loops
        if self._should_check("PPO009") and self._in_loop():
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "groupby":
                    self._add_finding("PPO009", node)
            elif isinstance(node.func, ast.Name) and node.func.id == "groupby":
                self._add_finding("PPO009", node)

        # PPO010: Check for sort_values() inside loops
        if self._should_check("PPO010") and self._in_loop():
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ("sort_values", "sort_index"):
                    self._add_finding("PPO010", node)

        self.generic_visit(node)

    # =========================================================================
    # PPO004: Chained indexing assignment
    # =========================================================================
    def visit_Assign(self, node: ast.Assign) -> None:
        if self._should_check("PPO004"):
            for target in node.targets:
                # Look for pattern: df[...][...] = value
                # This is: Subscript(value=Subscript(...))
                if isinstance(target, ast.Subscript):
                    if isinstance(target.value, ast.Subscript):
                        self._add_finding("PPO004", target)

        self.generic_visit(node)

    # =========================================================================
    # PPO006: df.values deprecation
    # =========================================================================
    def visit_Attribute(self, node: ast.Attribute) -> None:
        # PPO006: Check for .values access
        if self._should_check("PPO006"):
            if node.attr == "values":
                # Only flag if it looks like DataFrame/Series access
                # We can't do type inference, but we can check common patterns
                self._add_finding("PPO006", node)

        # PPO008: Check for string methods in loop (e.g., row['col'].lower())
        if self._should_check("PPO008") and self._in_loop():
            # Check for common string methods called on potential Series elements
            string_methods = {
                "lower", "upper", "strip", "lstrip", "rstrip",
                "replace", "split", "join", "find", "rfind",
                "startswith", "endswith", "contains", "match",
                "capitalize", "title", "swapcase", "center",
                "ljust", "rjust", "zfill", "encode", "decode",
            }
            if node.attr in string_methods:
                # Check if this is being called on a subscript (row['col'])
                if isinstance(node.value, ast.Subscript):
                    self._add_finding("PPO008", node)

        self.generic_visit(node)


def analyze_source(
    source: str,
    path: str = "<memory>",
    selected_rules: set[str] | None = None,
    ignored_rules: set[str] | None = None,
) -> list[Finding]:
    """Analyze Python source code for pandas performance anti-patterns.

    Args:
        source: Python source code to analyze
        path: File path for reporting
        selected_rules: If set, only check these rules (e.g., {"PPO001", "PPO002"})
        ignored_rules: Rules to skip (e.g., {"PPO005"})

    Returns:
        List of findings sorted by (path, line, col, rule_id)
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    visitor = PandasPerfVisitor(path, selected_rules, ignored_rules)
    visitor.visit(tree)

    # Sort findings for deterministic output
    return sorted(
        visitor.findings,
        key=lambda f: (f.path, f.line, f.col, f.rule_id)
    )


def analyze_source_with_errors(
    source: str,
    path: str = "<memory>",
    selected_rules: set[str] | None = None,
    ignored_rules: set[str] | None = None,
) -> tuple[list[Finding], ParseError | None]:
    """Analyze Python source code, returning findings and any parse error.

    Returns:
        Tuple of (findings, parse_error). Parse error is None if parsing succeeded.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        parse_error = ParseError(
            path=path,
            line=e.lineno or 1,
            col=e.offset or 0,
            message=str(e.msg) if e.msg else "Syntax error",
        )
        return [], parse_error

    visitor = PandasPerfVisitor(path, selected_rules, ignored_rules)
    visitor.visit(tree)

    # Sort findings for deterministic output
    sorted_findings = sorted(
        visitor.findings,
        key=lambda f: (f.path, f.line, f.col, f.rule_id)
    )
    return sorted_findings, None


def analyze_file(
    file_path: Path,
    selected_rules: set[str] | None = None,
    ignored_rules: set[str] | None = None,
) -> list[Finding]:
    """Analyze a Python file for pandas performance anti-patterns."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    return analyze_source(source, str(file_path), selected_rules, ignored_rules)


def analyze_file_with_errors(
    file_path: Path,
    selected_rules: set[str] | None = None,
    ignored_rules: set[str] | None = None,
) -> tuple[list[Finding], ParseError | None]:
    """Analyze a Python file, returning findings and any parse error."""
    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        parse_error = ParseError(
            path=str(file_path),
            line=1,
            col=0,
            message=f"Could not read file: {e}",
        )
        return [], parse_error

    return analyze_source_with_errors(source, str(file_path), selected_rules, ignored_rules)


def analyze_path(
    root: Path,
    selected_rules: set[str] | None = None,
    ignored_rules: set[str] | None = None,
) -> Iterator[Finding]:
    """Analyze a file or directory recursively.

    Yields findings as they are discovered.
    """
    if root.is_file() and root.suffix == ".py":
        yield from analyze_file(root, selected_rules, ignored_rules)
    elif root.is_dir():
        for py_file in root.rglob("*.py"):
            yield from analyze_file(py_file, selected_rules, ignored_rules)


def analyze_path_with_errors(
    root: Path,
    selected_rules: set[str] | None = None,
    ignored_rules: set[str] | None = None,
) -> AnalysisResult:
    """Analyze a file or directory recursively, tracking parse errors.

    Returns:
        AnalysisResult containing all findings and any parse errors.
    """
    result = AnalysisResult()

    if root.is_file() and root.suffix == ".py":
        files = [root]
    elif root.is_dir():
        files = list(root.rglob("*.py"))
    else:
        files = []

    for py_file in files:
        findings, parse_error = analyze_file_with_errors(py_file, selected_rules, ignored_rules)
        result.findings.extend(findings)
        if parse_error:
            result.parse_errors.append(parse_error)

    # Sort findings for deterministic output
    result.findings.sort(key=lambda f: (f.path, f.line, f.col, f.rule_id))
    result.parse_errors.sort(key=lambda e: e.path)

    return result

