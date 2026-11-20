set positional-arguments

# List recipes.
default:
    @just --list

# Install the runner and development tools.
setup:
    uv sync --locked

# Run the CLI with arbitrary arguments.
run *args:
    @uv run --locked --no-sync agent-runner "$@"

# Start a command and print its run ID.
start command *args:
    @uv run --locked --no-sync agent-runner start -- "$@"

# Show the run state, PID, and exit code.
status id:
    @uv run --locked --no-sync agent-runner status "$1"

# Suspend the process group.
suspend id:
    @uv run --locked --no-sync agent-runner suspend "$1"

# Resume the process group.
resume id:
    @uv run --locked --no-sync agent-runner resume "$1"

# Print the run output.
logs id:
    @uv run --locked --no-sync agent-runner logs "$1"

# Terminate the process group.
stop id:
    @uv run --locked --no-sync agent-runner stop "$1"

# Serve a GGUF model on loopback with the model name local.
serve gguf:
    llama-server --model "$1" --alias local --jinja --host 127.0.0.1 --port 8080 --api-key local

# Start a ReAct run and print its run ID.
react model prompt:
    @uv run --locked --no-sync agent-runner start -- uv run --locked --script examples/react.py --model "$1" -- "$2"

fmt:
    uv run --locked --no-sync ruff format

lint:
    uv run --locked --no-sync ruff check

typecheck:
    uv run --locked --no-sync ty check src tests
    uv sync --locked --script examples/react.py
    uv run --locked --no-sync ty check --python "$(uv python find --script examples/react.py)" examples/react.py

test:
    uv run --locked --no-sync pytest

check: lint typecheck test
    uv run --locked --no-sync ruff format --check
