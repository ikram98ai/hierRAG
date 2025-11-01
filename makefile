sync:
	uv sync

lint:
	uv run ruff check

fix:
	uv run ruff check --fix

format:
	uv run ruff format

dev: 
	uv run gradio src/app.py

test: 
	uv run pytest tests

deps:
	uv pip compile pyproject.toml -o hierRAG/requirements.txt