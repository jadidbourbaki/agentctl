# agentctl

agentctl starts local commands and lets you suspend and resume them by run ID.
It runs on macOS and Linux with Python 3.13 or newer.

## Install

Install [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).
From the repository root, install agentctl on your PATH.

```sh
just install
```

## Incident demo

Start [llama-server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
with a tool-capable GGUF model. Replace the example path with your model
file. The serve recipe exposes the model as local on port 8080.

```sh
just serve /path/to/model.gguf
```

From a second terminal, start the Pydantic Deep agent and save its run ID.
The agent investigates a simulated checkout slowdown by reading deployment,
latency, and error feeds.

```sh
run=$(agentctl run just incident)
```

Print the run ID so you can use it in another pane.

```sh
echo "$run"
```

In a third terminal or split pane, replace RUN_ID with the printed value.
The terminal UI shows the run state, PID, and agent output as it arrives.

```sh
just watch RUN_ID
```

In the second terminal, suspend the group while the agent reads a feed.
The output stops updating and the terminal UI shows SUSPENDED.

```sh
agentctl suspend "$run"
```

Resume the group. The agent keeps its PID and continues through the
remaining feeds. The final report gives the impact, likely cause, and
next action.

```sh
agentctl resume "$run"
```

For vLLM, SGLang, or Orla, set OPENAI_BASE_URL to the chat API base URL and
OPENAI_API_KEY if the server requires credentials. Pass the served model
name to the incident recipe. The example defaults to local and uses the
same endpoint for every model call.

## Process control

Pass any non-interactive command and its arguments to agentctl. Pass a Python
file directly to use agentctl's interpreter, or pass an explicit interpreter
to use a different environment.

```sh
run=$(agentctl run sleep 300)
```

Read the state, process ID, and exit code. The exit code is null while
the process is alive.

```sh
agentctl status "$run"
```

Read the combined standard output and standard error.

```sh
agentctl logs "$run"
```

Terminate the group. agentctl gives it three seconds to handle SIGTERM
before sending SIGKILL.

```sh
agentctl stop "$run"
```

Commands inherit the caller's working directory and environment. agentctl
gives commands an empty standard input stream and keeps their logs and exit
codes after exit. A host restart ends live runs. Child processes that create
their own process groups manage their own lifecycles. An inference server can
finish an in-flight request while the local agent is suspended.

agentctl stores run data under the agentctl directory in XDG_STATE_HOME.
The parent defaults to ~/.local/state. Set AGENTCTL_STATE_DIR to use another
directory.

## Development

Install the project and its development tools.

```sh
just setup
```

Run the formatter check, lint, type checker, and tests.

```sh
just check
```
