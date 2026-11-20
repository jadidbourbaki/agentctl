# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "pydantic-ai-slim[openai]==2.52.0",
#     "pydantic-deep==0.3.50",
#     "pydantic==2.14.4",
#     "rich==15.0.0",
#     "textual==8.2.8",
# ]
# ///

"""Investigate a simulated checkout incident or watch an existing run."""

from __future__ import annotations

import argparse
import asyncio
import os
from time import sleep
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ValidationError
from pydantic_ai import UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_deep import create_deep_agent, create_default_deps
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Footer, RichLog, Static

SIGNALS = {
    "rollout": (
        "14:00 UTC   Checkout v2.8 rollout begins",
        "14:04 UTC   eu-west reaches 100% on v2.8",
        "14:05 UTC   us-east remains on v2.7",
    ),
    "latency": (
        "13:55 UTC   eu-west p95 is 180 ms",
        "14:05 UTC   eu-west p95 rises to 920 ms",
        "14:05 UTC   us-east p95 holds at 190 ms",
    ),
    "errors": (
        "13:55 UTC   eu-west errors are 0.4%",
        "14:05 UTC   eu-west errors reach 6.1%",
        "14:06 UTC   Payment timeouts account for 84% of eu-west errors",
    ),
}


def replay_signal(signal: Literal["rollout", "latency", "errors"]) -> tuple[str, ...]:
    """Read one simulated telemetry feed."""
    print(f"\nReading {signal}", flush=True)
    for sample in SIGNALS[signal]:
        sleep(2)
        print(sample, flush=True)
    return SIGNALS[signal]


def investigate(model_name: str, prompt: str) -> None:
    provider = OpenAIProvider(
        base_url=os.environ.get("OPENAI_BASE_URL") or "http://127.0.0.1:8080/v1",
        api_key=os.environ.get("OPENAI_API_KEY") or "local",
    )
    agent = create_deep_agent(
        model=OpenAIChatModel(model_name, provider=provider),
        instructions=(
            "Review a simulated checkout incident. Call replay_signal for rollout, latency, "
            "and errors in that order. After all three, write a short report with one plain "
            "text line each for Impact, Suspect, and Action. Include the measured latency "
            "and error rates. Distinguish correlation from a proven cause."
        ),
        include_filesystem=False,
        include_subagents=False,
        include_skills=False,
        include_todo=False,
        include_memory=False,
        include_history_archive=False,
        include_monitoring=False,
        cost_tracking=False,
        web_search=False,
        web_fetch=False,
        model_settings={"parallel_tool_calls": False, "temperature": 0},
    )
    agent.tool_plain(replay_signal)
    result = agent.run_sync(
        prompt, deps=create_default_deps(), usage_limits=UsageLimits(request_limit=8)
    )
    print(f"\nIncident report\n{result.output}", flush=True)


class RunStatus(BaseModel):
    state: Literal["running", "suspended", "stopping", "exited"]
    pid: int
    returncode: int | None


async def agentctl(action: str, run_id: str) -> str:
    process = await asyncio.create_subprocess_exec(
        "agentctl", action, run_id, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    output, error = await process.communicate()
    if process.returncode:
        raise RuntimeError(error.decode().strip())
    return output.decode(errors="replace")


class IncidentView(App[None]):
    CSS = """
    Screen { padding: 1 2; }
    #title { text-style: bold; height: 2; }
    #state { height: 2; }
    RichLog { height: 1fr; border: round $primary; padding: 0 1; }
    """
    BINDINGS = [("q", "quit", "Close")]

    def __init__(self, run_id: UUID) -> None:
        super().__init__()
        self.run_id = run_id.hex
        self.output_length = 0

    def compose(self) -> ComposeResult:
        yield Static("Checkout incident", id="title")
        yield Static("Connecting to agentctl", id="state")
        yield RichLog(wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.poller = self.set_interval(0.75, self.refresh_run)
        self.call_after_refresh(self.refresh_run)

    async def refresh_run(self) -> None:
        label = self.query_one("#state", Static)
        try:
            snapshot = await agentctl("status", self.run_id)
            status = RunStatus.model_validate_json(snapshot)
            output = await agentctl("logs", self.run_id)
        except (OSError, RuntimeError, ValidationError) as error:
            label.update(Text(str(error), style="red"))
            self.poller.pause()
            return

        style = "yellow" if status.state == "suspended" else "green"
        if status.returncode:
            style = "red"
        summary = f"{status.state.upper()}  •  PID {status.pid}"
        if status.returncode is not None:
            summary += f"  •  Exit {status.returncode}"
        label.update(Text(summary, style=style))

        log = self.query_one(RichLog)
        for line in output[self.output_length :].splitlines():
            color = "bold cyan" if line.startswith("Reading ") or line == "Incident report" else ""
            log.write(Text(line, style=color))
        self.output_length = len(output)
        if status.state == "exited":
            self.poller.pause()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="investigate the simulated incident")
    run.add_argument("--model", default="local")
    run.add_argument("prompt", nargs="?", default="Investigate the checkout slowdown.")
    watch = commands.add_parser("watch", help="show the live run in a terminal")
    watch.add_argument("run_id", type=UUID)
    args = parser.parse_args()
    if args.command == "watch":
        IncidentView(args.run_id).run()
    else:
        investigate(args.model, args.prompt)


if __name__ == "__main__":
    main()
