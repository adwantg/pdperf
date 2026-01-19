"""Rule definitions for pdperf.

Each rule is a dataclass with metadata and detection logic.

Author: gadwant
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """Severity levels for findings."""
    WARN = "warn"
    ERROR = "error"


class Confidence(str, Enum):
    """Confidence levels for rule detection accuracy.
    
    - HIGH: Structural AST pattern match, very precise
    - MEDIUM: Heuristic-based, some false positives possible
    - LOW: Suggestion-only, requires human judgment
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class Rule:
    """Rule metadata and documentation."""
    rule_id: str
    name: str
    severity: Severity
    message: str
    suggested_fix: str
    confidence: Confidence = Confidence.HIGH  # Default to high confidence
    docs_url: str | None = None
    explanation: str | None = None  # Extended explanation for `pdperf explain`
    patchable: bool = False  # Whether this rule supports auto-patching

    def __str__(self) -> str:
        return f"{self.rule_id}: {self.name}"


# Rule Registry
RULES: dict[str, Rule] = {}


def register_rule(rule: Rule) -> Rule:
    """Register a rule in the global registry."""
    RULES[rule.rule_id] = rule
    return rule


# =============================================================================
# PPO001: iterrows / itertuples in loops
# =============================================================================
PPO001 = register_rule(Rule(
    rule_id="PPO001",
    name="iterrows/itertuples loop",
    severity=Severity.WARN,
    message="Avoid df.iterrows() or df.itertuples() in loops; prefer vectorized operations.",
    suggested_fix="Use vectorized column operations like df['a'] + df['b'], or np.where(), merge(), map(), groupby().agg().",
    docs_url="https://pandas.pydata.org/docs/user_guide/enhancingperf.html",
    explanation="""
## Why iterrows() is slow

`iterrows()` is extremely slow because:
1. **Python interpreter overhead**: Each row iteration invokes the Python interpreter
2. **Series object creation**: Each row is converted to a pandas Series object
3. **Type conversion**: Data types may be converted during iteration
4. **No vectorization**: Cannot leverage NumPy's C-optimized operations

### Performance comparison

```python
# SLOW: ~100x slower for large DataFrames
for idx, row in df.iterrows():
    result.append(row['a'] * row['b'])

# FAST: Vectorized operation
result = df['a'] * df['b']
```

### When iteration is necessary

If you truly need row-by-row processing:
1. Use `df.itertuples()` (10x faster than iterrows)
2. Use `df.to_numpy()` and iterate over arrays
3. Consider `numba` JIT compilation for complex logic
""",
))

# =============================================================================
# PPO002: apply(axis=1) row-wise operations
# =============================================================================
PPO002 = register_rule(Rule(
    rule_id="PPO002",
    name="apply(axis=1) row-wise",
    severity=Severity.WARN,
    message="Row-wise df.apply(axis=1) is slow; prefer vectorized operations.",
    suggested_fix="Replace with df['x'] + df['y'], np.where(condition, a, b), Series.map(), or merge().",
    docs_url="https://pandas.pydata.org/docs/user_guide/enhancingperf.html",
    explanation="""
## Why apply(axis=1) is slow

`df.apply(func, axis=1)` processes one row at a time, invoking Python for each row.

### Common patterns and their vectorized alternatives

| Pattern | Slow (apply) | Fast (vectorized) |
|---------|--------------|-------------------|
| Arithmetic | `df.apply(lambda r: r['a'] + r['b'], axis=1)` | `df['a'] + df['b']` |
| Conditionals | `df.apply(lambda r: 'yes' if r['x'] > 0 else 'no', axis=1)` | `np.where(df['x'] > 0, 'yes', 'no')` |
| Multiple conditions | Custom function with if/elif | `np.select([cond1, cond2], [val1, val2], default)` |
| Lookups | `df.apply(lambda r: mapping[r['key']], axis=1)` | `df['key'].map(mapping)` |

### Performance impact

Row-wise apply is typically 10-100x slower than vectorized operations.
""",
))

# =============================================================================
# PPO003: append/concat in loop (O(n²) pattern)
# =============================================================================
PPO003 = register_rule(Rule(
    rule_id="PPO003",
    name="concat/append in loop",
    severity=Severity.ERROR,
    message="Building DataFrame via append/concat in a loop is O(n²); accumulate in a list first.",
    suggested_fix="Collect DataFrames in a list, then call pd.concat(frames, ignore_index=True) once after the loop.",
    docs_url="https://pandas.pydata.org/docs/reference/api/pandas.concat.html",
    explanation="""
## Why concat/append in a loop is O(n²)

Each `pd.concat()` or `df.append()` creates a new DataFrame by copying all existing data.
After n iterations, you've copied: 1 + 2 + 3 + ... + n = O(n²) rows.

### The scaling problem

| Rows (n) | Concat in loop | List + single concat |
|----------|----------------|---------------------|
| 1,000 | ~0.5s | ~0.01s |
| 10,000 | ~50s | ~0.1s |
| 100,000 | ~1.4 hours | ~1s |

### The fix

```python
# SLOW: O(n²)
df = pd.DataFrame()
for chunk in chunks:
    df = pd.concat([df, chunk])

# FAST: O(n)
frames = []
for chunk in chunks:
    frames.append(chunk)
df = pd.concat(frames, ignore_index=True)

# EVEN FASTER: List comprehension
df = pd.concat([process(chunk) for chunk in chunks], ignore_index=True)
```
""",
))

