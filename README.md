# Agent Energy

Agent Energy admits a local command, gives it a run ID, and lets you suspend
and resume the same live process. Use it to compare when agents run while
keeping inference on an existing model server.

## Run a command

Install [uv](https://docs.astral.sh/uv/), then run from the repository root.
The runner uses Python 3.13 or newer.

```sh
uv sync
run=$(uv run agent-energy start -- ./my-agent --prompt "Summarize this file")
uv run agent-energy status "$run"
uv run agent-energy suspend "$run"
uv run agent-energy resume "$run"
uv run agent-energy logs "$run"
uv run agent-energy stop "$run"
```

Pass a Python script with `start -- /path/to/agent.py arg`. The runner uses
its Python interpreter for a bare `.py` file. Pass an explicit interpreter or
another environment's command when the agent needs its own dependencies.
The command inherits the caller's working directory and environment.
Each run reads from closed standard input and writes combined output to its log.

Runs continue after the start command returns. Run logs and final return codes
live under `${XDG_STATE_HOME:-$HOME/.local/state}/agent-energy`. Set
`AGENT_ENERGY_STATE_DIR` to choose a different directory.

On macOS and Linux, each run gets its own process group. Suspend keeps the
group in memory and resume continues it with the same PID. Stop sends
`SIGTERM`, wakes a suspended group so it can handle the signal, and gives it
three seconds before forcing exit. The run ends when its original command
exits, and the supervisor cleans up processes still in the group. Commands
that daemonize into another process group manage those processes themselves.

A remote inference request can continue on the model server while the local
agent is suspended. Suspend at a tool or request boundary if the experiment
requires inference to be idle. A host restart ends live runs.

## ReAct example

Start [llama-server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
with a tool-capable GGUF model.

```sh
llama-server -m /path/to/model.gguf --alias local --jinja \
  --host 127.0.0.1 --port 8080 --api-key local
```

In another terminal, start a run and inspect its output.

```sh
uv sync --extra react
run=$(uv run --extra react agent-energy start -- agent-react \
  --base-url http://127.0.0.1:8080/v1 --model local \
  "Use the multiplication tool to compute 37 times 61.")
uv run --extra react agent-energy status "$run"
uv run --extra react agent-energy logs "$run"
```

Pydantic AI handles the model, tool call, tool result, and final response.
The example uses a single multiplication tool and allows up to eight model
requests. Use `--base-url` or `OPENAI_BASE_URL` to point it at vLLM, SGLang,
Orla, or another OpenAI-compatible chat endpoint. Use the server's model name
and enable its tool-call parser where required. Set `OPENAI_API_KEY` when the
endpoint requires credentials.

Run `just check` for formatting, lint, type checks, and lifecycle tests.
