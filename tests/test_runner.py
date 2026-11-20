from __future__ import annotations

import json
import os
import pty
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from select import select
from uuid import uuid4

import pytest


class Runner:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.runs: list[str] = []

    def invoke(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", "from agentctl.cli import main; main()", *args],
            env={**os.environ, "AGENTCTL_STATE_DIR": str(self.directory)},
            capture_output=True,
            text=True,
            timeout=10,
        )

    def call(self, *args: str) -> str:
        result = self.invoke(*args)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()

    def start(self, *args: str) -> str:
        run_id = self.call("run", *args)
        self.runs.append(run_id)
        return run_id

    def wait_for_exit(self, run_id: str) -> int:
        for _ in range(100):
            status = json.loads(self.call("status", run_id))
            if status["state"] == "exited":
                return int(status["returncode"])
            time.sleep(0.02)
        pytest.fail(f"{run_id} did not exit")


@pytest.fixture
def runner(tmp_path: Path) -> Iterator[Runner]:
    runner = Runner(tmp_path / ("long-state-path-" * 8))
    try:
        yield runner
    finally:
        for run_id in runner.runs:
            runner.call("stop", run_id)
            runner.wait_for_exit(run_id)


def test_python_script_preserves_arguments_and_exit_code(runner: Runner, tmp_path: Path) -> None:
    script = tmp_path / "my agent.py"
    script.write_text("import sys\nprint(sys.argv[1])\nraise SystemExit(7)\n")
    run_id = runner.start(str(script), "one argument; $literal")
    assert runner.wait_for_exit(run_id) == 7
    assert runner.call("logs", run_id) == "one argument; $literal"


def test_suspend_and_resume_include_child_process(runner: Runner) -> None:
    run_id = runner.start(
        "/bin/sh",
        "-c",
        "while true; do echo tick; sleep 0.03; done & wait",
    )
    log = runner.directory / run_id / "output.log"
    for _ in range(100):
        if log.stat().st_size:
            break
        time.sleep(0.02)
    assert log.stat().st_size > 0

    suspended = json.loads(runner.call("suspend", run_id))
    assert suspended["state"] == "suspended"
    time.sleep(0.1)
    paused_size = log.stat().st_size
    time.sleep(0.15)
    assert log.stat().st_size == paused_size

    running = json.loads(runner.call("resume", run_id))
    assert running["state"] == "running"
    assert running["pid"] == suspended["pid"]
    for _ in range(100):
        if log.stat().st_size > paused_size:
            break
        time.sleep(0.02)
    assert log.stat().st_size > paused_size

    runner.call("suspend", run_id)
    runner.call("stop", run_id)
    assert runner.wait_for_exit(run_id) == -signal.SIGTERM


def test_stop_kills_a_process_that_ignores_sigterm(runner: Runner) -> None:
    run_id = runner.start(
        sys.executable,
        "-c",
        "import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print('ready', flush=True)\ntime.sleep(60)",
    )
    for _ in range(100):
        if runner.call("logs", run_id) == "ready":
            break
        time.sleep(0.02)
    assert runner.call("logs", run_id) == "ready"

    runner.call("stop", run_id)
    assert runner.wait_for_exit(run_id) == -signal.SIGKILL


def test_status_rejects_a_malformed_result(runner: Runner) -> None:
    run_id = uuid4().hex
    run_directory = runner.directory / run_id
    run_directory.mkdir(parents=True)
    (run_directory / "result.json").write_text(
        '{"state":"exited","pid":"not a process ID","returncode":0}'
    )

    result = runner.invoke("status", run_id)
    assert result.returncode == 1
    assert not result.stdout
    assert "pid" in result.stderr


def test_list_discovers_active_run_and_accepts_its_short_id(runner: Runner) -> None:
    completed = runner.start("/bin/echo", "done")
    assert runner.wait_for_exit(completed) == 0
    active = runner.start("-n", "worker", "/bin/sleep", "30")
    active_id = active[:8]

    assert active_id in runner.call("list")
    assert completed[:8] not in runner.call("list")
    assert completed[:8] in runner.call("list", "--all")
    assert "worker" in runner.call("list")
    assert json.loads(runner.call("suspend", active_id))["state"] == "suspended"
    assert json.loads(runner.call("resume", active_id))["state"] == "running"


def test_ambiguous_short_id_is_rejected(runner: Runner) -> None:
    prefix = uuid4().hex[:8]
    for suffix in ("a", "b"):
        run_path = runner.directory / (prefix + suffix * 24)
        run_path.mkdir(parents=True)

    result = runner.invoke("resume", prefix)
    assert result.returncode == 1
    assert "ambiguous" in result.stderr


def read_terminal(master: int, expected: bytes) -> None:
    data = bytearray()
    deadline = time.monotonic() + 8
    while expected not in data:
        readable, _, _ = select([master], [], [], max(0, deadline - time.monotonic()))
        assert readable, data.decode(errors="replace")
        data.extend(os.read(master, 1024))


def test_tty_preserves_interactive_input_after_resume(runner: Runner) -> None:
    pid, master = pty.fork()
    if pid == 0:
        os.execve(
            sys.executable,
            [
                sys.executable,
                "-c",
                "from agentctl.cli import main; main()",
                "run",
                "--tty",
                "sh",
                "-c",
                'echo ready; read -r line; echo "received: $line"; exit 7',
            ],
            {**os.environ, "AGENTCTL_STATE_DIR": str(runner.directory)},
        )

    try:
        read_terminal(master, b"ready")
        run_id = runner.call("list").splitlines()[1].split()[0]
        suspended = json.loads(runner.call("suspend", run_id))
        assert suspended["state"] == "suspended"
        resumed = json.loads(runner.call("resume", run_id))
        assert resumed["state"] == "running"
        assert resumed["pid"] == suspended["pid"]

        os.write(master, b"terminal input\n")
        read_terminal(master, b"received: terminal input")
        assert runner.wait_for_exit(run_id) == 7
    finally:
        os.close(master)
        _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 7
