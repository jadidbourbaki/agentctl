# Agent Runner

Agent Runner starts a local command and gives it a run ID. You can suspend
the command and its child processes, resume them, and read their output.
The runner supports macOS and Linux.

## Setup

Install Python 3.13 or newer, [uv](https://docs.astral.sh/uv/), and
[just](https://just.systems/). From the repository root, install the runner
and the development tools.

```sh
just setup
```

List the available recipes.

```sh
just
```

## Process control

Start a five-minute test process and save its run ID. You can pass any
executable and its arguments to the start recipe. Pass a Python file
directly to use the runner's Python interpreter, or supply an explicit
interpreter for a script with its own environment.

```sh
run_id=$(just start sleep 300)
```

Check the run's state and process ID. The exit code is null while the
process is alive.

```sh
just status "$run_id"
```

Suspend the process group. The processes stay in memory.

```sh
just suspend "$run_id"
```

Resume the same process group.

```sh
just resume "$run_id"
```

Read the command's standard output and standard error. The sleep example
produces no output.

```sh
just logs "$run_id"
```

Terminate the run. The runner gives the process group three seconds to
handle SIGTERM before sending SIGKILL.

```sh
just stop "$run_id"
```

Commands inherit the caller's working directory and environment. The runner
closes standard input and keeps the output and exit code after the command
exits. Runs end when the host restarts. Child processes that create their own
process groups manage their own lifecycles.

The runner stores logs and exit codes in the agent-runner directory under
XDG_STATE_HOME. The parent defaults to ~/.local/state. Set
AGENT_RUNNER_STATE_DIR to choose another directory.

## ReAct example

Install [llama-server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
and choose a GGUF model that supports tool calls. Replace the example path
with your model file. The serve recipe exposes the model as local on port
8080 and enables tool calls.

```sh
just serve /path/to/model.gguf
```

From a second terminal, start the [ReAct script](examples/react.py). uv
installs the script's dependencies in a separate environment on its first
run. Pydantic Deep sends your prompt to the model, runs the multiplication
tool when the model requests it, and passes the result back to the model.

```sh
run_id=$(OPENAI_BASE_URL=http://127.0.0.1:8080/v1 OPENAI_API_KEY=local \
  just react local 'Use the multiplication tool to compute 37 times 61.')
```

Read the log after the run exits. The answer should include 2257.

```sh
just logs "$run_id"
```

For vLLM, SGLang, or Orla, use the model name served by the endpoint and
configure the variables below. Enable the model server's tool-call parser
if the server requires one. Suspending the local agent leaves the inference
server free to finish requests it already received.

| Environment variable | Default | Purpose |
| --- | --- | --- |
| OPENAI_BASE_URL | http://127.0.0.1:8080/v1 | OpenAI-compatible chat API base URL. |
| OPENAI_API_KEY | local | API key sent to the model server. |

## Development checks

Run the formatter check, lint, type checker, and lifecycle tests.

```sh
just check
```
