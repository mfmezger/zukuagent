import asyncio
import sys

import zukuagent


class _FakeAgent:
    last_init: tuple[str | None, str | None] | None = None
    run_called = False

    def __init__(self, provider=None, model_name=None):
        type(self).last_init = (provider, model_name)

    async def run(self):
        type(self).run_called = True

    async def chat(self, _message: str) -> str:
        return "ok"


class _FakeTelegramEndpoint:
    last_handler = None
    run_called = False

    def __init__(self, message_handler):
        type(self).last_handler = message_handler

    async def run(self):
        type(self).run_called = True


def _run_coroutine(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_main_runs_cli_mode(monkeypatch):
    _FakeAgent.last_init = None
    _FakeAgent.run_called = False

    monkeypatch.setattr(zukuagent, "ZukuAgent", _FakeAgent)
    monkeypatch.setattr(zukuagent, "TelegramEndpoint", _FakeTelegramEndpoint)
    monkeypatch.setattr(zukuagent.asyncio, "run", _run_coroutine)
    monkeypatch.setattr(sys, "argv", ["zukuagent", "--endpoint", "cli", "--provider", "openai", "--model", "m1"])

    zukuagent.main()

    assert _FakeAgent.last_init == ("openai", "m1")
    assert _FakeAgent.run_called is True


def test_main_runs_telegram_mode(monkeypatch):
    _FakeAgent.last_init = None
    _FakeAgent.run_called = False
    _FakeTelegramEndpoint.last_handler = None
    _FakeTelegramEndpoint.run_called = False

    monkeypatch.setattr(zukuagent, "ZukuAgent", _FakeAgent)
    monkeypatch.setattr(zukuagent, "TelegramEndpoint", _FakeTelegramEndpoint)
    monkeypatch.setattr(zukuagent.asyncio, "run", _run_coroutine)
    monkeypatch.setattr(sys, "argv", ["zukuagent", "--endpoint", "telegram", "--provider", "google", "--model", "g1"])

    zukuagent.main()

    assert _FakeAgent.last_init == ("google", "g1")
    assert _FakeTelegramEndpoint.run_called is True
    assert _FakeTelegramEndpoint.last_handler is not None
