# /// script
# requires-python = ">=3.13"
# dependencies = ["pydantic-ai-slim[openai]==2.52.0", "pydantic-deep==0.3.50"]
# ///

"""Run a tool-using example against an OpenAI-compatible chat endpoint."""

from __future__ import annotations

import argparse
import os

from pydantic_ai import UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_deep import create_deep_agent, create_default_deps


def multiply(left: int, right: int) -> int:
    """Multiply two integers."""
    return left * right


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="model name served by the endpoint")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL") or "http://127.0.0.1:8080/v1",
    )
    parser.add_argument("prompt")
    args = parser.parse_args()

    provider = OpenAIProvider(
        base_url=args.base_url,
        api_key=os.environ.get("OPENAI_API_KEY") or "local",
    )
    model = OpenAIChatModel(args.model, provider=provider)
    agent = create_deep_agent(
        model=model,
        instructions="Use the multiply tool for multiplication and report the resulting integer.",
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
    )
    agent.tool_plain(multiply)
    result = agent.run_sync(
        args.prompt, deps=create_default_deps(), usage_limits=UsageLimits(request_limit=8)
    )
    print(result.output)


if __name__ == "__main__":
    main()
