.PHONY: install run-collector simulate transform analyze dashboard test lint clean

# Python environment
PYTHON := python
PIP := pip

install:
	$(PIP) install -r requirements.txt

# Event collector
run-collector:
	$(PYTHON) -m uvicorn src.collector.app:app --reload --port 8000

# User simulator
simulate:
	$(PYTHON) -m src.simulator.generate

# dbt transformations
transform:
	cd dbt && dbt run

# Experiment analysis
analyze:
	$(PYTHON) -m src.analysis.run

# Dashboard
dashboard:
	$(PYTHON) -m http.server 8080 --directory src/dashboard

# Testing
test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check src/ tests/

# Cleanup
clean:
	rm -f data/*.duckdb
	rm -rf dbt/target dbt/logs
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
