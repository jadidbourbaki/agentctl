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

The recording shows Claude Code pause mid-task and resume with the same PID.

https://github.com/user-attachments/assets/98d4b150-b696-4f9b-a828-546651cae063

With [Claude Code](https://code.claude.com/docs/en/overview) installed and
configured, open its interactive UI in your terminal.

```sh
agentctl run --tty claude
```

Ask Claude to read the runner modules and explain how suspension works.
In a second terminal pane, list active runs and find the Claude Code run.

```sh
agentctl list
```

Suspend Claude Code. Replace RUN_ID with the ID from the table.

```sh
agentctl suspend RUN_ID
```

Resume the same process group. Claude Code keeps its session and terminal.

```sh
agentctl resume RUN_ID
```

Terminal runs keep input and output in the terminal. Exit Claude Code to
return to the shell.

## Headless Claude Code

The review recipe streams events from Claude Code as it reads the runner
source.

```sh
agentctl run -n claude just claude-review
```

Use jq to follow the tool calls and final report. Press Ctrl+C to close
the log view.

```sh
just review-log RUN_ID
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

Commands inherit the caller's working directory and environment. Headless
commands get an empty standard input stream. agentctl saves their logs and
exit codes. A host restart ends live runs. Child processes that create
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
