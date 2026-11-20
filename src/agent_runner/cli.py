"""Start a command or control a run by its ID."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from uuid import UUID, uuid4

from .supervisor import CONTROL, LOG, RESULT


def state_directory() -> Path:
    default = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return Path(os.environ.get("AGENT_RUNNER_STATE_DIR") or default / "agent-runner").resolve()


def start(directory: Path, command: list[str]) -> str:
    run_id = uuid4().hex
    run_directory = directory / run_id
    run_directory.mkdir(mode=0o700, parents=True)
    if command[0].endswith(".py"):
        command = [sys.executable, *command]
    with (run_directory / "supervisor.log").open("wb") as log:
        supervisor = subprocess.Popen(
            [sys.executable, "-m", "agent_runner.supervisor", str(run_directory), *command],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=log,
        )
    assert supervisor.stdout is not None
    with supervisor.stdout as startup:
        if startup.readline() != b"ready\n":
            supervisor.wait()
            raise RuntimeError(f"could not start command. See {run_directory / 'supervisor.log'}")
    return run_id


def request(run_directory: Path, command: str) -> str:
    result = run_directory / RESULT
    if result.exists():
        return result.read_text()

    # Relative socket paths keep the state directory outside the Unix path limit.
    os.chdir(run_directory)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2)
            client.connect(CONTROL)
            client.sendall(command.encode())
            client.shutdown(socket.SHUT_WR)
            with client.makefile() as response:
                status = response.read()
            if status:
                return status
    except (ConnectionError, FileNotFoundError):
        if not result.exists():
            raise RuntimeError(
                f"supervisor unavailable. See {run_directory / 'supervisor.log'}"
            ) from None
    return result.read_text()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    launch = actions.add_parser("start", help="start a command and print its run ID")
    launch.add_argument("command", nargs=argparse.REMAINDER)
    for action in ("status", "suspend", "resume", "stop", "logs"):
        actions.add_parser(action).add_argument("run_id", type=UUID)
    args = parser.parse_args()
    directory = state_directory()

    try:
        if args.action == "start":
            command = args.command
            if command[:1] == ["--"]:
                command = command[1:]
            if not command:
                launch.error("a command is required")
            print(start(directory, command))
            return

        run_directory = directory / args.run_id.hex
        if args.action == "logs":
            with (run_directory / LOG).open("rb") as log:
                shutil.copyfileobj(log, sys.stdout.buffer)
        else:
            print(request(run_directory, args.action))
    except (OSError, RuntimeError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
