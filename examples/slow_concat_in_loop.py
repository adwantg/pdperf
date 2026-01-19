"""Example: Slow code using concat in loop - PPO003 anti-pattern.

This demonstrates the O(n²) performance problem of growing DataFrames in loops.
pdperf will flag this with: PPO003 - Building DataFrame via append/concat in a loop is O(n²)
"""

import pandas as pd
import numpy as np


def slow_build_dataframe(n: int) -> pd.DataFrame:
    """Build a DataFrame by concatenating in a loop (SLOW - O(n²)).
    
    Each concat copies the entire existing DataFrame plus the new row,
    leading to:
    - 1 + 2 + 3 + ... + n = O(n²) total copy operations
    - Continuously growing memory allocations
    - GC pressure from discarded intermediate DataFrames
    """
    df = pd.DataFrame()
    for i in range(n):
        row = pd.DataFrame({"id": [i], "value": [np.random.randn()]})
        df = pd.concat([df, row])  # PPO003: This triggers an ERROR!
    return df


def slow_build_with_append(n: int) -> pd.DataFrame:
    """Build a DataFrame using deprecated append (SLOW - O(n²)).
    
    Same O(n²) problem as concat in loop.
    Note: append() is deprecated in pandas >= 1.4.0
    """
    df = pd.DataFrame(columns=["id", "value"])
    for i in range(n):
        df = df.append({"id": i, "value": np.random.randn()}, ignore_index=True)  # PPO003
    return df


def fast_build_dataframe(n: int) -> pd.DataFrame:
    """Build a DataFrame by collecting in a list first (FAST - O(n)).
    
    This is the correct pattern:
    1. Collect all data in a Python list (O(1) amortized append)
    2. Create DataFrame once at the end (O(n) single allocation)
    
    Total: O(n) instead of O(n²)
    """
    rows = []
    for i in range(n):
        rows.append({"id": i, "value": np.random.randn()})
    return pd.DataFrame(rows)


def fast_build_from_arrays(n: int) -> pd.DataFrame:
    """Build a DataFrame from pre-allocated arrays (FASTEST).
    
    If you know the size upfront, pre-allocating is even faster.
    """
    ids = np.arange(n)
    values = np.random.randn(n)
    return pd.DataFrame({"id": ids, "value": values})


if __name__ == "__main__":
    import timeit
    
    n = 1000  # Use smaller n for demo since slow version is O(n²)
    
    # Verify correctness (shapes should match)
    slow_df = slow_build_dataframe(n)
    fast_df = fast_build_dataframe(n)
    fastest_df = fast_build_from_arrays(n)
    
    print(f"All have {n} rows: {len(slow_df) == len(fast_df) == len(fastest_df) == n}")
    
    # Benchmark
    print(f"\nBenchmark for n={n}:")
    
    slow_time = timeit.timeit(lambda: slow_build_dataframe(n), number=10)
    fast_time = timeit.timeit(lambda: fast_build_dataframe(n), number=10)
    fastest_time = timeit.timeit(lambda: fast_build_from_arrays(n), number=10)
    
    print(f"Slow (concat in loop): {slow_time:.3f}s")
    print(f"Fast (list + concat):  {fast_time:.3f}s  ({slow_time/fast_time:.1f}x speedup)")
    print(f"Fastest (arrays):      {fastest_time:.3f}s  ({slow_time/fastest_time:.1f}x speedup)")
    
    # Show scaling
    print("\n⚠️  The slow version gets MUCH worse as n grows:")
    print("    n=1000  → ~0.5s")
    print("    n=10000 → ~50s (100x slower, not 10x!)")
    print("    n=100000 → ~5000s = 1.4 hours")
