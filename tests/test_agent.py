"""Snapshot and recording tests for ZukuAgent.

This module demonstrates the use of:
1. pytest-recording (via @pytest.mark.vcr) for capturing network requests.
2. inline-snapshot for asserting data structures.
3. dirty-equals for flexible matching of dynamic values (IDs, timestamps).
"""

import pytest
from inline_snapshot import snapshot
from dirty_equals import IsStr, IsInt, IsNow, IsUUID
from zukuagent.core.agent import ZukuAgent
from zukuagent.core.settings import settings


@pytest.fixture
def stub_runtime_services(monkeypatch):
    monkeypatch.setattr("zukuagent.core.agent.ParakeetTranscriptionService", lambda: object())
    monkeypatch.setattr("zukuagent.core.agent.AgentHeartbeat", lambda *args, **kwargs: object())


def test_loads_skills_into_system_prompt(tmp_path, monkeypatch, stub_runtime_services):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(ZukuAgent, "_find_project_root", lambda self: tmp_path)
    monkeypatch.setattr(settings, "identity_dir", ".")
    monkeypatch.setattr(settings, "identity_files", ["IDENTITY.md"])

    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "IDENTITY.md").write_text("You are Zuku.", encoding="utf-8")
    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    marker_text = "VERY LONG SKILL INSTRUCTION THAT SHOULD BE COMPRESSED LATER."
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

    agent = ZukuAgent(provider="openrouter")

    assert "Loaded Skills Context" in agent.system_prompt
    assert marker_text in agent.system_prompt
    assert agent.skills_compressed is False


def test_compresses_skills_after_use(tmp_path, monkeypatch, stub_runtime_services):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(ZukuAgent, "_find_project_root", lambda self: tmp_path)
    monkeypatch.setattr(settings, "identity_dir", ".")
    monkeypatch.setattr(settings, "identity_files", ["IDENTITY.md"])

    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "IDENTITY.md").write_text("You are Zuku.", encoding="utf-8")
    skill_dir = tmp_path / "skills" / "demo-skill"
    skill_dir.mkdir(parents=True)
    marker_text = "VERY LONG SKILL INSTRUCTION THAT SHOULD BE COMPRESSED LATER."
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

    agent = ZukuAgent(provider="openrouter")
    original_prompt = agent.system_prompt
    agent._compress_skills_after_use()

    assert agent.skills_compressed is True
    assert "Compressed Skills Context" in agent.system_prompt
    assert len(agent.system_prompt) < len(original_prompt)
    assert "name: demo-skill" not in agent.system_prompt
    assert "Skill `demo-skill`." in agent.system_prompt
    assert agent.history[0]["content"] == agent.system_prompt

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_agent_initialization(monkeypatch):
    """Test ZukuAgent initialization with mocked environment.

    This will be recorded in a cassette (vcrpy).
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    agent = ZukuAgent(provider="google")

    assert agent.provider == snapshot("google")
    assert agent.model_name == settings.google_model

def test_pydantic_snapshot_demo():
    """Demonstrate snapshotting a structure with dynamic fields.

    Run `pytest --inline-snapshot=fix` to automatically update the snapshot.
    """
    # Example data similar to what a Pydantic model might produce
    response_data = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "created_at": "2026-03-01T12:00:00Z",
        "role": "assistant",
        "content": "Hello! I am ZukuAgent.",
        "tokens_used": 42
    }

    # After running with --inline-snapshot=fix, it would look like this:
    assert response_data == snapshot({
        "id": IsUUID,
        "created_at": IsStr,  # Or IsNow() if it's current
        "role": "assistant",
        "content": "Hello! I am ZukuAgent.",
        "tokens_used": IsInt
    })

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_agent_chat_recording_example(monkeypatch):
    """This test would record real API calls if GOOGLE_API_KEY was present.

    To record:
    1. Set export GOOGLE_API_KEY=your-key
    2. Run: uv run pytest --record-mode=once
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    # agent = ZukuAgent(provider="google")
    # response = await agent.chat("ping")
    # assert response == snapshot("pong")
    pass
