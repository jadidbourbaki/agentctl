"""Own one admitted process group and serve its lifecycle commands."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import termios
import time
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from select import select
from typing import Literal

from pydantic import BaseModel, ConfigDict, PositiveInt

CONTROL = "control.sock"
RESULT = "result.json"
LOG = "output.log"
STOP_GRACE_SECONDS = 3


class Status(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    state: Literal["running", "suspended", "stopping", "exited"]
    pid: PositiveInt
    returncode: int | None = None


def control(group: int, status: Status, command: bytes) -> float | None:
    if command == b"suspend" and status.state == "running":
        os.killpg(group, signal.SIGSTOP)
        status.state = "suspended"
    elif command == b"resume" and status.state == "suspended":
        os.killpg(group, signal.SIGCONT)
        status.state = "running"
    elif command == b"stop" and status.state in {"running", "suspended"}:
        os.killpg(group, signal.SIGTERM)
        os.killpg(group, signal.SIGCONT)
        status.state = "stopping"
        return time.monotonic() + STOP_GRACE_SECONDS
    return None


def has_exited(pid: int) -> bool:
    event = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    # macOS can report a stopped child even when WEXITED is the only event requested.
    return event is not None and event.si_code in {os.CLD_EXITED, os.CLD_KILLED, os.CLD_DUMPED}


def kill_group(group: int) -> None:
    # macOS returns EPERM when the group contains only an unreaped zombie.
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(group, signal.SIGKILL)


def finish(process: subprocess.Popen[bytes], status: Status) -> None:
    # The unreaped leader reserves the group ID while we clean up descendants.
    kill_group(process.pid)
    status.returncode = process.wait()
    status.state = "exited"
    Path("result.tmp").write_text(status.model_dump_json())
    Path("result.tmp").replace(RESULT)


def supervise(
    listener: socket.socket, child_events: socket.socket, process: subprocess.Popen[bytes]
) -> None:
    status = Status(state="running", pid=process.pid)
    stop_deadline = None
    while not has_exited(process.pid):
        timeout = None
        if stop_deadline is not None:
            timeout = stop_deadline - time.monotonic()
            if timeout <= 0:
                break
        readable, _, _ = select([listener, child_events], [], [], timeout)
        if not readable:
            break
        if child_events in readable:
            child_events.recv(4096)
            continue
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(0.5)
            try:
                with connection.makefile("rb") as request:
                    command = request.read(32)
            except (ConnectionError, TimeoutError):
                continue
            try:
                deadline = control(process.pid, status, command)
            except ProcessLookupError:
                finish(process, status)
                deadline = None
            if deadline is not None:
                stop_deadline = deadline
            with suppress(ConnectionError, TimeoutError):
                connection.sendall(status.model_dump_json().encode())
        if status.state == "exited":
            return
    finish(process, status)


@contextmanager
def terminal_process(command: list[str], directory: Path) -> Iterator[subprocess.Popen[bytes]]:
    terminal = sys.stdin.fileno()
    foreground_group = os.tcgetpgrp(terminal)
    if foreground_group != os.getpgrp():
        raise RuntimeError("--tty must run in the foreground")
    settings = termios.tcgetattr(terminal)
    read_fd, write_fd = os.pipe()

    # Wait for the terminal handoff before the child starts reading from it.
    with os.fdopen(read_fd, "rb"), os.fdopen(write_fd, "wb", buffering=0) as gate:
        process = subprocess.Popen(
            [sys.executable, "-m", "agentctl.supervisor", "--tty-child", str(read_fd), *command],
            cwd=directory,
            process_group=0,
            pass_fds=(read_fd,),
        )
        previous_handler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
        try:
            os.tcsetpgrp(terminal, process.pid)
            gate.write(b"1")
            yield process
        finally:
            with suppress(OSError, termios.error):
                os.tcsetpgrp(terminal, foreground_group)
                termios.tcsetattr(terminal, termios.TCSANOW, settings)
            signal.signal(signal.SIGTTOU, previous_handler)
            if process.returncode is None:
                kill_group(process.pid)
                process.wait()


def exec_terminal_child(args: list[str]) -> None:
    with os.fdopen(int(args[0]), "rb", buffering=0) as gate:
        if gate.read(1) != b"1":
            raise SystemExit(1)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    os.execvp(args[1], args[1:])


def main() -> None:
    args = sys.argv[1:]
    if args[0] == "--tty-child":
        exec_terminal_child(args[1:])
        return
    terminal = args[0] == "--tty"
    if terminal:
        args = args[1:]

    run_directory = Path(args[0])
    work_directory = Path.cwd()
    os.chdir(run_directory)
    child_events, signal_writer = socket.socketpair()
    with child_events, signal_writer, socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        signal_writer.setblocking(False)
        signal.set_wakeup_fd(signal_writer.fileno())
        signal.signal(signal.SIGCHLD, lambda *_: None)
        listener.bind(CONTROL)
        listener.listen()
        if terminal:
            with terminal_process(args[1:], work_directory) as process:
                supervise(listener, child_events, process)
            assert process.returncode is not None
            returncode = process.returncode
            raise SystemExit(returncode if returncode >= 0 else 128 - returncode)

        with Path(LOG).open("ab", buffering=0) as log:
            process = subprocess.Popen(
                args[1:],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                cwd=work_directory,
                env={"PYTHONUNBUFFERED": "1", **os.environ},
            )
        try:
            print("ready", flush=True)
            supervise(listener, child_events, process)
        finally:
            if process.returncode is None:
                kill_group(process.pid)
                process.wait()


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, termios.error) as error:
        raise SystemExit(f"agentctl: {error}") from None
