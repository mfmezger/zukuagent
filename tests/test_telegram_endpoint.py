from types import SimpleNamespace

import pytest

import zukuagent.endpoints.telegram as telegram_module
from zukuagent.endpoints.telegram import TelegramEndpoint


class _Filter:
    def __and__(self, _other):
        return self

    def __invert__(self):
        return self


class _FakeUpdater:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start_polling(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


class _FakeApp:
    def __init__(self) -> None:
        self.handlers = []
        self.updater = _FakeUpdater()
        self.initialized = False
        self.started = False
        self.stopped = False
        self.shutdown_called = False

    def add_handler(self, handler) -> None:
        self.handlers.append(handler)

    async def initialize(self) -> None:
        self.initialized = True

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def shutdown(self) -> None:
        self.shutdown_called = True


class _FakeApplicationBuilder:
    def __init__(self) -> None:
        self._token = None
        self._app = _FakeApp()

    def token(self, token: str):
        self._token = token
        return self

    def build(self) -> _FakeApp:
        return self._app


class _FakeMessage:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, message: str) -> None:
        self.replies.append(message)


class _FakeUpdate:
    def __init__(self, chat_id: int, text: str | None = None) -> None:
        self.effective_chat = SimpleNamespace(id=chat_id)
        self.message = _FakeMessage(text=text)


class _FakeContext:
    def __init__(self, args: list[str] | None = None) -> None:
        self.args = args or []


@pytest.fixture
def fake_telegram_api(monkeypatch):
    fake_builder = _FakeApplicationBuilder()
    monkeypatch.setattr(telegram_module, "ApplicationBuilder", lambda: fake_builder)
    monkeypatch.setattr(telegram_module, "CommandHandler", lambda command, callback: ("command", command, callback))
    monkeypatch.setattr(telegram_module, "TelegramMessageHandler", lambda _filter, callback: ("message", callback))
    monkeypatch.setattr(telegram_module, "filters", SimpleNamespace(TEXT=_Filter(), COMMAND=_Filter()))
    return fake_builder


@pytest.fixture
def endpoint(monkeypatch, tmp_path, fake_telegram_api):
    monkeypatch.setattr(telegram_module.settings, "telegram_bot_token", "token-123")
    monkeypatch.setattr(telegram_module.settings, "telegram_allowed_chat_ids", [100])
    monkeypatch.setattr(telegram_module.settings, "telegram_require_pairing", True)
    monkeypatch.setattr(telegram_module.settings, "telegram_pairings_file", str(tmp_path / "pairings.json"))
    monkeypatch.setattr(telegram_module.settings, "telegram_allowed_pairing_devices", ["dev-1"])

    async def handler(message: str) -> str:
        return f"echo:{message}"

    return TelegramEndpoint(message_handler=handler)


def test_constructor_requires_telegram_dependency(monkeypatch):
    monkeypatch.setattr(telegram_module, "ApplicationBuilder", None)

    async def handler(_message: str) -> str:
        return "ok"

    with pytest.raises(RuntimeError, match="python-telegram-bot"):
        TelegramEndpoint(message_handler=handler)


def test_constructor_requires_token(monkeypatch, fake_telegram_api):
    monkeypatch.setattr(telegram_module.settings, "telegram_bot_token", None)

    async def handler(_message: str) -> str:
        return "ok"

    with pytest.raises(ValueError, match="Missing TELEGRAM_BOT_TOKEN"):
        TelegramEndpoint(message_handler=handler)


def test_register_handlers(endpoint):
    endpoint.register_handlers()

    assert len(endpoint.app.handlers) == 3
    assert endpoint.app.handlers[0][0] == "command"
    assert endpoint.app.handlers[1][0] == "command"
    assert endpoint.app.handlers[2][0] == "message"


def test_register_handlers_requires_telegram_dependency(endpoint, monkeypatch):
    monkeypatch.setattr(telegram_module, "CommandHandler", None)

    with pytest.raises(RuntimeError, match="python-telegram-bot"):
        endpoint.register_handlers()


