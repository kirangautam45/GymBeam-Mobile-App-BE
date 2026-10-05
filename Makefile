PY := .venv/bin/python

.PHONY: dev dev-lan start test migrate lint install

dev:
	$(PY) -m fastapi dev app/main.py

# Reachable from phones and emulators on the same network
dev-lan:
	$(PY) -m fastapi dev app/main.py --host 0.0.0.0

start:
	$(PY) -m fastapi run app/main.py

test:
	$(PY) -m pytest

migrate:
	$(PY) -m alembic upgrade head

lint:
	$(PY) -m ruff check . && $(PY) -m ruff format .

install:
	python3.12 -m venv .venv
	$(PY) -m pip install -e ".[dev]"
