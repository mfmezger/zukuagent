"""Core agent implementation for ZukuAgent without agent frameworks."""

import asyncio
import inspect
from pathlib import Path
from typing import ClassVar

from google import genai
from google.genai import types
from loguru import logger
from openai import AsyncOpenAI
from rich.console import Console
from rich.markdown import Markdown

from zukuagent.core.heartbeat import AgentHeartbeat
from zukuagent.core.settings import settings
from zukuagent.services.audio_service import ParakeetTranscriptionService


class ZukuAgent:
    """The core ZukuAgent class that manages chat, skills, and runtime services."""

    PROJECT_MARKERS: ClassVar[tuple[str, ...]] = ("pyproject.toml", ".git")
    SKILLS_DIR: ClassVar[str] = "skills"
    SKILL_FILE_NAME: ClassVar[str] = "SKILL.md"

    def __init__(self, provider: str | None = None, model_name: str | None = None) -> None:
        """Initialize the agent.

        Args:
            provider: Optional runtime override. Supports "google" and "openai-local".
            model_name: Optional model override.

        """
        self.console = Console()
        self.provider = (provider or settings.default_provider).lower()
        self.model_name = model_name
        self.skills_compressed = False
        self.project_root = self._find_project_root()
        self.base_prompt = self._load_base_identity()
        self.skill_contexts = self._load_skills()
        self.system_prompt = self._compose_system_prompt(use_compressed_skills=False)

        self.transcriber = ParakeetTranscriptionService()
        self.heartbeat = AgentHeartbeat(
            interval_minutes=settings.heartbeat_interval_minutes,
            heartbeat_file=settings.heartbeat_file,
        )

        self.client: object | None = None
        self.google_aio_client = None
        self.chat_session = None
        self._openai_client: AsyncOpenAI | None = None
        self._openai_messages: list[dict[str, str]] = []

        self._setup_provider()
        logger.info("ZukuAgent initialized with runtime provider: {}", self.provider)

    def _load_base_identity(self) -> str:
        """Load identity and behavior rules from project root markdown files."""
        identity_content = []
        base_path = self.project_root
        identity_dir = Path(settings.identity_dir)
        identity_base = identity_dir if identity_dir.is_absolute() else base_path / identity_dir

        for file_name in settings.identity_files:
            p = identity_base / file_name
            if p.exists():
                with p.open(encoding="utf-8") as f:
                    identity_content.append(f.read())
            else:
                logger.warning("Identity file {} not found.", p)

        return "\n\n".join(identity_content) if identity_content else "You are Zuku, a helpful AI assistant."

    def _load_skills(self) -> list[dict[str, str]]:
        """Load local skills from skills/*/SKILL.md into prompt context."""
        skills_root = self.project_root / self.SKILLS_DIR
        if not skills_root.exists():
            return []

        loaded_skills: list[dict[str, str]] = []
        for skill_file in sorted(skills_root.glob(f"*/{self.SKILL_FILE_NAME}")):
            with skill_file.open(encoding="utf-8") as f:
                full_content = f.read().strip()
            if not full_content:
                continue
            loaded_skills.append(
                {
                    "name": skill_file.parent.name,
                    "full": full_content,
                    "compressed": self._compress_skill_content(full_content, skill_file.parent.name),
                }
            )

        if loaded_skills:
            logger.info("Loaded {} skills from {}", len(loaded_skills), skills_root)

        return loaded_skills

    def _compose_system_prompt(self, use_compressed_skills: bool) -> str:
        """Compose full system prompt with optional compressed skill context."""
        if not self.skill_contexts:
            return self.base_prompt

        skill_blocks = []
        for skill in self.skill_contexts:
            body = skill["compressed"] if use_compressed_skills else skill["full"]
            skill_blocks.append(f"### Skill: {skill['name']}\n{body}")

        section_title = "Compressed Skills Context" if use_compressed_skills else "Loaded Skills Context"
        skills_section = f"## {section_title}\n\n" + "\n\n".join(skill_blocks)
        return f"{self.base_prompt}\n\n{skills_section}"

    def _compress_skill_content(self, content: str, skill_name: str) -> str:
        """Compress verbose skill text into a concise prompt summary."""
        non_empty = [line.strip() for line in content.splitlines() if line.strip()]
        if not non_empty:
            return f"Skill `{skill_name}` with no additional details."

        description = ""
        for line in non_empty:
            if line.lower().startswith("description:"):
                description = line.split(":", 1)[1].strip()
                break

        body_candidates: list[str] = []
        for line in non_empty:
            if line.startswith(("#", "---")):
                continue
            if line.lower().startswith(("name:", "description:", "license:")):
                continue
            body_candidates.append(line)
            if len(body_candidates) == 4:
                break

        summary_parts = [f"Skill `{skill_name}`."]
        if description:
            summary_parts.append(f"Description: {description}")
        if body_candidates:
            summary_parts.append("Key guidance: " + " ".join(body_candidates))
        return " ".join(summary_parts)

    def _compress_skills_after_use(self) -> None:
        """Switch loaded skill context to compressed form after first successful use."""
        if not self.skill_contexts or self.skills_compressed:
            return

        self.skills_compressed = True
        self.system_prompt = self._compose_system_prompt(use_compressed_skills=True)
        logger.info("Compressed loaded skills for ongoing conversations.")

        if self.provider == "google":
            # Google chat sessions keep system instructions at session creation time.
            # Reset so the next request picks up the compressed prompt.
            self.chat_session = None
        elif self.provider == "openai-local":
            if self._openai_messages and self._openai_messages[0]["role"] == "system":
                self._openai_messages[0]["content"] = self.system_prompt

    def _find_project_root(self) -> Path:
        """Locate the project root by searching parent directories for known markers."""
        start = Path(__file__).resolve().parent
        for candidate in (start, *start.parents):
            if any((candidate / marker).exists() for marker in self.PROJECT_MARKERS):
                return candidate
        logger.warning("Could not find project root marker; falling back to current working directory.")
        return Path.cwd()

    def _setup_provider(self) -> None:
        """Configure the chosen runtime provider."""
        if self.provider not in {"google", "openai-local"}:
            msg = f"Unsupported provider: {self.provider}. Supported providers are: google, openai-local"
            raise ValueError(msg)

        if self.provider == "google":
            api_key = settings.google_api_key
            if not api_key:
                logger.error("GOOGLE_API_KEY not found in settings.")
                msg = "Missing GOOGLE_API_KEY"
                raise ValueError(msg)

            self.model_name = self.model_name or settings.google_model
            self.client = genai.Client(api_key=api_key)
            self.google_aio_client = self.client.aio
            return

        self.model_name = self.model_name or settings.openai_model
        api_key = settings.openai_api_key or "local"
        self._openai_client = AsyncOpenAI(base_url=settings.openai_base_url, api_key=api_key)
        self._openai_messages = [{"role": "system", "content": self.system_prompt}]

    async def chat(self, message: str) -> str:
        """Send a message to the configured runtime and return the response."""
        if self.provider == "google":
            logger.info("Sending message to Google runtime...")
            if self.chat_session is None:
                create_result = self.google_aio_client.chats.create(
                    model=self.model_name,
                    config=types.GenerateContentConfig(system_instruction=self.system_prompt),
                )
                self.chat_session = await create_result if inspect.isawaitable(create_result) else create_result

            send_result = self.chat_session.send_message(message)
            response = await send_result if inspect.isawaitable(send_result) else send_result
            response_text = response.text or ""
            if not response_text:
                response_text = "I could not produce a response from the Google runtime."
        else:
            self._openai_messages.append({"role": "user", "content": message})
            response = await self._openai_client.chat.completions.create(
                model=self.model_name,
                messages=self._openai_messages,
            )
            response_text = response.choices[0].message.content or ""
            if not response_text:
                response_text = "I could not produce a response from the OpenAI-compatible runtime."
            self._openai_messages.append({"role": "assistant", "content": response_text})

        self._compress_skills_after_use()
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
    agent = ZukuAgent()
    asyncio.run(agent.run())
