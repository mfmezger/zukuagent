"""Core agent implementation for ZukuAgent."""

import asyncio
import inspect
import json
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
from zukuagent.services.sandbox_service import MontySandboxService


class ZukuAgent:
    """The core ZukuAgent class that manages the agent loop.

    LLM providers, and integrated services.
    """

    PROJECT_MARKERS: ClassVar[tuple[str, ...]] = ("pyproject.toml", ".git")
    SKILLS_DIR: ClassVar[str] = "skills"
    SKILL_FILE_NAME: ClassVar[str] = "SKILL.md"
    SANDBOX_TOOL_NAME: ClassVar[str] = "execute_python_sandbox"

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
        self.google_aio_client = None
        self.skills_compressed = False
        self.project_root = self._find_project_root()
        self.base_prompt = self._load_base_identity()
        self.skill_contexts = self._load_skills()

        # Load Identity and Skills
        self.system_prompt = self._compose_system_prompt(use_compressed_skills=False)

        # Initialize Services
        self.transcriber = ParakeetTranscriptionService()
        self.sandbox = MontySandboxService()
        self.heartbeat = AgentHeartbeat(
            interval_minutes=settings.heartbeat_interval_minutes,
            heartbeat_file=settings.heartbeat_file,
        )

        # Provider-specific setup
        self._setup_provider()

        logger.info(f"ZukuAgent initialized with provider: {self.provider}")

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
                logger.warning(f"Identity file {p} not found.")

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

        if self.provider == "openrouter" and self.history and self.history[0]["role"] == "system":
            self.history[0]["content"] = self.system_prompt
        if self.provider == "google":
            # Google chat sessions keep system instructions at session creation time.
            # Reset so the next request picks up the compressed prompt.
            self.chat_session = None

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
            self.google_aio_client = self.client.aio

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
            if self.chat_session is None:
                create_result = self.google_aio_client.chats.create(
                    model=self.model_name,
                    config=types.GenerateContentConfig(system_instruction=self.system_prompt),
                )
                self.chat_session = await create_result if inspect.isawaitable(create_result) else create_result
            send_result = self.chat_session.send_message(message)
            response = await send_result if inspect.isawaitable(send_result) else send_result
            response_text = response.text

        elif self.provider == "openrouter":
            self.history.append({"role": "user", "content": message})
            response_text = await self._chat_openrouter_with_tools()

        self._compress_skills_after_use()
        return response_text

    async def _chat_openrouter_with_tools(self) -> str:
        """Run one OpenRouter turn, resolving tool calls when requested."""
        max_tool_rounds = 3
        for _ in range(max_tool_rounds):
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=self.history,
                tools=self._openrouter_tools(),
                tool_choice="auto",
            )
            message = response.choices[0].message
            tool_calls = message.tool_calls or []

            if not tool_calls:
                response_text = message.content or ""
                self.history.append({"role": "assistant", "content": response_text})
                return response_text

            assistant_message = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in tool_calls
                ],
            }
            self.history.append(assistant_message)

            for tool_call in tool_calls:
                tool_payload = self._run_tool_call(tool_call.function.name, tool_call.function.arguments)
                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_payload),
                    }
                )

        msg = "Tool call loop exceeded the maximum number of rounds."
        raise RuntimeError(msg)

    def _openrouter_tools(self) -> list[dict]:
        """Return function tool definitions for OpenRouter."""
        return [
            {
                "type": "function",
                "function": {
                    "name": self.SANDBOX_TOOL_NAME,
                    "description": "Execute provided Python code in a Monty sandbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute inside the sandbox.",
                            },
                            "inputs": {
                                "type": "object",
                                "description": "Optional inputs available to the sandboxed program.",
                            },
                        },
                        "required": ["code"],
                    },
                },
            }
        ]

    def _run_tool_call(self, tool_name: str, arguments_json: str) -> dict[str, object]:
        """Execute a single tool call and return structured output."""
        if tool_name != self.SANDBOX_TOOL_NAME:
            return {"ok": False, "error": f"Unsupported tool: {tool_name}"}

        try:
            raw_args = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": f"Invalid tool arguments JSON: {exc}"}

        code = raw_args.get("code")
        if not isinstance(code, str) or not code.strip():
            return {"ok": False, "error": "Missing required string argument: code"}

        inputs = raw_args.get("inputs")
        if inputs is not None and not isinstance(inputs, dict):
            return {"ok": False, "error": "inputs must be an object if provided"}

        try:
            result = self.sandbox.run_code(code=code, inputs=inputs)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        output = result.output
        serialized_output = output if isinstance(output, str) else repr(output)

        return {
            "ok": True,
            "output": serialized_output,
            "duration_ms": round(result.duration_ms, 3),
        }

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