# =============================================================================
# PPO004: chained indexing assignment
# =============================================================================
PPO004 = register_rule(Rule(
    rule_id="PPO004",
    name="chained indexing assignment",
    severity=Severity.ERROR,
    message="Chained indexing df[mask]['col'] = val may assign to a copy, causing silent bugs and poor performance.",
    suggested_fix="Use .loc[mask, 'col'] = val for correct and efficient assignment.",
    docs_url="https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html#returning-a-view-versus-a-copy",
    patchable=True,  # This rule supports auto-patching
    explanation="""
## Why chained indexing is dangerous

`df[mask]['col'] = value` performs two separate operations:
1. `df[mask]` returns a copy OR a view (unpredictable!)
2. `['col'] = value` assigns to whatever step 1 returned

If step 1 returned a copy, your assignment is lost silently.

### The SettingWithCopyWarning

Pandas tries to warn you, but the warning is often missed or ignored.
The correct pattern is always `.loc[]`:

```python
# WRONG: May assign to a copy
df[df['a'] > 0]['b'] = 10

# CORRECT: Always works
df.loc[df['a'] > 0, 'b'] = 10
```

### Performance benefit

`.loc[]` is also faster because it's a single operation instead of two.
""",
))

# =============================================================================
# PPO005: reset_index/set_index churn in loops
# =============================================================================
PPO005 = register_rule(Rule(
    rule_id="PPO005",
    name="index churn in loop",
    severity=Severity.WARN,
    message="Repeated reset_index()/set_index() inside a loop is inefficient.",
    suggested_fix="Move index operations outside the loop, or avoid unnecessary index mutations.",
    docs_url="https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.reset_index.html",
    explanation="""
## Why index churn is wasteful

`reset_index()` and `set_index()` create new DataFrame copies with modified indexes.
Doing this inside a loop multiplies the overhead.

### Common anti-pattern

```python
# SLOW: Index rebuilt every iteration
for group_key in keys:
    df = df.reset_index()  # Unnecessary!
    df = df.set_index('col')  # Also unnecessary!
    # ... do work ...
```

### The fix

Move index operations outside the loop, or avoid them entirely if not needed:

```python
# FAST: Set index once
df = df.set_index('col')
for group_key in keys:
    # ... do work without index changes ...
```
""",
))

# =============================================================================
# PPO006: df.values — prefer .to_numpy()
# =============================================================================
PPO006 = register_rule(Rule(
    rule_id="PPO006",
    name="Avoid .values; prefer .to_numpy()",
    severity=Severity.WARN,
    message="Avoid .values; prefer .to_numpy() for explicit array conversion with consistent return type.",
    suggested_fix="Replace df.values with df.to_numpy() for clearer intent and consistent behavior.",
    docs_url="https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_numpy.html",
    patchable=True,
    explanation="""
## Why .values is discouraged

`.values` has inconsistent return types depending on the DataFrame's dtypes:
- Sometimes returns a NumPy ndarray
- Sometimes returns a pandas ExtensionArray (e.g., for nullable dtypes)

`.to_numpy()` is explicit and provides control:
- Always returns a NumPy array
- Optional `dtype` and `copy` parameters
- Clearer intent in code

### The fix

```python
# DISCOURAGED: Inconsistent return type
arr = df.values
arr = df['col'].values

# RECOMMENDED: Explicit conversion
arr = df.to_numpy()
arr = df['col'].to_numpy()

# With explicit dtype
arr = df.to_numpy(dtype='float64', copy=False)
```

Note: Ruff rule PD011 also flags this pattern.
""",
))

# =============================================================================
# PPO007: unoptimized groupby().apply()
# =============================================================================
PPO007 = register_rule(Rule(
    rule_id="PPO007",
    name="unoptimized groupby().apply()",
    severity=Severity.WARN,
    message="groupby().apply() with a custom function is slow; prefer built-in aggregations or transform().",
    suggested_fix="Use groupby().agg(), groupby().transform(), or built-in methods like sum(), mean(), etc.",
    docs_url="https://pandas.pydata.org/docs/user_guide/groupby.html",
    explanation="""
## Why groupby().apply() is slow

`apply()` invokes Python for each group, losing vectorization benefits.

### Faster alternatives

| Use case | Slow | Fast |
|----------|------|------|
| Single aggregation | `groupby().apply(lambda g: g['x'].sum())` | `groupby()['x'].sum()` |
| Multiple aggregations | Custom function | `groupby().agg({'x': 'sum', 'y': 'mean'})` |
| Per-group transform | `apply(lambda g: g - g.mean())` | `groupby().transform(lambda x: x - x.mean())` |
| Named aggregations | Custom function | `groupby().agg(total=('x', 'sum'))` |

### When apply() is necessary

Use `apply()` only when you need access to the entire group DataFrame
for complex operations that can't be expressed with agg/transform.
""",
))

