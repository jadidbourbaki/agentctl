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

from pydantic import ValidationError

from .supervisor import CONTROL, LOG, RESULT, Status


def state_directory() -> Path:
    default = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    configured = os.environ.get("AGENTCTL_STATE_DIR") or os.environ.get("AGENT_RUNNER_STATE_DIR")
    return Path(configured or default / "agentctl").resolve()


def start(directory: Path, command: list[str]) -> str:
    run_id = uuid4().hex
    run_directory = directory / run_id
    run_directory.mkdir(mode=0o700, parents=True)
    if command[0].endswith(".py"):
        command = [sys.executable, *command]
    with (run_directory / "supervisor.log").open("wb") as log:
        supervisor = subprocess.Popen(
            [sys.executable, "-m", "agentctl.supervisor", str(run_directory), *command],
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


def request(run_directory: Path, command: str) -> Status:
    result = run_directory / RESULT
    if result.exists():
        return Status.model_validate_json(result.read_bytes())

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
                return Status.model_validate_json(status)
    except (ConnectionError, FileNotFoundError):
        if not result.exists():
            raise RuntimeError(
                f"supervisor unavailable. See {run_directory / 'supervisor.log'}"
            ) from None
    return Status.model_validate_json(result.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    launch = actions.add_parser(
        "run", aliases=["start"], help="start a command and print its run ID"
    )
    launch.add_argument("command", nargs=argparse.REMAINDER)
    for action in ("status", "suspend", "resume", "stop", "logs"):
        actions.add_parser(action).add_argument("run_id", type=UUID)
    args = parser.parse_args()
    directory = state_directory()

    try:
        if args.action in {"run", "start"}:
            command = args.command
            if command[:1] == ["--"]:
                command = command[1:]
            if not command:
                launch.error("a command is required")
            print(start(directory, command))
            return

        run_directory = directory / args.run_id.hex
        if not run_directory.exists() and not (
            os.environ.get("AGENTCTL_STATE_DIR") or os.environ.get("AGENT_RUNNER_STATE_DIR")
        ):
            legacy_run = directory.with_name("agent-runner") / args.run_id.hex
            if legacy_run.is_dir():
                run_directory = legacy_run
        if args.action == "logs":
            with (run_directory / LOG).open("rb") as log:
                shutil.copyfileobj(log, sys.stdout.buffer)
        else:
            status = request(run_directory, args.action)
            print(status.model_dump_json())
    except (OSError, RuntimeError, ValidationError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
