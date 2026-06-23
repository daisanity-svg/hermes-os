.PHONY: help test lint fmt run build clean

help:
	@echo "Hermes OS make targets:"
	@echo "  make test    - run pytest"
	@echo "  make lint    - run static checks"
	@echo "  make fmt     - format source code"
	@echo "  make run     - run the CLI runner"
	@echo "  make build   - build wheel/sdist"
	@echo "  make clean   - clean build/test artifacts"

test:
	python -m pytest tests/ -q

lint:
	@python -m py_compile src/hermes_os/**/*.py tests/**/*.py
	@python -m py_compile scripts/*.py

fmt:
	@echo "Use ruff/black in this repo if configured."

run:
	PYTHONPATH=src python -m hermes_os --help

build:
	python -m build

clean:
	rm -rf .venv dist build .pytest_cache **/__pycache__ **/*.pyc
