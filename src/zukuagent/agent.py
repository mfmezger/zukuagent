"""Core agent implementation for ZukuAgent."""

import asyncio
from pathlib import Path
from typing import ClassVar

from google import genai
from google.genai import types
from loguru import logger
from openai import AsyncOpenAI
from rich.console import Console
from rich.markdown import Markdown

from zukuagent.audio_service import ParakeetTranscriptionService
from zukuagent.heartbeat import AgentHeartbeat
from zukuagent.settings import settings


class ZukuAgent:
    """The core ZukuAgent class that manages the agent loop.

    LLM providers, and integrated services.
    """

    IDENTITY_FILES: ClassVar[list[str]] = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "USER.md"]
    PROJECT_MARKERS: ClassVar[tuple[str, ...]] = ("pyproject.toml", ".git")

    def __init__(self, provider: str | None = None, model_name: str | None = None) -> None:
        """Initialize the agent with a specific provider and model.

        Args:
            provider (str): 'google' or 'openrouter'
            model_name (str): Specific model ID (e.g., 'gemini-1.5-flash')

        """
        self.console = Console()
        self.provider = (provider or settings.default_provider).lower()
        self.model_name = model_name
        self.history: list[dict[str, str]] = []
        self.chat_session = None

        # Load Identity
        self.system_prompt = self._load_identity()

        # Initialize Services
        self.transcriber = ParakeetTranscriptionService()
        self.heartbeat = AgentHeartbeat(
            interval_minutes=settings.heartbeat_interval_minutes,
            heartbeat_file=settings.heartbeat_file,
        )

        # Provider-specific setup
        self._setup_provider()

        logger.info(f"ZukuAgent initialized with provider: {self.provider}")

    def _load_identity(self) -> str:
        """Load identity and behavior rules from Markdown files."""
        identity_content = []
        base_path = self._find_project_root()

        for file_name in self.IDENTITY_FILES:
            p = base_path / file_name
            if p.exists():
                with p.open(encoding="utf-8") as f:
                    identity_content.append(f.read())
            else:
                logger.warning(f"Identity file {p} not found.")

        return "\n\n".join(identity_content) if identity_content else "You are Zuku, a helpful AI assistant."

    def _find_project_root(self) -> Path:
        """Locate the project root by searching parent directories for known markers."""
        start = Path(__file__).resolve().parent
        for candidate in (start, *start.parents):
            if any((candidate / marker).exists() for marker in self.PROJECT_MARKERS):
                return candidate
        logger.warning("Could not find project root marker; falling back to current working directory.")
        return Path.cwd()

    def _setup_provider(self) -> None:
        """Configure the chosen LLM provider."""
        if self.provider == "google":
            api_key = settings.google_api_key
            if not api_key:
                logger.error("GOOGLE_API_KEY not found in settings.")
                msg = "Missing GOOGLE_API_KEY"
                raise ValueError(msg)
            self.model_name = self.model_name or settings.google_model
            self.client = genai.Client(api_key=api_key.get_secret_value())
            self.chat_session = self.client.chats.create(
                model=self.model_name,
                config=types.GenerateContentConfig(system_instruction=self.system_prompt),
            )

        elif self.provider == "openrouter":
            api_key = settings.openrouter_api_key
            if not api_key:
                logger.error("OPENROUTER_API_KEY not found in settings.")
                msg = "Missing OPENROUTER_API_KEY"
                raise ValueError(msg)
            self.model_name = self.model_name or settings.openrouter_model
            self.client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key.get_secret_value(),
            )
            self.history.append({"role": "system", "content": self.system_prompt})
        else:
            msg = f"Unsupported provider: {self.provider}"
            raise ValueError(msg)

    async def chat(self, message: str) -> str:
        """Send a message to the LLM and return the response."""
        logger.info(f"Sending message to {self.provider}...")

        if self.provider == "google":
            response = await asyncio.to_thread(self.chat_session.send_message, message)
            response_text = response.text

        elif self.provider == "openrouter":
            self.history.append({"role": "user", "content": message})
            response = await self.client.chat.completions.create(model=self.model_name, messages=self.history)
            response_text = response.choices[0].message.content
            self.history.append({"role": "assistant", "content": response_text})

        return response_text

    async def process_audio(self, audio_path: str) -> None:
        """Transcribe audio and send it to the agent."""
        text = self.transcriber.transcribe(audio_path)
        if text:
            self.console.print(f"[bold cyan]Transcribed:[/bold cyan] {text}")
            response = await self.chat(text)
            self.console.print(Markdown(response))
        else:
            logger.warning("No speech detected in audio file.")

    async def run(self) -> None:
        """Start the agent's main interactive loop."""
        self.heartbeat.start()
        self.console.print("[bold green]ZukuAgent is active. Type 'exit' to quit.[/bold green]")

        try:
            while True:
                user_input = await asyncio.to_thread(input, "User > ")

                if user_input.lower() in ["exit", "quit"]:
                    break

                if user_input.startswith("/audio "):
                    audio_path = user_input.split(" ", 1)[1]
                    await self.process_audio(audio_path)
                    continue

                response = await self.chat(user_input)
                self.console.print(Markdown(response))

        finally:
            self.heartbeat.stop()
            logger.info("ZukuAgent shutting down.")


if __name__ == "__main__":
    # Example usage
    agent = ZukuAgent()
    asyncio.run(agent.run())
