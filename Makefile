.PHONY: setup init-db seed ingest mcp-dev run test eval lint

PYTHON := .venv/Scripts/python
PYTEST := .venv/Scripts/pytest
RUFF := .venv/Scripts/ruff

setup:
	python -m pip install -r requirements.txt

init-db:
	$(PYTHON) -m db.init_db

seed:
	$(PYTHON) -m db.seed_patients

ingest:
	$(PYTHON) -m rag.ingest

mcp-dev:
	$(PYTHON) -m mcp.cli dev mcp_server/server.py

run:
	$(PYTHON) -m streamlit run app/main.py

test:
	$(PYTEST) -q -m "not slow"

eval:
	$(PYTHON) -m evals.run_eval

lint:
	$(RUFF) check .
