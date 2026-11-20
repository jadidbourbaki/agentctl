run *args:
    uv run agent-energy {{args}}

fmt:
    uv run ruff format

lint:
    uv run ruff check

typecheck:
    uv run --extra react ty check

check:
    uv run ruff format --check
    uv run ruff check
    uv run --extra react ty check
    uv run --extra react pytest
