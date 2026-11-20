set positional-arguments

# List recipes.
default:
    @just --list

# Install the runner and development tools.
setup:
    uv sync --locked

# Install agentctl on PATH.
install:
    uv tool install .

# Start a command and print its run ID.
run command *args:
    @uv run --locked --no-sync agentctl run -- "$@"

# Show the run state, PID, and exit code.
status id:
    @uv run --locked --no-sync agentctl status "$1"

# Suspend the process group.
suspend id:
    @uv run --locked --no-sync agentctl suspend "$1"

# Resume the process group.
resume id:
    @uv run --locked --no-sync agentctl resume "$1"

# Print the run output.
logs id:
    @uv run --locked --no-sync agentctl logs "$1"

# Terminate the process group.
stop id:
    @uv run --locked --no-sync agentctl stop "$1"

# Serve a GGUF model on loopback with the model name local.
serve gguf:
    llama-server --model "$1" --alias local --jinja --host 127.0.0.1 --port 8080 --api-key local

# Run the Pydantic Deep incident agent.
incident *args:
    @PYDANTIC_AI_NO_BANNER=1 uv run --locked --script examples/incident.py run "$@"

# Watch an incident run.
watch id:
    @uv run --locked --script examples/incident.py watch "$1"

fmt:
    uv run --locked --no-sync ruff format

lint:
    uv run --locked --no-sync ruff check

typecheck:
    uv run --locked --no-sync ty check src tests
    uv sync --locked --script examples/incident.py
    uv run --locked --no-sync ty check --python "$(uv python find --script examples/incident.py)" examples/incident.py

test:
    uv run --locked --no-sync pytest

check: lint typecheck test
    uv run --locked --no-sync ruff format --check
