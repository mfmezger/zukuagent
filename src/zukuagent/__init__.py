"""Main entry point for ZukuAgent."""

import argparse
import asyncio

from zukuagent.core.agent import ZukuAgent
from zukuagent.core.settings import settings
from zukuagent.endpoints.telegram import TelegramEndpoint


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
    args = parser.parse_args()

    agent = ZukuAgent(provider=args.provider, model_name=args.model)

    if args.endpoint == "telegram":
        endpoint = TelegramEndpoint(message_handler=agent.chat)
        asyncio.run(endpoint.run())
        return

    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
