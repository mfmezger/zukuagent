"""Main entry point for ZukuAgent."""

import asyncio

from zukuagent.agent import ZukuAgent


def main() -> None:
    """Run the ZukuAgent CLI application."""
    agent = ZukuAgent()
    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
