"""Configuration loading from pyproject.toml.

Provides project-level configuration for pdperf.

Author: gadwant
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore


@dataclass
class Config:
    """pdperf configuration loaded from pyproject.toml."""
    select: set[str] = field(default_factory=set)
    ignore: set[str] = field(default_factory=set)
    severity_threshold: str = "warn"
    fail_on: str = "error"
    format: str = "text"
    min_confidence: str = "low"  # Accept all by default
    profile: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        select = set(data.get("select", []))
        ignore = set(data.get("ignore", []))
        return cls(
            select=select,
            ignore=ignore,
            severity_threshold=data.get("severity_threshold", "warn"),
            fail_on=data.get("fail_on", "error"),
            format=data.get("format", "text"),
            min_confidence=data.get("min_confidence", "low"),
            profile=data.get("profile"),
        )


def load_config(path: Path | None = None) -> Config:
    """Load configuration from pyproject.toml.

    Args:
        path: Path to pyproject.toml. If None, searches from cwd upward.

    Returns:
        Config object with merged settings.
    """
    if path is None:
        path = find_pyproject_toml()

    if path is None or not path.exists():
        return Config()

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return Config()

    pdperf_config = data.get("tool", {}).get("pdperf", {})
    return Config.from_dict(pdperf_config)


def find_pyproject_toml() -> Path | None:
    """Find pyproject.toml by searching from cwd upward."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            return pyproject
    return None


# =============================================================================
# Rule Profiles
# =============================================================================

PROFILES: dict[str, dict[str, Any]] = {
    "etl": {
        "description": "Optimized for ETL pipelines — strict on performance-critical patterns",
        "select": ["PPO001", "PPO002", "PPO003", "PPO004", "PPO005", "PPO009", "PPO010"],
        "severity_threshold": "warn",
        "fail_on": "error",
    },
    "notebook": {
        "description": "Balanced for notebooks — warnings without blocking",
        "select": ["PPO001", "PPO002", "PPO003", "PPO004", "PPO006", "PPO007", "PPO008"],
        "ignore": ["PPO005"],  # Index churn less critical in notebooks
        "severity_threshold": "warn",
        "fail_on": "none",
    },
}


def get_profile(name: str) -> dict[str, Any] | None:
    """Get a profile by name."""
    return PROFILES.get(name)


def list_profiles() -> list[str]:
    """List available profile names."""
    return sorted(PROFILES.keys())


def apply_profile(config: Config, profile_name: str) -> Config:
    """Apply a profile to a config, merging settings."""
    profile = get_profile(profile_name)
    if profile is None:
        return config

    # Profile settings override config, but CLI overrides profile
    select = config.select or set(profile.get("select", []))
    ignore = config.ignore | set(profile.get("ignore", []))

    return Config(
        select=select,
        ignore=ignore,
        severity_threshold=config.severity_threshold or profile.get("severity_threshold", "warn"),
        fail_on=config.fail_on or profile.get("fail_on", "error"),
        format=config.format,
        min_confidence=config.min_confidence,
        profile=profile_name,
    )
