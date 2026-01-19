"""Example: Slow code using iterrows - PPO001 anti-pattern.

This demonstrates the performance cost of using iterrows() for row iteration.
ppopt will flag this with: PPO001 - Avoid df.iterrows() or df.itertuples() in loops
"""

import pandas as pd


def slow_sum_products(path: str) -> float:
    """Calculate sum of units * price using iterrows (SLOW).
    
    This is O(n) but with very high constant factor due to:
    - Python interpreter overhead per row
    - Series object creation for each row
    - No vectorization benefits
    """
    df = pd.read_csv(path)
    total = 0.0
    for _, row in df.iterrows():  # PPO001: This triggers a warning!
        total += row["units"] * row["price"]
    return total


def fast_sum_products(path: str) -> float:
    """Calculate sum of units * price using vectorized operations (FAST).
    
    This is ~100x faster for large datasets because:
    - Operations happen in optimized C code (NumPy)
    - No Python interpreter overhead per element
    - CPU cache-friendly memory access patterns
    """
    df = pd.read_csv(path)
    return (df["units"] * df["price"]).sum()


if __name__ == "__main__":
    # Example usage
    import timeit
    
    path = "../datasets/sales_small.csv"
    
    # Verify both produce same result
    slow_result = slow_sum_products(path)
    fast_result = fast_sum_products(path)
    print(f"Slow result: {slow_result}")
    print(f"Fast result: {fast_result}")
    print(f"Results match: {abs(slow_result - fast_result) < 0.01}")
    
    # Benchmark
    print("\nBenchmark (1000 runs):")
    slow_time = timeit.timeit(lambda: slow_sum_products(path), number=100)
    fast_time = timeit.timeit(lambda: fast_sum_products(path), number=100)
    print(f"Slow (iterrows): {slow_time:.3f}s")
    print(f"Fast (vectorized): {fast_time:.3f}s")
    print(f"Speedup: {slow_time / fast_time:.1f}x")
