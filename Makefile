.PHONY: install run lint format test build check update-rates

install:
	uv sync --locked

run:
	uv run project

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --select I --fix .
	uv run ruff format .

test:
	uv run python -m unittest discover -s tests -v

build:
	uv build

check: lint test

update-rates:
	uv run python -m valutatrade_hub.parser_service.scheduler --once
