"""Golden tests for pdperf rules.

Each test case uses inline Python code to verify detection patterns.
"""

from pandas_perf_opt.analyzer import analyze_source
from pandas_perf_opt.rules import Severity


class TestPPO001IterrowsItertuples:
    """Tests for PPO001: iterrows/itertuples in loops."""

    def test_detects_iterrows_in_for_loop(self):
        code = '''
import pandas as pd
df = pd.read_csv("data.csv")
for idx, row in df.iterrows():
    print(row["col"])
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO001"
        assert findings[0].severity == Severity.WARN
        assert "iterrows" in findings[0].message.lower() or "itertuples" in findings[0].message.lower()

    def test_detects_itertuples_in_for_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
for row in df.itertuples():
    print(row.a)
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO001"

    def test_iterrows_outside_loop_not_flagged(self):
        # Just calling iterrows() without a for loop shouldn't trigger
        # (The current implementation only checks inside For loops)
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
iterator = df.iterrows()
'''
        findings = analyze_source(code, "test.py")
        # This case might or might not be flagged depending on implementation
        # Current implementation flags it if used as For.iter
        assert len(findings) == 0  # Not used in a for loop


class TestPPO002ApplyAxis1:
    """Tests for PPO002: apply(axis=1) row-wise operations."""

    def test_detects_apply_axis_1(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
result = df.apply(lambda row: row["a"] + row["b"], axis=1)
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO002"
        assert findings[0].severity == Severity.WARN

    def test_detects_apply_axis_columns(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
result = df.apply(some_func, axis="columns")
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO002"

    def test_apply_axis_0_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
result = df.apply(sum, axis=0)  # Column-wise, this is fine
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 0

    def test_apply_without_axis_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
result = df.apply(sum)  # Default axis=0
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 0


class TestPPO003ConcatAppendInLoop:
    """Tests for PPO003: append/concat in loop (O(n²) pattern)."""

    def test_detects_concat_in_for_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame()
for i in range(10):
    chunk = pd.DataFrame({"a": [i]})
    df = pd.concat([df, chunk])
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO003"
        assert findings[0].severity == Severity.ERROR

    def test_detects_append_in_for_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame()
for i in range(10):
    df = df.append({"a": i}, ignore_index=True)
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO003"

    def test_detects_concat_in_while_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame()
i = 0
while i < 10:
    chunk = pd.DataFrame({"a": [i]})
    df = pd.concat([df, chunk])
    i += 1
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO003"

    def test_concat_outside_loop_not_flagged(self):
        code = '''
import pandas as pd
dfs = [pd.DataFrame({"a": [i]}) for i in range(10)]
result = pd.concat(dfs, ignore_index=True)  # This is the correct pattern!
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 0


class TestPPO004ChainedIndexing:
    """Tests for PPO004: chained indexing assignment."""

    def test_detects_chained_indexing_assignment(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
df[df["a"] > 1]["b"] = 100  # This is the anti-pattern!
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO004"
        assert findings[0].severity == Severity.ERROR

    def test_detects_nested_subscript_assignment(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
mask = df["a"] > 1
df[mask]["b"] = 100
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO004"

    def test_loc_assignment_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
df.loc[df["a"] > 1, "b"] = 100  # Correct pattern!
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 0

    def test_simple_indexing_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
df["b"] = 100  # Single indexing is fine
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 0


class TestPPO005IndexChurnInLoop:
    """Tests for PPO005: reset_index/set_index churn in loops."""

    def test_detects_reset_index_in_for_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
for i in range(10):
    df = df.reset_index()
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO005"
        assert findings[0].severity == Severity.WARN

    def test_detects_set_index_in_while_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
i = 0
while i < 5:
    df = df.set_index("a")
    i += 1
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 1
        assert findings[0].rule_id == "PPO005"

    def test_reset_index_outside_loop_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
df = df.reset_index()  # Outside loop, fine
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) == 0


class TestRuleFiltering:
    """Tests for --select and --ignore functionality."""

    def test_select_filters_to_specified_rules(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
for idx, row in df.iterrows():
    pass
result = df.apply(lambda x: x, axis=1)
'''
        # Select only PPO001
        findings = analyze_source(code, "test.py", selected_rules={"PPO001"})
        assert all(f.rule_id == "PPO001" for f in findings)

    def test_ignore_excludes_specified_rules(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
for idx, row in df.iterrows():
    pass
result = df.apply(lambda x: x, axis=1)
'''
        # Ignore PPO001
        findings = analyze_source(code, "test.py", ignored_rules={"PPO001"})
        assert all(f.rule_id != "PPO001" for f in findings)


class TestMultipleFindings:
    """Tests for code with multiple issues."""

    def test_detects_multiple_different_issues(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})

# PPO001: iterrows
for idx, row in df.iterrows():
    pass

# PPO002: apply axis=1
result = df.apply(lambda x: x["a"] + x["b"], axis=1)

# PPO003: concat in loop
for i in range(5):
    df = pd.concat([df, df])

# PPO004: chained indexing
df[df["a"] > 1]["b"] = 0

# PPO005: reset_index in loop
for i in range(3):
    df = df.reset_index()
'''
        findings = analyze_source(code, "test.py")
        rule_ids = {f.rule_id for f in findings}
        assert "PPO001" in rule_ids
        assert "PPO002" in rule_ids
        assert "PPO003" in rule_ids
        assert "PPO004" in rule_ids
        assert "PPO005" in rule_ids


class TestDeterministicOutput:
    """Tests for deterministic output ordering."""

    def test_findings_are_sorted_by_location(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
result = df.apply(lambda x: x, axis=1)  # Line 4
for idx, row in df.iterrows():  # Line 5
    pass
'''
        findings = analyze_source(code, "test.py")
        # Should be sorted by line number
        lines = [f.line for f in findings]
        assert lines == sorted(lines)


class TestPPO006DfValues:
    """Tests for PPO006: df.values deprecation."""

    def test_detects_df_values(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
arr = df.values
'''
        findings = analyze_source(code, "test.py")
        ppo006_findings = [f for f in findings if f.rule_id == "PPO006"]
        assert len(ppo006_findings) == 1
        assert ppo006_findings[0].severity == Severity.WARN

    def test_detects_series_values(self):
        code = '''
import pandas as pd
s = pd.Series([1, 2, 3])
arr = s.values
'''
        findings = analyze_source(code, "test.py")
        ppo006_findings = [f for f in findings if f.rule_id == "PPO006"]
        assert len(ppo006_findings) == 1

    def test_to_numpy_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
arr = df.to_numpy()
'''
        findings = analyze_source(code, "test.py")
        ppo006_findings = [f for f in findings if f.rule_id == "PPO006"]
        assert len(ppo006_findings) == 0


class TestPPO007GroupbyApply:
    """Tests for PPO007: unoptimized groupby().apply()."""

    def test_detects_groupby_apply(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 1, 2], "b": [1, 2, 3]})
result = df.groupby("a").apply(lambda g: g.sum())
'''
        findings = analyze_source(code, "test.py")
        ppo007_findings = [f for f in findings if f.rule_id == "PPO007"]
        assert len(ppo007_findings) == 1
        assert ppo007_findings[0].severity == Severity.WARN

    def test_groupby_agg_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 1, 2], "b": [1, 2, 3]})
result = df.groupby("a").agg({"b": "sum"})
'''
        findings = analyze_source(code, "test.py")
        ppo007_findings = [f for f in findings if f.rule_id == "PPO007"]
        assert len(ppo007_findings) == 0

    def test_groupby_builtin_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 1, 2], "b": [1, 2, 3]})
result = df.groupby("a").sum()
'''
        findings = analyze_source(code, "test.py")
        ppo007_findings = [f for f in findings if f.rule_id == "PPO007"]
        assert len(ppo007_findings) == 0


class TestPPO008StringOpsInLoop:
    """Tests for PPO008: string operations in loops."""

    def test_detects_string_lower_in_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": ["A", "B", "C"]})
for idx, row in df.iterrows():
    result = row["a"].lower()
'''
        findings = analyze_source(code, "test.py")
        ppo008_findings = [f for f in findings if f.rule_id == "PPO008"]
        assert len(ppo008_findings) == 1
        assert ppo008_findings[0].severity == Severity.WARN

    def test_detects_string_replace_in_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": ["hello", "world"]})
for i in range(len(df)):
    df.iloc[i]["a"].replace("o", "0")
'''
        findings = analyze_source(code, "test.py")
        ppo008_findings = [f for f in findings if f.rule_id == "PPO008"]
        assert len(ppo008_findings) >= 1

    def test_str_accessor_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": ["A", "B", "C"]})
result = df["a"].str.lower()  # Vectorized, correct!
'''
        findings = analyze_source(code, "test.py")
        ppo008_findings = [f for f in findings if f.rule_id == "PPO008"]
        assert len(ppo008_findings) == 0

    def test_string_op_outside_loop_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": ["A", "B", "C"]})
single_value = df.iloc[0]["a"].lower()  # Outside loop, acceptable
'''
        findings = analyze_source(code, "test.py")
        ppo008_findings = [f for f in findings if f.rule_id == "PPO008"]
        assert len(ppo008_findings) == 0


class TestParseErrorHandling:
    """Tests for syntax error detection and reporting."""

    def test_syntax_error_returns_parse_error(self):
        from pandas_perf_opt.analyzer import analyze_source_with_errors
        
        code = '''
import pandas as pd
def broken(
'''  # Missing close paren
        findings, parse_error = analyze_source_with_errors(code, "broken.py")
        assert len(findings) == 0
        assert parse_error is not None
        assert parse_error.path == "broken.py"
        assert parse_error.message  # Has some error message

    def test_valid_code_no_parse_error(self):
        from pandas_perf_opt.analyzer import analyze_source_with_errors
        
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
'''
        findings, parse_error = analyze_source_with_errors(code, "valid.py")
        assert parse_error is None

    def test_analysis_result_tracks_parse_errors(self):
        from pandas_perf_opt.analyzer import AnalysisResult
        
        result = AnalysisResult()
        assert result.findings == []
        assert result.parse_errors == []


class TestPPO009GroupbyInLoop:
    """Tests for PPO009: groupby() inside loops."""

    def test_detects_groupby_in_for_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
for x in range(10):
    groups = df.groupby("a")
'''
        findings = analyze_source(code, "test.py")
        ppo009_findings = [f for f in findings if f.rule_id == "PPO009"]
        assert len(ppo009_findings) == 1

    def test_groupby_outside_loop_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
groups = df.groupby("a")
'''
        findings = analyze_source(code, "test.py")
        ppo009_findings = [f for f in findings if f.rule_id == "PPO009"]
        assert len(ppo009_findings) == 0


class TestPPO010SortValuesInLoop:
    """Tests for PPO010: sort_values() inside loops."""

    def test_detects_sort_values_in_for_loop(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
for x in range(10):
    df = df.sort_values("a")
'''
        findings = analyze_source(code, "test.py")
        ppo010_findings = [f for f in findings if f.rule_id == "PPO010"]
        assert len(ppo010_findings) == 1

    def test_sort_values_outside_loop_not_flagged(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
df = df.sort_values("a")
'''
        findings = analyze_source(code, "test.py")
        ppo010_findings = [f for f in findings if f.rule_id == "PPO010"]
        assert len(ppo010_findings) == 0


class TestConfidenceScoring:
    """Tests for confidence scoring in findings."""

    def test_findings_include_confidence(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
for idx, row in df.iterrows():
    pass
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) >= 1
        assert findings[0].confidence is not None
        assert findings[0].confidence.value in ("high", "medium", "low")

    def test_findings_include_confidence_reason(self):
        code = '''
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3]})
for idx, row in df.iterrows():
    pass
'''
        findings = analyze_source(code, "test.py")
        assert len(findings) >= 1
        assert findings[0].confidence_reason != ""



