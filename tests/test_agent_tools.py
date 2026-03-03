from types import SimpleNamespace

import pytest

from zukuagent.core.agent import ZukuAgent
from zukuagent.core.settings import settings


@pytest.fixture
def stub_runtime_services(monkeypatch):
    monkeypatch.setattr("zukuagent.core.agent.ParakeetTranscriptionService", lambda: object())
    monkeypatch.setattr("zukuagent.core.agent.AgentHeartbeat", lambda *args, **kwargs: object())


def _tool_call(name: str, arguments: str, call_id: str = "call-1"):
    function = SimpleNamespace(name=name, arguments=arguments)

    class _ToolCall(SimpleNamespace):
        def model_dump(self):
            return {
                "id": self.id,
                "type": "function",
                "function": {
                    "name": self.function.name,
                    "arguments": self.function.arguments,
                },
            }

    return _ToolCall(
        id=call_id,
        function=function,
        type="function",
    )


def _openrouter_response(*, content: str | None, tool_calls: list | None = None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls,
                )
            )
        ]
    )


@pytest.mark.asyncio
async def test_openrouter_executes_sandbox_tool(monkeypatch, tmp_path, stub_runtime_services):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(ZukuAgent, "_find_project_root", lambda self: tmp_path)
    monkeypatch.setattr(settings, "identity_dir", ".")
    monkeypatch.setattr(settings, "identity_files", ["IDENTITY.md"])
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "IDENTITY.md").write_text("You are Zuku.", encoding="utf-8")

    agent = ZukuAgent(provider="openrouter")
    monkeypatch.setattr(
        agent.sandbox,
        "run_code",
        lambda code, inputs=None: SimpleNamespace(output=f"sum={inputs['x'] + inputs['y']}", duration_ms=1.234),
    )

    first = _openrouter_response(
        content=None,
        tool_calls=[
            _tool_call(
                name=agent.SANDBOX_TOOL_NAME,
                arguments='{"code":"x + y","inputs":{"x":2,"y":3}}',
            )
        ],
    )
    second = _openrouter_response(content="The sandbox result is 5.", tool_calls=None)
    responses = iter([first, second])

    async def fake_create(**_kwargs):
        return next(responses)

    monkeypatch.setattr(agent.client.chat.completions, "create", fake_create)

    text = await agent.chat("add these numbers")

    assert text == "The sandbox result is 5."
    tool_messages = [m for m in agent.history if m["role"] == "tool"]
    assert len(tool_messages) == 1
    assert '"ok": true' in tool_messages[0]["content"]
    assert "sum=5" in tool_messages[0]["content"]


def test_run_tool_call_rejects_invalid_inputs(monkeypatch, tmp_path, stub_runtime_services):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(ZukuAgent, "_find_project_root", lambda self: tmp_path)
    monkeypatch.setattr(settings, "identity_dir", ".")
    monkeypatch.setattr(settings, "identity_files", ["IDENTITY.md"])
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    (tmp_path / "IDENTITY.md").write_text("You are Zuku.", encoding="utf-8")

    agent = ZukuAgent(provider="openrouter")

    bad_json = agent._run_tool_call(agent.SANDBOX_TOOL_NAME, "{not-json")
    assert bad_json["ok"] is False
    assert "Invalid tool arguments JSON" in bad_json["error"]

    bad_inputs = agent._run_tool_call(agent.SANDBOX_TOOL_NAME, '{"code":"1 + 1","inputs":[1,2]}')
    assert bad_inputs["ok"] is False
    assert "inputs must be an object" in bad_inputs["error"]
