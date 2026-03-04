"""Main entry point for ZukuAgent."""

import argparse
import asyncio
import sys
from pathlib import Path

from zukuagent.core.agent import ZukuAgent
from zukuagent.core.settings import settings
from zukuagent.endpoints.telegram import TelegramEndpoint
from zukuagent.services.sandbox_service import MontySandboxService


def main() -> None:
    """Run the ZukuAgent CLI application."""
    parser = argparse.ArgumentParser(description="Run ZukuAgent with different endpoints.")
    parser.add_argument(
        "--endpoint",
        choices=["cli", "telegram"],
        default=settings.endpoint_mode,
        help="Endpoint mode to run.",
    )
    parser.add_argument("--provider", default=None, help="Runtime provider override (google|openai-local).")
    parser.add_argument("--model", default=None, help="Model name override.")
    parser.add_argument("--message", default=None, help="Send one message and exit (CLI endpoint only).")
    parser.add_argument("--sandbox-code", default=None, help="Python code snippet to execute in Monty sandbox.")
    parser.add_argument("--sandbox-file", default=None, help="Path to a Python file to execute in Monty sandbox.")
    parser.add_argument("--sandbox-type-check", action="store_true", help="Enable Monty type checking.")
    args = parser.parse_args()

    if args.sandbox_code and args.sandbox_file:
        parser.error("Use only one of --sandbox-code or --sandbox-file.")

    if args.sandbox_code or args.sandbox_file:
        code = args.sandbox_code
        if args.sandbox_file:
            try:
                code = Path(args.sandbox_file).read_text(encoding="utf-8")
            except FileNotFoundError:
                parser.error(f"File not found: {args.sandbox_file}")

        sandbox = MontySandboxService(type_check=args.sandbox_type_check)
        result = sandbox.run_code(code)
        if result.output is not None:
            sys.stdout.write(f"{result.output}\n")
        return

    agent = ZukuAgent(provider=args.provider, model_name=args.model)

    if args.endpoint == "telegram":
        endpoint = TelegramEndpoint(message_handler=agent.chat)
        asyncio.run(endpoint.run())
        return

    if args.message:
        response = asyncio.run(agent.chat(args.message))
        sys.stdout.write(f"{response}\n")
        return

    asyncio.run(agent.run())


if __name__ == "__main__":  # pragma: no cover
    main()
