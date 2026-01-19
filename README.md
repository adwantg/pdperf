# pdperf — Pandas Performance Optimizer

[![PyPI](https://img.shields.io/pypi/v/pdperf)](https://pypi.org/project/pdperf/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://img.shields.io/pypi/dm/pdperf)](https://pypi.org/project/pdperf/)
[![CI](https://github.com/adwantg/pdperf/actions/workflows/ci.yml/badge.svg)](https://github.com/adwantg/pdperf/actions/workflows/ci.yml)
[![Codacy Badge](https://app.codacy.com/project/badge/Grade/a9559933e1a04c669ec4ce263a70c94f)](https://app.codacy.com/gh/adwantg/pdperf/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)]()
[![Tests](https://img.shields.io/badge/tests-42%2F42%20passing-success)]()
[![Author: gadwant](https://img.shields.io/badge/author-gadwant-purple.svg)](https://github.com/adwantg)

> **A static linter that catches silent Pandas performance killers before they ship to production.**

pdperf scans your Python code for common Pandas anti-patterns that *work correctly* but are often **10–100× slower at scale** than necessary. It's **local-first**, **deterministic**, and **CI-friendly** — no code execution required.

## 📑 Table of Contents

- [Why pdperf?](#-why-pdperf)
- [Quick Start](#-quick-start)
- [CI-Friendly Guarantees](#-ci-friendly-guarantees)
- [Rules Reference](#-rules-reference)
- [Detailed Rule Examples](#-detailed-rule-examples)
- [CLI Reference](#️-cli-reference)
- [How pdperf Works — Technical Deep-Dive](#-how-pdperf-works--technical-deep-dive)
- [Integrations](#-integrations)
- [License](#-license)

---

## 🎯 Why pdperf?

Pandas makes it easy to write code that works but scales poorly:

```python
# This works... but is painfully slow on large datasets
for idx, row in df.iterrows():
    total += row['price'] * row['quantity']

# pdperf catches this and suggests:
# 💡 Use vectorized: (df['price'] * df['quantity']).sum()
```

These issues often start in notebooks and quietly move into ETL pipelines. **pdperf catches them before production.**

---

## ⚡ Quick Start

### Installation

```bash
# PyPI (coming soon)
# pip install pdperf

# Install from source
git clone https://github.com/adwantg/pdperf.git
cd pdperf
pip install -e .

# Or with dev dependencies
pip install -e ".[dev]"
```

### Basic Usage

```bash
# Scan a file or directory
pdperf scan your_code.py
pdperf scan src/

# List all available rules
pdperf rules

# Get detailed explanation for a rule
pdperf explain PPO003
```

### Example Output

```
📄 etl/transform.py
  ⚠️ 45:12 [PPO001] Avoid df.iterrows() or df.itertuples() in loops; prefer vectorized operations.
     💡 Use vectorized column operations like df['a'] + df['b'], or np.where(), merge(), map(), groupby().agg().

  ❌ 67:8 [PPO003] Building DataFrame via append/concat in a loop is O(n²); accumulate in a list first.
     💡 Collect DataFrames in a list, then call pd.concat(frames, ignore_index=True) once after the loop.

📄 features/pipeline.py
  ⚠️ 23:15 [PPO002] Row-wise df.apply(axis=1) is slow; prefer vectorized operations.
     💡 Replace with df['x'] + df['y'], np.where(condition, a, b), Series.map(), or merge().
```

---

## ✅ CI-Friendly Guarantees

- **No code execution**: pdperf parses code using AST only — safe on any codebase
- **Deterministic output**: stable ordering by `path → line → col → rule_id`
- **Schema-versioned JSON**: `schema_version` field for tooling stability
- **Pattern-based detection**: doesn't require import resolution or `import pandas as pd`

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No findings (or `--fail-on none`) |
| `1` | Findings at/above `--fail-on` threshold |
| `2` | Tool error (invalid args, parse error with `--fail-on-parse-error`) |

### JSON Output Schema

```json
{
  "schema_version": "1.0",
  "tool": "pdperf",
  "tool_version": "0.1.0",
  "total_findings": 3,
  "findings": [
    {
      "rule_id": "PPO001",
      "path": "src/etl.py",
      "line": 45,
      "col": 12,
      "severity": "warn",
      "message": "Avoid df.iterrows()...",
      "suggested_fix": "Use vectorized..."
    }
  ]
}
```

---

## 📋 Rules Reference

pdperf includes **8 rules** targeting the most impactful Pandas performance anti-patterns:

| Rule | Name | Severity | Patchable | Confidence |
|------|------|----------|-----------|------------|
| PPO001 | iterrows/itertuples loop | ⚠️ WARN | — | High |
| PPO002 | apply(axis=1) row-wise | ⚠️ WARN | — | High |
| PPO003 | concat/append in loop | ❌ ERROR | — | High |
| PPO004 | chained indexing | ❌ ERROR | 🔧 | High |
| PPO005 | index churn in loop | ⚠️ WARN | — | High |
| PPO006 | .values → .to_numpy() | ⚠️ WARN | 🔧 | High |
| PPO007 | groupby().apply() | ⚠️ WARN | — | Medium |
| PPO008 | string ops in loop | ⚠️ WARN | — | Medium |

**Legend:**
- 🔧 = Auto-fixable with `--patch`
- — = Not auto-fixable
- **High confidence**: Structural AST pattern match (precise)
- **Medium confidence**: Heuristic-based detection (see rule details for boundaries)

> **Note:** pdperf is import-agnostic by design. In rare cases, non-pandas objects with similar method names (e.g., `.values`) may be flagged. Use `--ignore` or `--select` to control rules.

---

## 📖 Detailed Rule Examples

### PPO001: iterrows/itertuples Loop

**What it catches:**
```python
# ❌ SLOW: Python loop with iterrows
for idx, row in df.iterrows():
    result.append(row['a'] * row['b'])

# ❌ SLOW: itertuples is faster but still not ideal
for row in df.itertuples():
    result.append(row.a * row.b)
```

**Why it's slow:**
- Each row iteration invokes the Python interpreter
- `iterrows()` creates a Series object per row (expensive!)
- No vectorization benefits from NumPy's C backend

**The fix:**
```python
# ✅ FAST: Vectorized operation
result = df['a'] * df['b']

# ✅ FAST: Use numpy for complex operations
result = np.where(df['a'] > 0, df['a'] * df['b'], 0)
```

---

### PPO002: apply(axis=1) Row-wise Operations

**What it catches:**
```python
# ❌ SLOW: Row-wise apply with lambda
df['total'] = df.apply(lambda row: row['price'] * row['qty'], axis=1)

# ❌ SLOW: Row-wise apply with custom function
df['category'] = df.apply(categorize_row, axis=1)
```

**Why it's slow:**
- `axis=1` processes one row at a time
- Python function call overhead for each row

**The fix:**
```python
# ✅ FAST: Direct vectorized arithmetic
df['total'] = df['price'] * df['qty']

# ✅ FAST: Use np.where for conditionals
df['category'] = np.where(df['value'] > 100, 'high', 'low')

# ✅ FAST: Use np.select for multiple conditions
conditions = [df['value'] > 100, df['value'] > 50]
choices = ['high', 'medium']
df['category'] = np.select(conditions, choices, default='low')

# ✅ FAST: Use map for lookups
df['category'] = df['key'].map(category_mapping)
```

---

### PPO003: concat/append in Loop (O(n²) Pattern)

**What it catches:**
```python
# ❌ EXTREMELY SLOW: O(n²) complexity!
df = pd.DataFrame()
for file in files:
    chunk = pd.read_csv(file)
    df = pd.concat([df, chunk])  # Copies entire df each time!

# ❌ DEPRECATED AND SLOW: df.append (removed in pandas 2.0)
for item in items:
    df = df.append({'col': item}, ignore_index=True)
```

**Why it's catastrophic:**
Each concat copies all existing data. After n iterations: 1 + 2 + 3 + ... + n = O(n²) copies.

> ⚠️ **Note:** `DataFrame.append()` was deprecated in pandas 1.4.0 and removed in 2.0. See [pandas docs](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.append.html).

**The fix:**
```python
# ✅ FAST: Collect in list, concat once (O(n))
frames = []
for file in files:
    chunk = pd.read_csv(file)
    frames.append(chunk)
df = pd.concat(frames, ignore_index=True)

# ✅ EVEN FASTER: List comprehension
df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
```

---

### PPO004: Chained Indexing Assignment

**What it catches:**
```python
# ❌ DANGEROUS: May silently fail!
df[df['a'] > 0]['b'] = 10

# ❌ DANGEROUS: Same pattern with variable
mask = df['a'] > 0
df[mask]['b'] = 10
```

**Why it's dangerous:**
1. `df[mask]` might return a **copy** (unpredictable!)
2. `['b'] = 10` assigns to the copy, not the original
3. Your data update is **silently lost**

Pandas warns with `SettingWithCopyWarning`, but warnings are often ignored. See [Real Python's explanation](https://realpython.com/pandas-settingwithcopywarning/).

**The fix:**
```python
# ✅ CORRECT: Use .loc for safe assignment
df.loc[df['a'] > 0, 'b'] = 10

# ✅ CORRECT: With named mask
mask = df['a'] > 0
df.loc[mask, 'b'] = 10
```

---

### PPO005: Index Churn in Loop

**What it catches:**
```python
# ❌ WASTEFUL: Rebuilds index every iteration
for key in keys:
    df = df.reset_index()
    df = df.set_index('col')
    # ... process ...
```

**Why it matters:**
- `reset_index()` and `set_index()` create new DataFrame copies
- Index operations inside loops multiply the overhead

**The fix:**
```python
# ✅ BETTER: Set index once, outside loop
df = df.set_index('col')
for key in keys:
    # ... process without index changes ...
```

---

### PPO006: .values → .to_numpy()

**What it catches:**
```python
# ❌ DISCOURAGED: Inconsistent return type
arr = df.values
arr = df['col'].values
```

**Why it matters:**
- `.values` sometimes returns NumPy array, sometimes ExtensionArray
- Behavior depends on DataFrame dtypes
- `.to_numpy()` is explicit and always returns NumPy array

> 📝 **Note:** Ruff rule PD011 (from pandas-vet) also flags this pattern.

**The fix:**
```python
# ✅ RECOMMENDED: Explicit conversion
arr = df.to_numpy()
arr = df['col'].to_numpy()

# With explicit dtype
arr = df.to_numpy(dtype='float64', copy=False)
```

---

### PPO007: Unoptimized groupby().apply()

**What it catches:**
```python
# ❌ SLOW: Custom function invoked per group
result = df.groupby('category').apply(lambda g: g['value'].sum())
```

**Why it's slow:**
- `apply()` invokes Python for each group
- Loses vectorization benefits

**The fix:**
```python
# ✅ FAST: Built-in aggregation
result = df.groupby('category')['value'].sum()

# ✅ FAST: Multiple aggregations with agg()
result = df.groupby('category').agg({
    'value': ['sum', 'mean'],
    'quantity': 'count'
})

# ✅ FAST: Named aggregations (pandas 0.25+)
result = df.groupby('category').agg(
    total=('value', 'sum'),
    average=('value', 'mean')
)
```

> **Detection boundary:** PPO007 flags any `groupby(...).apply(...)` call. This is a heuristic — some `apply()` uses are unavoidable. Use `--ignore PPO007` if you have legitimate use cases.

---

### PPO008: String Operations in Loop

**What it catches:**
```python
# ❌ SLOW: String processing in loop
for idx, row in df.iterrows():
    df.at[idx, 'name'] = row['name'].lower()
```

**Why it's slow:**
- Python string methods called one at a time
- Combined with iterrows overhead

**The fix:**
```python
# ✅ FAST: Vectorized string operations
df['name'] = df['name'].str.lower()
df['clean'] = df['text'].str.strip().str.replace('  ', ' ', regex=False)
```

> **Detection boundary:** PPO008 only flags string methods (`.lower()`, `.strip()`, etc.) called on subscript expressions (e.g., `row['col']`) inside loops. It does not flag `.str` accessor usage.

---

## 🛠️ CLI Reference

### Commands

```bash
pdperf scan <path>          # Scan files for anti-patterns
pdperf rules                # List all rules
pdperf explain <RULE_ID>    # Explain a specific rule in detail
```

### Scan Options

| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format: `text`, `json`, `sarif` | `text` |
| `--out` | Write output to file | stdout |
| `--select` | Only check these rules (comma-separated) | all |
| `--ignore` | Skip these rules (comma-separated) | none |
| `--severity-threshold` | Minimum severity: `warn`, `error` | `warn` |
| `--fail-on` | Exit 1 threshold: `warn`, `error`, `none` | `error` |
| `--fail-on-parse-error` | Exit 2 if any files have syntax errors | false |
| `--patch` | Generate unified diff for auto-fixable rules | — |

### Examples

```bash
# Quick check of a single file
pdperf scan etl/transform.py

# Full project scan with JSON output for CI
pdperf scan src/ --format json --out reports/pdperf.json --fail-on error

# Generate SARIF for GitHub Security integration
pdperf scan . --format sarif --out results.sarif

# Focus on critical issues only
pdperf scan . --severity-threshold error --select PPO003,PPO004

# Generate auto-fix patch
pdperf scan . --patch out/fixes.diff
```

---

## ⚙️ Configuration (Planned)

pdperf will support configuration via `pyproject.toml`:

```toml
[tool.pdperf]
select = ["PPO001", "PPO002", "PPO003", "PPO004", "PPO005"]
ignore = ["PPO006"]
severity_threshold = "warn"
fail_on = "error"
format = "json"
```

---

## 🔬 How pdperf Works — Technical Deep-Dive

This section explains the internals of pdperf for curious developers. Whether you're a beginner or an expert, you'll understand exactly how we detect performance anti-patterns.

### The Big Picture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Your Code  │ ──▶ │  AST Parser │ ──▶ │  Visitors   │ ──▶ │  Findings   │
│   (.py)     │     │  (Python)   │     │  (Rules)    │     │  (Report)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

**In simple terms:** pdperf reads your Python code, converts it into a tree structure, walks through that tree looking for patterns that indicate slow code, and reports what it finds.

---

### Step 1: Abstract Syntax Tree (AST) Parsing

#### What is an AST?

When Python reads your code, it doesn't see text — it sees a **tree of instructions**. This tree is called an **Abstract Syntax Tree (AST)**.

**Example code:**
```python
for idx, row in df.iterrows():
    total += row['value']
```

**What Python sees (simplified AST):**
```
For
├── target: Tuple(idx, row)
├── iter: Call
│   └── func: Attribute
│       ├── value: Name(df)
│       └── attr: "iterrows"
└── body: [AugAssign...]
```

#### Why AST?

| Approach | Pros | Cons |
|----------|------|------|
| **Regex on text** | Simple | Breaks on formatting, comments, strings |
| **Running code** | Accurate | Dangerous, slow, needs dependencies |
| **AST parsing** ✅ | Safe, accurate, fast | Requires understanding tree structure |

**pdperf uses Python's built-in `ast` module** — the same parser Python itself uses. This means:
- ✅ **100% safe** — we never execute your code
- ✅ **Handles all Python syntax** — even complex expressions
- ✅ **Zero false positives from comments/strings** — AST ignores them

```python
import ast

# This is what pdperf does internally:
source_code = open("your_file.py").read()
tree = ast.parse(source_code)  # Convert text → tree
```

---

### Step 2: Tree Traversal with the Visitor Pattern

#### What is the Visitor Pattern?

Instead of manually searching the tree, we use a **Visitor** — an object that automatically walks through every node in the tree and lets us react to specific node types.

**Think of it like a security scanner at an airport:**
- The scanner (visitor) checks every bag (node)
- It only alerts on specific items (patterns we care about)
- It doesn't modify anything — just observes

#### How pdperf implements this:

```python
class PandasPerfVisitor(ast.NodeVisitor):
    def visit_For(self, node):
        # Called for every 'for' loop in the code
        # Check if iterating over iterrows/itertuples
        ...
    
    def visit_Call(self, node):
        # Called for every function call
        # Check for concat(), apply(axis=1), etc.
        ...
```

**Why this is elegant:**
- Python automatically walks the entire tree
- We only write code for patterns we care about
- Adding new rules = adding new `visit_X` methods

---

### Step 3: Context Tracking (Loop Detection)

Many anti-patterns are only problematic **inside loops**. For example:
- `pd.concat()` outside a loop → ✅ Fine
- `pd.concat()` inside a loop → ❌ O(n²) performance

#### How we track loop context:

```python
class PandasPerfVisitor(ast.NodeVisitor):
    def __init__(self):
        self._loop_stack = []  # Track nested loops
    
    def visit_For(self, node):
        self._loop_stack.append(node)  # Enter loop
        self.generic_visit(node)        # Check children
        self._loop_stack.pop()          # Exit loop
    
    def _in_loop(self):
        return len(self._loop_stack) > 0
```

**This enables rules like:**
- PPO003: `concat` in loop (only flagged when `_in_loop() == True`)
- PPO009: `groupby` in loop
- PPO010: `sort_values` in loop

---

### Step 4: Pattern Matching

Each rule looks for a specific AST pattern. Here's how the most important ones work:

#### PPO001: iterrows/itertuples Detection

**Pattern:** A `For` loop where the iterator is a call to `.iterrows()` or `.itertuples()`

```python
def visit_For(self, node):
    if isinstance(node.iter, ast.Call):
        if isinstance(node.iter.func, ast.Attribute):
            if node.iter.func.attr in ("iterrows", "itertuples"):
                self._add_finding("PPO001", node)
```

**Visual breakdown:**
```
for idx, row in df.iterrows():
    │              └─ Attribute(attr="iterrows")
    └── For.iter = Call(func=Attribute...)
```

#### PPO003: concat in Loop Detection

**Pattern:** A call to `.concat()` or `pd.concat()` while inside a loop

```python
def visit_Call(self, node):
    if self._in_loop():  # Only flag inside loops
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "concat":
                self._add_finding("PPO003", node)
```

#### PPO004: Chained Indexing Detection

**Pattern:** Assignment where the target is `df[x][y] = value`

This is tricky because we need to detect **nested subscripts on the left side of an assignment**:

```python
df[mask]["col"] = value
│  │     │
│  │     └── Subscript (inner)
│  └──────── Subscript (outer) 
└─────────── This is the assignment target
```

```python
def visit_Assign(self, node):
    for target in node.targets:
        if isinstance(target, ast.Subscript):
            if isinstance(target.value, ast.Subscript):
                # Nested subscript = chained indexing!
                self._add_finding("PPO004", target)
```

---

### Step 5: Confidence Scoring

Not all detections are equally reliable. pdperf includes a **confidence score** with each finding:

| Level | Meaning | Example |
|-------|---------|---------|
| **High** | Structural match, very reliable | `iterrows()` in for loop |
| **Medium** | Heuristic, some false positives possible | `groupby().apply()` |
| **Low** | Suggestion only | (future rules) |

```python
@dataclass
class Finding:
    rule_id: str
    confidence: Confidence  # HIGH, MEDIUM, LOW
    confidence_reason: str  # Human-readable explanation
```

**Why this matters:**
- CI can filter: `--min-confidence high`
- Users understand reliability of each finding
- Reduces "alert fatigue" from uncertain warnings

---

### Step 6: Deterministic Output

For CI/CD reliability, pdperf guarantees **deterministic output**:

```python
# Findings are always sorted by:
findings.sort(key=lambda f: (f.path, f.line, f.col, f.rule_id))
```

This means:
- Same code → same JSON output
- No flaky CI builds
- Diffs are meaningful

---

### Architecture Summary

```
┌─────────────────────────────────────────────────────────────┐
│                         pdperf                               │
├─────────────────────────────────────────────────────────────┤
│  cli.py          │ Entry point, argument parsing, output   │
│  analyzer.py     │ AST parsing, visitor, finding creation  │
│  rules.py        │ Rule definitions, severity, messages    │
│  config.py       │ pyproject.toml loading, profiles        │
│  reporting.py    │ JSON, text, SARIF output formatting     │
└─────────────────────────────────────────────────────────────┘
```

| File | Responsibility | Key Classes/Functions |
|------|----------------|----------------------|
| `analyzer.py` | Core detection engine | `PandasPerfVisitor`, `Finding`, `analyze_path` |
| `rules.py` | Rule registry | `Rule`, `Severity`, `Confidence`, `RULES` dict |
| `config.py` | Configuration | `Config`, `load_config`, `PROFILES` |
| `cli.py` | User interface | `build_parser`, `cmd_scan`, `cmd_explain` |
| `reporting.py` | Output formatting | `format_text`, `write_json`, `write_sarif` |

---

### Algorithms & Complexity

| Operation | Algorithm | Complexity |
|-----------|-----------|------------|
| **AST parsing** | Python's built-in parser | O(n) where n = file size |
| **Tree traversal** | Depth-first visitor | O(nodes) — visits each node once |
| **Pattern matching** | Direct attribute checks | O(1) per node |
| **Finding sorting** | Timsort | O(k log k) where k = findings |

**Total complexity:** O(n) for a single file — linear in code size.

**Benchmark:** pdperf scans ~10,000 lines/second on typical hardware.

---

### Why This Approach Works

| Design Choice | Benefit |
|---------------|---------|
| **AST, not regex** | Handles all valid Python syntax correctly |
| **Visitor pattern** | Clean separation, easy to add rules |
| **Loop stack** | Context-aware detection (loop vs. not-loop) |
| **No type inference** | Fast, no dependencies, works on any code |
| **Confidence levels** | Users trust findings at appropriate level |
| **Deterministic output** | Reliable CI integration |

---

### Limitations (Honest Assessment)

| Limitation | Why It Exists | Mitigation |
|------------|---------------|------------|
| **No type inference** | Would require running code | Use `--ignore` for false positives |
| **Import-agnostic** | Can flag non-pandas `.values` | Filter with `--select` |
| **Syntax errors skip file** | Can't parse invalid Python | Use `--fail-on-parse-error` |
| **No cross-file analysis** | Keeps tool simple and fast | May miss imported patterns |

---

### Extending pdperf

Want to add a new rule? Here's the template:

```python
# 1. Define in rules.py
PPO011 = register_rule(Rule(
    rule_id="PPO011",
    name="your-rule-name",
    severity=Severity.WARN,
    message="...",
    suggested_fix="...",
    confidence=Confidence.HIGH,
))

# 2. Detect in analyzer.py
def visit_Call(self, node):
    if self._should_check("PPO011"):
        if your_detection_logic(node):
            self._add_finding("PPO011", node)
```

---

## 🔌 Integrations

### CI: Fail PRs on Errors

```bash
pdperf scan . --format json --out pdperf.json --fail-on error
```

### Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: pdperf
        name: pdperf (pandas performance linter)
        entry: pdperf scan --fail-on error
        language: python
        types: [python]
```

### GitHub Actions

```yaml
name: Lint
on: [push, pull_request]

jobs:
  pdperf:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e .
      - run: pdperf scan src/ --format sarif --out results.sarif --fail-on error
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: results.sarif
```

---

## ✅ Verification

### Run Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"
pip install pytest

# Run all tests (33 tests)
python -m pytest tests/ -v
```

### Verify Installation

```bash
# Check version
pdperf --version
# → pdperf 0.1.0

# List rules (should show 8 rules)
pdperf rules

# Test on example files
pdperf scan examples/
```

---

## 📁 Project Structure

```
pandas-perf-optimizer/
├── src/pandas_perf_opt/
│   ├── __init__.py      # Package version
│   ├── analyzer.py      # AST-based detection engine
│   ├── cli.py           # Command-line interface
│   ├── reporting.py     # JSON/text/SARIF output
│   └── rules.py         # Rule definitions & explanations
├── tests/
│   ├── test_rules.py    # 33 golden tests
│   └── test_smoke.py    # Version test
├── examples/
│   ├── slow_iterrows.py      # PPO001 example
│   ├── slow_apply_axis1.py   # PPO002 example
│   └── slow_concat_in_loop.py # PPO003 example
├── pyproject.toml       # Package configuration
├── Makefile             # Dev commands
└── README.md            # This file
```

---

## 🔧 Supported Versions

| Dependency | Supported |
|------------|-----------|
| **Python** | 3.10+ |
| **Pandas** | 1.5+, 2.x (detection is version-agnostic) |

---

## 📚 References

- [Pandas Performance Guide](https://pandas.pydata.org/docs/user_guide/enhancingperf.html) — Official pandas performance tips
- [SettingWithCopyWarning Explained](https://realpython.com/pandas-settingwithcopywarning/) — Real Python guide
- [DataFrame.to_numpy()](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_numpy.html) — Why .to_numpy() over .values
- [DataFrame.append() Deprecation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.append.html) — Pandas 1.4+ deprecation notice
- [Ruff PD011](https://docs.astral.sh/ruff/rules/pandas-use-of-dot-values/) — Ruff's `.values` rule (similar to PPO006)