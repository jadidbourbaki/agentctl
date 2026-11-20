# /// script
# requires-python = ">=3.13"
# dependencies = ["pydantic-ai-slim[openai]==2.30.0"]
# ///

"""Run a tool-using example against an OpenAI-compatible chat endpoint."""

from __future__ import annotations

import argparse
import os

from pydantic_ai import Agent, UsageLimits
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


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
    agent = Agent(
        model,
        instructions="Use the multiply tool for multiplication and report the resulting integer.",
    )
    agent.tool_plain(multiply)
    result = agent.run_sync(args.prompt, usage_limits=UsageLimits(request_limit=8))
    print(result.output)


if __name__ == "__main__":
    main()
