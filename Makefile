# SkynetClaw — common tasks.
#
#   make install    create .venv and install dependencies
#   make setup      install + create config from templates + init the database
#   make run        start the backend
#   make test       run the backend test suite
#   make health     probe a running instance
#   make clean      remove caches and the virtualenv (keeps your config and data)
#
# Windows users without make: use install.bat / start.bat, or the commands in README.

PYTHON  ?= python3
VENV    ?= .venv
BIN     := $(VENV)/bin
HOST    ?= 127.0.0.1
PORT    ?= 8766

# On Windows the venv layout differs.
ifeq ($(OS),Windows_NT)
  BIN := $(VENV)/Scripts
  PYTHON ?= python
endif

.PHONY: help install setup config db run test health lint clean

help:
	@echo "SkynetClaw"
	@echo "  make setup    one-time: venv + deps + config + database"
	@echo "  make run      start the backend on $(HOST):$(PORT)"
	@echo "  make test     run the test suite"
	@echo "  make health   probe a running instance"

$(VENV):
	$(PYTHON) -m venv $(VENV)

install: $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/pip install -r backend/requirements.txt

config:
	@test -f backend/settings.json || (cp backend/settings.example.json backend/settings.json && \
	  echo "created backend/settings.json — edit it to choose your model")
	@test -f .env || (test -f .env.example && cp .env.example .env && echo "created .env") || true

db:
	cd backend && ../$(BIN)/python migrate.py up

setup: install config db
	@echo
	@echo "Setup complete. Next: make run"

run:
	cd backend && ../$(BIN)/python -m uvicorn main:app --host $(HOST) --port $(PORT)

test:
	cd backend && ../$(BIN)/python -m pytest -q

health:
	@curl -sf http://$(HOST):$(PORT)/api/system/health || \
	  echo "no response — is the server running? (make run)"

clean:
	rm -rf $(VENV)
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	@echo "removed caches and the virtualenv (config and databases were kept)"
