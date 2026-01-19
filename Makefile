.PHONY: dev test demo bench fmt

dev:
	python -m pip install -U pip
	python -m pip install -e .

test:
	python -m pytest -q

demo:
	python -m pandas_perf_opt.cli --version

bench:
	@echo "TODO: add benchmarks"

fmt:
	@echo "Optional: add ruff/black later"
