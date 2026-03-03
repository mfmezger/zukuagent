import asyncio
from datetime import UTC, datetime

import pytest

from zukuagent.core.heartbeat import AgentHeartbeat


@pytest.mark.asyncio
async def test_cheap_checks_file_missing(tmp_path):
    hb = AgentHeartbeat(interval_minutes=1, heartbeat_file=str(tmp_path / "missing.md"))

    assert await hb._cheap_checks() is False


@pytest.mark.asyncio
async def test_cheap_checks_file_with_content(tmp_path):
    heartbeat_file = tmp_path / "HEARTBEAT.md"
    heartbeat_file.write_text("do this", encoding="utf-8")

    hb = AgentHeartbeat(interval_minutes=1, heartbeat_file=str(heartbeat_file))

    assert await hb._cheap_checks() is True


@pytest.mark.asyncio
async def test_cheap_checks_file_empty(tmp_path):
    heartbeat_file = tmp_path / "HEARTBEAT.md"
    heartbeat_file.write_text("   ", encoding="utf-8")

    hb = AgentHeartbeat(interval_minutes=1, heartbeat_file=str(heartbeat_file))

    assert await hb._cheap_checks() is False


@pytest.mark.asyncio
async def test_pulse_loop_without_escalation(monkeypatch):
    hb = AgentHeartbeat(interval_minutes=1, heartbeat_file="unused.md")
    events: list[str] = []

    async def fake_checks() -> bool:
        events.append("checks")
        hb.is_running = False
        return False

    async def fake_sleep(_seconds: float) -> None:
        events.append("sleep")

    hb.is_running = True
    monkeypatch.setattr(hb, "_cheap_checks", fake_checks)
    monkeypatch.setattr("zukuagent.core.heartbeat.asyncio.sleep", fake_sleep)

    await hb._pulse_loop()

    assert events == ["checks", "sleep"]


@pytest.mark.asyncio
async def test_pulse_loop_with_escalation(monkeypatch):
    hb = AgentHeartbeat(interval_minutes=1, heartbeat_file="unused.md")
    events: list[str] = []

    async def fake_checks() -> bool:
        events.append("checks")
        return True

    async def fake_trigger() -> None:
        events.append("trigger")

    async def fake_sleep(_seconds: float) -> None:
        events.append("sleep")
        hb.is_running = False

    hb.is_running = True
    monkeypatch.setattr(hb, "_cheap_checks", fake_checks)
    monkeypatch.setattr(hb, "_trigger_agent_action", fake_trigger)
    monkeypatch.setattr("zukuagent.core.heartbeat.asyncio.sleep", fake_sleep)

    await hb._pulse_loop()

    assert events == ["checks", "trigger", "sleep"]


@pytest.mark.asyncio
async def test_pulse_loop_handles_cancelled_error(monkeypatch):
    hb = AgentHeartbeat(interval_minutes=1, heartbeat_file="unused.md")

    async def fake_checks() -> bool:
        raise asyncio.CancelledError

    hb.is_running = True
    monkeypatch.setattr(hb, "_cheap_checks", fake_checks)

    await hb._pulse_loop()


@pytest.mark.asyncio
async def test_pulse_loop_handles_generic_error(monkeypatch):
    hb = AgentHeartbeat(interval_minutes=1, heartbeat_file="unused.md")
    calls = {"checks": 0, "sleep": 0}

    async def fake_checks() -> bool:
        calls["checks"] += 1
        if calls["checks"] == 1:
            raise RuntimeError("boom")
        hb.is_running = False
        return False

    async def fake_sleep(_seconds: float) -> None:
        calls["sleep"] += 1

    hb.is_running = True
    monkeypatch.setattr(hb, "_cheap_checks", fake_checks)
    monkeypatch.setattr("zukuagent.core.heartbeat.asyncio.sleep", fake_sleep)

    await hb._pulse_loop()

    assert calls == {"checks": 2, "sleep": 2}


@pytest.mark.asyncio
async def test_trigger_agent_action_placeholder():
    hb = AgentHeartbeat(interval_minutes=1, heartbeat_file="unused.md")

    await hb._trigger_agent_action()


@pytest.mark.asyncio
async def test_start_stop_and_status(monkeypatch):
    hb = AgentHeartbeat(interval_minutes=2, heartbeat_file="unused.md")

    class _FakeTask:
        cancelled = False

        def cancel(self) -> None:
            self.cancelled = True

    fake_task = _FakeTask()

    def fake_create_task(coro):
        coro.close()
        return fake_task

    monkeypatch.setattr("zukuagent.core.heartbeat.asyncio.create_task", fake_create_task)

    hb.start()
    hb.start()  # already running branch

    hb._last_pulse = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    status = hb.status

    assert status["running"] is True
    assert status["interval_minutes"] == 2
    assert status["last_pulse"] == "2026-01-02T03:04:05+00:00"

    hb.stop()
    assert fake_task.cancelled is True

    hb._task = None
    hb.stop()  # not running branch
