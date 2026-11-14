.PHONY: setup init-db seed ingest mcp-dev run test eval lint

PYTHON := .venv/Scripts/python
PYTEST := .venv/Scripts/pytest
RUFF := .venv/Scripts/ruff
MCP := .venv/Scripts/mcp

setup:
	python -m pip install -r requirements.txt

init-db:
	$(PYTHON) -m db.init_db

seed:
	$(PYTHON) -m db.seed_patients

ingest:
	$(PYTHON) -m rag.ingest

mcp-dev:
	$(MCP) dev mcp_server/server.py --with-editable .

run:
	$(PYTHON) -m streamlit run app/main.py

test:
	.venv/Scripts/python.exe -m pytest -q -m "not slow"

eval:
	$(PYTHON) -m evals.run_eval

lint:
	$(RUFF) check .
