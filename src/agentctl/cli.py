"""Start a command or control a run by its ID."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import socket
import subprocess
import sys
from collections import Counter
from contextlib import chdir
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from .supervisor import CONTROL, LOG, RESULT, Status

COMMAND = "command.json"
SHORT_ID_LENGTH = 8


class RunCommand(BaseModel):
    executable: str
    name: str | None = None
    tty: bool = False


def state_directories() -> list[Path]:
    configured = os.environ.get("AGENTCTL_STATE_DIR") or os.environ.get("AGENT_RUNNER_STATE_DIR")
    if configured:
        return [Path(configured).resolve()]
    default = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state").resolve()
    return [default / "agentctl", default / "agent-runner"]


def run_directories(roots: list[Path]) -> dict[str, Path]:
    runs: dict[str, Path] = {}
    for root in roots:
        if root.is_dir():
            for path in root.iterdir():
                if re.fullmatch(r"[0-9a-f]{32}", path.name) and path.is_dir():
                    runs.setdefault(path.name, path)
    return runs


def parse_run_id(value: str) -> str:
    if re.fullmatch(r"[0-9a-fA-F]{8,32}", value):
        return value.lower()
    try:
        return UUID(value).hex
    except ValueError as error:
        raise argparse.ArgumentTypeError("use a run UUID or at least eight hex digits") from error


def find_run(runs: dict[str, Path], run_id: str) -> Path:
    matches = [path for name, path in runs.items() if name.startswith(run_id)]
    if not matches:
        raise RuntimeError(f"no run matches {run_id}")
    if len(matches) > 1:
        raise RuntimeError(f"run ID {run_id} is ambiguous. Use more digits.")
    return matches[0]


def list_runs(runs: dict[str, Path], include_finished: bool) -> None:
    prefix_counts = Counter(run_id[:SHORT_ID_LENGTH] for run_id in runs)
    id_width = 32 if any(count > 1 for count in prefix_counts.values()) else 8
    print(f"{'ID':<{id_width}}  {'STATE':<12} {'PID':>7}  COMMAND")
    for run_id, path in sorted(runs.items()):
        prefix = run_id[:SHORT_ID_LENGTH]
        displayed_id = prefix if prefix_counts[prefix] == 1 else run_id
        try:
            status = request(path, "status")
        except (OSError, RuntimeError, ValidationError):
            status = None
        if not include_finished and (status is None or status.state == "exited"):
            continue
        state = status.state if status is not None else "unavailable"
        pid = str(status.pid) if status is not None else "-"
        print(f"{displayed_id:<{id_width}}  {state:<12} {pid:>7}  {command_name(path)}")


def command_name(run_directory: Path) -> str:
    try:
        record = (run_directory / COMMAND).read_bytes()
    except FileNotFoundError:
        return "-"
    command = RunCommand.model_validate_json(record)
    name = command.name or command.executable
    return "".join(character if character.isprintable() else "?" for character in name)


def start(directory: Path, command: list[str], name: str | None, tty: bool) -> str:
    if tty and not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise RuntimeError("--tty needs terminal input and output")
    run_id = uuid4().hex
    run_directory = directory / run_id
    run_directory.mkdir(mode=0o700, parents=True)
    command_record = RunCommand(executable=Path(command[0]).name, name=name, tty=tty)
    record = run_directory / "command.tmp"
    record.write_text(command_record.model_dump_json())
    record.replace(run_directory / COMMAND)
    if command[0].endswith(".py"):
        command = [sys.executable, *command]
    supervisor_args = [sys.executable, "-m", "agentctl.supervisor"]
    if tty:
        os.execv(sys.executable, [*supervisor_args, "--tty", str(run_directory), *command])

    with (run_directory / "supervisor.log").open("wb") as log:
        supervisor = subprocess.Popen(
            [*supervisor_args, str(run_directory), *command],
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
    try:
        with chdir(run_directory), socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
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
    launch.add_argument("-n", "--name", help="name to show in the run list")
    launch.add_argument("--tty", action="store_true", help="run in the current terminal")
    launch.add_argument("command", nargs=argparse.REMAINDER)
    listing = actions.add_parser("list", help="show active runs")
    listing.add_argument("--all", action="store_true", help="include finished and unavailable runs")
    for action in ("status", "suspend", "resume", "stop"):
        actions.add_parser(action).add_argument("run_id", type=parse_run_id)
    logs = actions.add_parser("logs", help="print a run's output")
    logs.add_argument("run_id", type=parse_run_id)
    logs.add_argument("-f", "--follow", action="store_true", help="follow new output")
    args = parser.parse_args()
    roots = state_directories()

    try:
        if args.action in {"run", "start"}:
            command = args.command
            if command[:1] == ["--"]:
                command = command[1:]
            if not command:
                launch.error("a command is required")
            print(start(roots[0], command, args.name, args.tty))
            return

        runs = run_directories(roots)
        if args.action == "list":
            list_runs(runs, include_finished=args.all)
            return
        run_directory = find_run(runs, args.run_id)
        if args.action == "logs":
            log_path = run_directory / LOG
            record = run_directory / COMMAND
            if record.exists() and RunCommand.model_validate_json(record.read_bytes()).tty:
                raise RuntimeError("this run writes output to its terminal")
            if args.follow:
                os.execlp("tail", "tail", "-n", "+1", "-f", str(log_path))
            with log_path.open("rb") as log:
                shutil.copyfileobj(log, sys.stdout.buffer)
        else:
            status = request(run_directory, args.action)
            print(status.model_dump_json())
    except (OSError, RuntimeError, ValidationError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
