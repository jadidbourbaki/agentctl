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

# List active runs. Pass --all to include history.
list *args:
    @uv run --locked --no-sync agentctl list "$@"

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

# Run a read-only Claude Code walkthrough with live events.
claude-review:
    @claude --safe-mode --print --output-format stream-json --verbose --no-session-persistence --strict-mcp-config --tools Read --allowedTools Read --system-prompt "You are a read-only source reviewer. Read only the requested files and rely on the results." -- "Read README.md, src/agentctl/cli.py, and src/agentctl/supervisor.py in separate tool calls. Explain how agentctl discovers runs and pauses and resumes a process group. Cite the functions you read. Answer in at most 100 words."

# Follow the Claude Code walkthrough as readable text. Requires jq.
review-log id:
    @agentctl logs --follow "$1" | jq -Rr --unbuffered -f examples/claude-log.jq

fmt:
    uv run --locked --no-sync ruff format

lint:
    uv run --locked --no-sync ruff check

typecheck:
    uv run --locked --no-sync ty check src tests

test:
    uv run --locked --no-sync pytest

check: lint typecheck test
    uv run --locked --no-sync ruff format --check
