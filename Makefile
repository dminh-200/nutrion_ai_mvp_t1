.PHONY: setup init-db import-food seed ingest mcp-dev run test test-fast test-mcp eval eval-rag check-rules lint

PYTHON := .venv/Scripts/python
PYTEST := .venv/Scripts/pytest
RUFF := .venv/Scripts/ruff
MCP := .venv/Scripts/mcp

setup:
	python -m pip install -r requirements.txt

init-db:
	$(PYTHON) -m db.init_db

import-food:
	$(PYTHON) -m db.import_food

seed:
	$(PYTHON) -m db.seed_patients

ingest:
	$(PYTHON) -m rag.ingest

mcp-dev:
	$(MCP) dev mcp_server/server.py --with-editable .

run:
	$(PYTHON) -m streamlit run app/main.py

test:
	$(PYTHON) -m pytest -q -m "not slow"

test-fast:
	$(PYTHON) -m pytest -q -m "not slow and not mcp"

test-mcp:
	$(PYTHON) -m pytest -q -m mcp

eval:
	$(PYTHON) -m evals.run_eval

eval-rag:
	$(PYTHON) -m evals.rag_eval

check-rules:
	$(PYTHON) -m scripts.check_rules

lint:
	$(RUFF) check .
