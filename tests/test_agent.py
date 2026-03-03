"""Tests for ZukuAgent runtime and skill prompt behavior."""

from dataclasses import dataclass

import pytest
from inline_snapshot import snapshot

from zukuagent.core.agent import ZukuAgent
from zukuagent.core.settings import settings


@dataclass
class _FakeGoogleResponse:
    text: str


class _FakeGoogleChatSession:
    async def send_message(self, message: str):
        return _FakeGoogleResponse(text=f"google:{message}")


class _FakeGoogleChats:
    def __init__(self) -> None:
        self.create_calls = 0

    async def create(self, **_kwargs):
        self.create_calls += 1
        return _FakeGoogleChatSession()


class _FakeGoogleAio:
    def __init__(self) -> None:
        self.chats = _FakeGoogleChats()


class _FakeGoogleClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.aio = _FakeGoogleAio()


class _FakeOpenAIChoiceMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeOpenAIChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeOpenAIChoiceMessage(content)


class _FakeOpenAIResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeOpenAIChoice(content)]


class _FakeOpenAICompletions:
    def __init__(self, owner: "_FakeOpenAIClient") -> None:
        self.owner = owner

    async def create(self, *, model: str, messages: list[dict[str, str]]):
        self.owner.calls.append({"model": model, "messages": messages[:]})
        return _FakeOpenAIResponse("local final response")


class _FakeOpenAIChat:
    def __init__(self, owner: "_FakeOpenAIClient") -> None:
        self.completions = _FakeOpenAICompletions(owner)


class _FakeOpenAIClient:
    def __init__(self, **_kwargs) -> None:
        self.calls: list[dict[str, object]] = []
        self.chat = _FakeOpenAIChat(self)


class _FakeTracingService:
    def __init__(self) -> None:
        self.flushed = 0

    def flush(self) -> None:
        self.flushed += 1


@pytest.fixture
def stub_runtime_services(monkeypatch):
    monkeypatch.setattr("zukuagent.core.agent.ParakeetTranscriptionService", lambda: object())
    monkeypatch.setattr("zukuagent.core.agent.AgentHeartbeat", lambda *args, **kwargs: object())
    monkeypatch.setattr("zukuagent.core.agent.OpenlitTracingService", _FakeTracingService)


@pytest.fixture
def stub_google_client(monkeypatch):
    monkeypatch.setattr("zukuagent.core.agent.genai.Client", _FakeGoogleClient)


@pytest.fixture
def stub_openai_client(monkeypatch):
    monkeypatch.setattr("zukuagent.core.agent.AsyncOpenAI", _FakeOpenAIClient)


def _prepare_identity_and_skill(tmp_path, marker_text: str) -> None:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "IDENTITY.md").write_text("You are Zuku.", encoding="utf-8")
    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    skill_dir.joinpath("SKILL.md").write_text(
        f"""---
name: demo-skill
description: Demo skill for tests
---

# Demo Skill
{marker_text}
Step 1: Do the thing.
Step 2: Verify the thing.
""",
        encoding="utf-8",
    )


def test_loads_skills_into_system_prompt(tmp_path, monkeypatch, stub_runtime_services, stub_google_client):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(ZukuAgent, "_find_project_root", lambda self: tmp_path)
    monkeypatch.setattr(settings, "identity_dir", ".")
    monkeypatch.setattr(settings, "identity_files", ["IDENTITY.md"])

    marker_text = "VERY LONG SKILL INSTRUCTION THAT SHOULD BE COMPRESSED LATER."
    _prepare_identity_and_skill(tmp_path, marker_text)

    agent = ZukuAgent(provider="google")

    assert "Loaded Skills Context" in agent.system_prompt
    assert marker_text in agent.system_prompt
    assert agent.skills_compressed is False


def test_compresses_skills_after_use(tmp_path, monkeypatch, stub_runtime_services, stub_google_client):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(ZukuAgent, "_find_project_root", lambda self: tmp_path)
    monkeypatch.setattr(settings, "identity_dir", ".")
    monkeypatch.setattr(settings, "identity_files", ["IDENTITY.md"])

    marker_text = "VERY LONG SKILL INSTRUCTION THAT SHOULD BE COMPRESSED LATER."
    _prepare_identity_and_skill(tmp_path, marker_text)

    agent = ZukuAgent(provider="google")
    agent.chat_session = object()
    original_prompt = agent.system_prompt
    agent._compress_skills_after_use()

    assert agent.skills_compressed is True
    assert "Compressed Skills Context" in agent.system_prompt
    assert len(agent.system_prompt) < len(original_prompt)
    assert "name: demo-skill" not in agent.system_prompt
    assert "Skill `demo-skill`." in agent.system_prompt
    assert agent.chat_session is None


@pytest.mark.asyncio
async def test_agent_initialization(monkeypatch, stub_runtime_services, stub_google_client):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    agent = ZukuAgent(provider="google")

    assert agent.provider == snapshot("google")
    assert agent.model_name == settings.google_model


@pytest.mark.asyncio
async def test_chat_uses_google_runtime(monkeypatch, stub_runtime_services, stub_google_client):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    agent = ZukuAgent(provider="google")

    reply = await agent.chat("ping")

    assert reply == "google:ping"


@pytest.mark.asyncio
async def test_google_chat_session_created_once(monkeypatch, stub_runtime_services, stub_google_client):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    agent = ZukuAgent(provider="google")

    await agent.chat("first")
    await agent.chat("second")

    assert agent.google_aio_client.chats.create_calls == 1


@pytest.mark.asyncio
async def test_chat_uses_openai_local_runtime(monkeypatch, stub_runtime_services, stub_openai_client):
    monkeypatch.setattr(settings, "openai_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(settings, "openai_model", "llama3.2")
    agent = ZukuAgent(provider="openai-local")

    reply = await agent.chat("ping")

    assert reply == "local final response"
    assert agent._openai_messages[0]["role"] == "system"
    assert agent._openai_client.calls[0]["model"] == "llama3.2"


def test_compress_updates_openai_system_message(tmp_path, monkeypatch, stub_runtime_services, stub_openai_client):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ZukuAgent, "_find_project_root", lambda self: tmp_path)
    monkeypatch.setattr(settings, "identity_dir", ".")
    monkeypatch.setattr(settings, "identity_files", ["IDENTITY.md"])
    monkeypatch.setattr(settings, "openai_base_url", "http://localhost:11434/v1")
    _prepare_identity_and_skill(tmp_path, "LONG SKILL INSTRUCTIONS")
    agent = ZukuAgent(provider="openai-local")

    original = agent._openai_messages[0]["content"]
    agent._compress_skills_after_use()

    assert agent._openai_messages[0]["role"] == "system"
    assert agent._openai_messages[0]["content"] == agent.system_prompt
    assert agent._openai_messages[0]["content"] != original
