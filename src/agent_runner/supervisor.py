"""Own one admitted process group and serve its lifecycle commands."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from select import select

CONTROL = "control.sock"
RESULT = "result.json"
LOG = "output.log"
STOP_GRACE_SECONDS = 3


@dataclass
class Status:
    state: str
    pid: int
    returncode: int | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))


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
    Path("result.tmp").write_text(status.to_json())
    Path("result.tmp").replace(RESULT)


def supervise(
    listener: socket.socket, child_events: socket.socket, process: subprocess.Popen[bytes]
) -> None:
    status = Status("running", process.pid)
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
                connection.sendall(status.to_json().encode())
        if status.state == "exited":
            return
    finish(process, status)


def main() -> None:
    run_directory = Path(sys.argv[1])
    work_directory = Path.cwd()
    os.chdir(run_directory)
    child_events, signal_writer = socket.socketpair()
    with child_events, signal_writer, socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        signal_writer.setblocking(False)
        signal.set_wakeup_fd(signal_writer.fileno())
        signal.signal(signal.SIGCHLD, lambda *_: None)
        listener.bind(CONTROL)
        listener.listen()
        with Path(LOG).open("ab", buffering=0) as log:
            process = subprocess.Popen(
                sys.argv[2:],
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
    main()
