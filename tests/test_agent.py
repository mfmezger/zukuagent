"""Snapshot and recording tests for ZukuAgent.

This module demonstrates the use of:
1. pytest-recording (via @pytest.mark.vcr) for capturing network requests.
2. inline-snapshot for asserting data structures.
3. dirty-equals for flexible matching of dynamic values (IDs, timestamps).
"""

import pytest
from inline_snapshot import snapshot
from dirty_equals import IsStr, IsInt, IsNow, IsUUID
from zukuagent.agent import ZukuAgent

@pytest.mark.asyncio
@pytest.mark.vcr
async def test_agent_initialization(monkeypatch):
    """Test ZukuAgent initialization with mocked environment.

    This will be recorded in a cassette (vcrpy).
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    agent = ZukuAgent(provider="google")

    assert agent.provider == snapshot("google")
    assert agent.model_name == snapshot("gemini-1.5-flash")

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