# =============================================================================
# PPO008: string operations in loops
# =============================================================================
PPO008 = register_rule(Rule(
    rule_id="PPO008",
    name="string ops in loop",
    severity=Severity.WARN,
    message="String operations on Series should use vectorized .str accessor, not loops.",
    suggested_fix="Use df['col'].str.contains(), .str.replace(), .str.lower(), etc. instead of looping.",
    docs_url="https://pandas.pydata.org/docs/user_guide/text.html",
    explanation="""
## Why loop string operations are slow

Looping over rows to process strings invokes Python's string methods one at a time.

### Vectorized string methods

Pandas provides the `.str` accessor for vectorized string operations:

```python
# SLOW: Loop
for i, row in df.iterrows():
    df.at[i, 'col'] = row['col'].lower()

# FAST: Vectorized
df['col'] = df['col'].str.lower()
```

### Common .str methods

- `.str.lower()`, `.str.upper()`, `.str.title()`
- `.str.contains()`, `.str.startswith()`, `.str.endswith()`
- `.str.replace()`, `.str.extract()`, `.str.split()`
- `.str.len()`, `.str.strip()`, `.str.pad()`
""",
))


# =============================================================================
# PPO009: groupby() with same keys repeated in loop
# =============================================================================
PPO009 = register_rule(Rule(
    rule_id="PPO009",
    name="groupby in loop",
    severity=Severity.WARN,
    message="groupby() inside a loop is expensive; the grouping is often invariant across iterations.",
    suggested_fix="Hoist groupby() outside the loop if the grouping keys don't change per iteration.",
    confidence=Confidence.HIGH,
    docs_url="https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.groupby.html",
    explanation="""
## Why groupby() in a loop is slow

`groupby()` performs significant work:
1. Computes group indices
2. Creates group mappings
3. Sorts or hashes the data

If you call it inside a loop with the same keys, you're repeating all this work.

### The anti-pattern

```python
# SLOW: groupby called N times
for threshold in thresholds:
    groups = df.groupby("category")
    for name, group in groups:
        # ... process ...
```

### The fix

```python
# FAST: groupby called once
groups = df.groupby("category")
for threshold in thresholds:
    for name, group in groups:
        # ... process ...
```

### Performance impact

| Iterations | In-loop groupby | Hoisted groupby |
|------------|-----------------|-----------------|
| 10 | ~10x overhead | 1x (baseline) |
| 100 | ~100x overhead | 1x (baseline) |
| 1000 | ~1000x overhead | 1x (baseline) |
""",
))


# =============================================================================
# PPO010: sort_values() inside loops
# =============================================================================
PPO010 = register_rule(Rule(
    rule_id="PPO010",
    name="sort_values in loop",
    severity=Severity.WARN,
    message="sort_values() inside a loop is O(n log n) per iteration; consider hoisting or avoiding.",
    suggested_fix="Sort once outside the loop, or restructure to avoid repeated sorting.",
    confidence=Confidence.HIGH,
    docs_url="https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.sort_values.html",
    explanation="""
## Why sort_values() in a loop is catastrophic

Sorting is O(n log n). Inside a loop of m iterations, you get O(m × n log n).

### The anti-pattern

```python
# SLOW: Sorting 1000 times
for key in keys:
    df = df.sort_values("timestamp")
    # ... process ...
```

### Common fixes

```python
# OPTION 1: Sort once before the loop
df = df.sort_values("timestamp")
for key in keys:
    # ... process (no re-sorting) ...

# OPTION 2: Maintain a sorted index
df = df.set_index("timestamp").sort_index()

# OPTION 3: Use nsmallest/nlargest for top-k
top_10 = df.nsmallest(10, "value")  # Faster than full sort
```

### Performance impact

| Rows | 1 sort | 100 sorts in loop |
|------|--------|-------------------|
| 10K | 2ms | 200ms |
| 100K | 25ms | 2.5s |
| 1M | 300ms | 30s |
""",
))


def get_rule(rule_id: str) -> Rule | None:
    """Get a rule by its ID."""
    return RULES.get(rule_id)


def list_rules() -> list[Rule]:
    """Return all registered rules in sorted order."""
    return sorted(RULES.values(), key=lambda r: r.rule_id)