@pytest.mark.asyncio
async def test_run_starts_and_stops_app(endpoint, monkeypatch):
    class _InterruptingEvent:
        async def wait(self):
            raise KeyboardInterrupt

    fake_asyncio = SimpleNamespace(Event=lambda: _InterruptingEvent())
    monkeypatch.setattr(telegram_module, "asyncio", fake_asyncio)

    await endpoint.run()

    assert endpoint.app.initialized is True
    assert endpoint.app.started is True
    assert endpoint.app.updater.started is True
    assert endpoint.app.updater.stopped is True
    assert endpoint.app.stopped is True
    assert endpoint.app.shutdown_called is True


@pytest.mark.asyncio
async def test_on_start_rejects_disallowed_chat(endpoint):
    update = _FakeUpdate(chat_id=999)

    await endpoint._on_start(update, _FakeContext())

    assert update.message.replies == ["This chat is not allowed to use this bot."]


@pytest.mark.asyncio
async def test_on_start_pairing_required(endpoint):
    update = _FakeUpdate(chat_id=100)

    await endpoint._on_start(update, _FakeContext())

    assert update.message.replies == ["Connected. Pair this chat with `/pair <device_id>` before sending messages."]


@pytest.mark.asyncio
async def test_on_start_without_pairing(monkeypatch, endpoint):
    monkeypatch.setattr(endpoint, "require_pairing", False)
    update = _FakeUpdate(chat_id=100)

    await endpoint._on_start(update, _FakeContext())

    assert update.message.replies == ["Connected. Send a message to start chatting."]


@pytest.mark.asyncio
async def test_on_pair_paths(endpoint, monkeypatch):
    disallowed = _FakeUpdate(chat_id=999)
    await endpoint._on_pair(disallowed, _FakeContext(args=["dev-1"]))
    assert disallowed.message.replies == ["This chat is not allowed to pair devices."]

    missing_args = _FakeUpdate(chat_id=100)
    await endpoint._on_pair(missing_args, _FakeContext(args=[]))
    assert missing_args.message.replies == ["Usage: /pair <device_id>"]

    monkeypatch.setattr(endpoint.pairings, "pair", lambda chat_id, device_id: (True, f"Paired {chat_id} {device_id}"))
    ok_update = _FakeUpdate(chat_id=100)
    await endpoint._on_pair(ok_update, _FakeContext(args=["dev-1"]))
    assert ok_update.message.replies == ["Paired 100 dev-1"]


@pytest.mark.asyncio
async def test_on_message_paths(endpoint, monkeypatch):
    disallowed = _FakeUpdate(chat_id=999, text="hello")
    await endpoint._on_message(disallowed, _FakeContext())
    assert disallowed.message.replies == ["This chat is not allowed to use this bot."]

    unpaired = _FakeUpdate(chat_id=100, text="hello")
    monkeypatch.setattr(endpoint.pairings, "get_device", lambda _chat_id: None)
    await endpoint._on_message(unpaired, _FakeContext())
    assert unpaired.message.replies == ["Pair this chat first with `/pair <device_id>`." ]

    blank = _FakeUpdate(chat_id=100, text="   ")
    monkeypatch.setattr(endpoint.pairings, "get_device", lambda _chat_id: "dev-1")
    await endpoint._on_message(blank, _FakeContext())
    assert blank.message.replies == []

    normal = _FakeUpdate(chat_id=100, text="ping")
    await endpoint._on_message(normal, _FakeContext())
    assert normal.message.replies == ["echo:ping"]


def test_is_chat_allowed(endpoint, monkeypatch):
    monkeypatch.setattr(endpoint, "allowed_chat_ids", set())
    assert endpoint._is_chat_allowed(1) is True

    monkeypatch.setattr(endpoint, "allowed_chat_ids", {1, 2})
    assert endpoint._is_chat_allowed(2) is True
    assert endpoint._is_chat_allowed(3) is False
