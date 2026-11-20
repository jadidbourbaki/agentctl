# agentctl

agentctl starts local commands and lets you list, suspend, and resume them.
It runs on macOS and Linux with Python 3.13 or newer.

## Install

Install [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).
From the repository root, install agentctl on your PATH.

```sh
just install
```

## Claude Code demo

With [Claude Code](https://code.claude.com/docs/en/overview) installed and
configured, start a headless source walkthrough. Claude Code reads the
README and the two runner modules with its Read tool. The name flag labels
the run as claude in the list.

```sh
agentctl run -n claude just claude-review
```

List the active runs. The table shows the run ID, state, PID, and command name.
Use the ID from the table in the commands below.

```sh
agentctl list
```

In another terminal, use jq to follow Claude Code's tool calls and final
report. Press Ctrl+C to close the view.

```sh
just review-log RUN_ID
```

Suspend the run. Replace RUN_ID with the ID from the table.

```sh
agentctl suspend RUN_ID
```

Resume the same process group.

```sh
agentctl resume RUN_ID
```

## Process control

Pass any non-interactive command and its arguments to agentctl. The runner
starts Python files with its own interpreter when you pass a file directly.

```sh
agentctl run sleep 300
```

Include finished runs when you need a recent run's ID.

```sh
agentctl list --all
```

Show the current state, PID, and exit code. The exit code is null while the
process is alive. Lifecycle commands accept the displayed ID or the full run
UUID.

```sh
agentctl status RUN_ID
```

Follow a command's unfiltered output.

```sh
agentctl logs --follow RUN_ID
```

Stop the group. agentctl gives it three seconds to handle SIGTERM before
sending SIGKILL.

```sh
agentctl stop RUN_ID
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
