"""Core heartbeat implementation for ZukuAgent."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


class AgentHeartbeat:
    """A proactive heartbeat mechanism for the ZukuAgent, inspired by OpenClaw.

    It runs in the background of the main agent loop, "waking up" periodically
    to perform 'cheap checks' (local file/status checks) before deciding whether
    to escalate to a full agent turn (LLM call).
    """

    def __init__(self, interval_minutes: int = 10, heartbeat_file: str = "HEARTBEAT.md") -> None:
        """Initialize the heartbeat service.

        Args:
            interval_minutes (int): How often the heartbeat should pulse.
            heartbeat_file (str): The local file to check for pending tasks.

        """
        self.interval_seconds = interval_minutes * 60
        self.heartbeat_file = heartbeat_file
        self.is_running = False
        self._task: asyncio.Task | None = None
        self._last_pulse: datetime | None = None

    async def _cheap_checks(self) -> bool:
        """Perform lightweight local checks to determine if the agent needs to act.

        This avoids unnecessary LLM API calls.

        Patterns:
        1. Check if HEARTBEAT.md exists and has content.
        2. Check for specific 'flag' files in the workspace.
        3. Check system status (e.g., low disk space, high CPU).
        """
        logger.debug("Heartbeat: Running cheap checks...")

        # Pattern 1: Check for HEARTBEAT.md presence and content
        path = Path(self.heartbeat_file)
        if path.exists():
            # Use to_thread for blocking file IO in async function to satisfy ruff ASYNC230
            content = await asyncio.to_thread(path.read_text)
            if content.strip():
                logger.info(f"Heartbeat: Found content in {self.heartbeat_file}. Action may be required.")
                return True

        # Add more cheap checks here as the agent evolves
        # (e.g., checking a database, a task queue, or a specific directory)

        return False

    async def _pulse_loop(self) -> None:
        """Run the internal loop that executes the heartbeat pulses."""
        while self.is_running:
            self._last_pulse = datetime.now(tz=UTC)
            logger.info(f"Heartbeat pulse at {self._last_pulse.strftime('%H:%M:%S')}")

            try:
                # 1. Run the 'cheap' local checks
                needs_escalation = await self._cheap_checks()

                # 2. If checks pass, trigger the 'expensive' agent turn
                if needs_escalation:
                    logger.info("Heartbeat: Cheap checks PASSED. Triggering full agent turn...")
                    await self._trigger_agent_action()
                else:
                    logger.debug("Heartbeat: Cheap checks FAILED (nothing to do). Returning to sleep.")

            except asyncio.CancelledError:
                logger.info("Heartbeat loop is being cancelled.")
                break
            except Exception as e:
                logger.error(f"Heartbeat encountered an error: {e}")

            # 3. Wait for the next interval
            logger.debug(f"Heartbeat: Sleeping for {self.interval_seconds} seconds...")
            await asyncio.sleep(self.interval_seconds)

    async def _trigger_agent_action(self) -> None:
        """Trigger the main Agent core logic.

        In a full implementation, this would trigger an LLM prompt.
        """
        # Placeholder for main agent logic escalation
        logger.warning("Heartbeat escalation: [PLACEHOLDER] Agent core would be invoked here.")

        # In a real OpenClaw-like system, we might clear the heartbeat file after processing
        # if os.path.exists(self.heartbeat_file):
        #     os.remove(self.heartbeat_file)

    def start(self) -> None:
        """Start the heartbeat as a background asyncio task."""
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._pulse_loop())
            logger.info(f"Heartbeat started (Interval: {self.interval_seconds / 60} mins).")
        else:
            logger.warning("Heartbeat is already running.")

    def stop(self) -> None:
        """Stop the heartbeat and cancel the background task."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            logger.info("Heartbeat stopped.")
        else:
            logger.warning("Heartbeat was not running.")

    @property
    def status(self) -> dict:
        """Return the current status of the heartbeat."""
        return {
            "running": self.is_running,
            "interval_minutes": self.interval_seconds / 60,
            "last_pulse": self._last_pulse.isoformat() if self._last_pulse else None,
        }


if __name__ == "__main__":
    # Test script to demonstrate the heartbeat in action
    async def test_main() -> None:
        """Run a simple test loop for the heartbeat."""
        logger.info("Starting Heartbeat test (30-second interval for demo)...")
        hb = AgentHeartbeat(interval_minutes=0.5)  # 30 seconds for testing
        hb.start()

        try:
            # Let it run for a bit
            await asyncio.sleep(70)
        finally:
            hb.stop()
            logger.info("Test complete.")

    asyncio.run(test_main())
