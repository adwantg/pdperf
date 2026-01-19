"""Example: Slow code using apply(axis=1) - PPO002 anti-pattern.

This demonstrates the performance cost of row-wise apply operations.
ppopt will flag this with: PPO002 - Row-wise df.apply(axis=1) is slow
"""

import pandas as pd
import numpy as np


def slow_conditional_column(df: pd.DataFrame) -> pd.Series:
    """Add a category column using apply(axis=1) (SLOW).
    
    This applies a Python function row-by-row, which is:
    - ~100x slower than vectorized operations
    - Memory inefficient (creates intermediate objects)
    """
    def categorize(row):
        if row["value"] > 100:
            return "high"
        elif row["value"] > 50:
            return "medium"
        else:
            return "low"
    
    return df.apply(categorize, axis=1)  # PPO002: This triggers a warning!


def fast_conditional_column(df: pd.DataFrame) -> pd.Series:
    """Add a category column using np.select (FAST).
    
    Vectorized conditional logic using NumPy is:
    - ~100x faster
    - Memory efficient
    - More readable for complex conditions
    """
    conditions = [
        df["value"] > 100,
        df["value"] > 50,
    ]
    choices = ["high", "medium"]
    return pd.Series(np.select(conditions, choices, default="low"), index=df.index)


def slow_row_calculation(df: pd.DataFrame) -> pd.Series:
    """Calculate derived column using apply(axis=1) (SLOW)."""
    return df.apply(lambda row: row["a"] * 2 + row["b"] ** 2, axis=1)  # PPO002


def fast_row_calculation(df: pd.DataFrame) -> pd.Series:
    """Calculate derived column using vectorized ops (FAST)."""
    return df["a"] * 2 + df["b"] ** 2


if __name__ == "__main__":
    import timeit
    
    # Create test data
    n = 10000
    df = pd.DataFrame({
        "value": np.random.randint(0, 150, n),
        "a": np.random.randn(n),
        "b": np.random.randn(n),
    })
    
    # Verify correctness
    slow = slow_conditional_column(df)
    fast = fast_conditional_column(df)
    print(f"Conditional results match: {(slow == fast).all()}")
    
    slow_calc = slow_row_calculation(df)
    fast_calc = fast_row_calculation(df)
    print(f"Calculation results match: {np.allclose(slow_calc, fast_calc)}")
    
    # Benchmark
    print("\nBenchmark (100 runs each):")
    
    slow_time = timeit.timeit(lambda: slow_conditional_column(df), number=100)
    fast_time = timeit.timeit(lambda: fast_conditional_column(df), number=100)
    print(f"Conditional - Slow (apply): {slow_time:.3f}s")
    print(f"Conditional - Fast (np.select): {fast_time:.3f}s")
    print(f"Speedup: {slow_time / fast_time:.1f}x")
    
    slow_time = timeit.timeit(lambda: slow_row_calculation(df), number=100)
    fast_time = timeit.timeit(lambda: fast_row_calculation(df), number=100)
    print(f"\nCalculation - Slow (apply): {slow_time:.3f}s")
    print(f"Calculation - Fast (vectorized): {fast_time:.3f}s")
    print(f"Speedup: {slow_time / fast_time:.1f}x")
