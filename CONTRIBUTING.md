# Contributing to pdperf

Thank you for your interest in contributing to pdperf! This document provides guidelines for contributing.

## Development Setup

### Prerequisites
- Python 3.10+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/adwantg/pdperf.git
cd pdperf

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_rules.py
```

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists in [GitHub Issues](https://github.com/adwantg/pdperf/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Minimal code example that reproduces the issue
   - Expected vs actual behavior
   - Python and pdperf versions

### Suggesting New Rules

We welcome suggestions for new rules! Please open an issue with:
- Description of the anti-pattern
- Code example (slow vs fast version)
- Why it's a performance problem
- Suggested rule ID (e.g., PPO011)

### Submitting Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Commit with a clear message: `git commit -m "Add PPO011: description"`
6. Push to your fork: `git push origin feature/my-feature`
7. Open a Pull Request

### Adding a New Rule

1. **Define the rule** in `src/pandas_perf_opt/rules.py`:
   ```python
   PPO011 = register_rule(Rule(
       rule_id="PPO011",
       name="your-rule-name",
       severity=Severity.WARN,  # or ERROR
       message="...",
       suggested_fix="...",
       confidence=Confidence.HIGH,  # HIGH, MEDIUM, or LOW
       explanation="...",  # Detailed markdown explanation
   ))
   ```

2. **Add detection logic** in `src/pandas_perf_opt/analyzer.py`:
   ```python
   # In the appropriate visit_* method
   if self._should_check("PPO011"):
       if your_detection_logic(node):
           self._add_finding("PPO011", node)
   ```

3. **Add tests** in `tests/test_rules.py`:
   ```python
   class TestPPO011YourRule:
       def test_detects_pattern(self):
           code = '''...'''
           findings = analyze_source(code, "test.py")
           assert len([f for f in findings if f.rule_id == "PPO011"]) == 1
       
       def test_no_false_positive(self):
           code = '''...'''
           findings = analyze_source(code, "test.py")
           assert len([f for f in findings if f.rule_id == "PPO011"]) == 0
   ```

4. **Update README.md** with rule documentation

## Code Style

- We use Python type hints throughout
- Follow PEP 8 guidelines
- Pre-commit hooks enforce formatting

## Architecture Overview

```
src/pandas_perf_opt/
├── __init__.py      # Version and exports
├── analyzer.py      # AST parsing, visitor, findings
├── cli.py           # Command-line interface
├── config.py        # Configuration and profiles
├── reporting.py     # Output formatting (text, JSON, SARIF)
└── rules.py         # Rule definitions and registry
```

See the [Technical Deep-Dive](README.md#-how-pdperf-works--technical-deep-dive) in the README for more details.

## Questions?

Open an issue or start a discussion on GitHub!
