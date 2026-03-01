"""Telegram endpoint integration for ZukuAgent."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from loguru import logger

from zukuagent.pairing import PairingRegistry
from zukuagent.settings import settings

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes

MessageHandler = Callable[[str], Awaitable[str]]


class TelegramEndpoint:
    """Expose ZukuAgent over Telegram chat."""

    def __init__(self, message_handler: MessageHandler) -> None:
        """Build Telegram application and configure access controls."""
        try:
            from telegram.ext import ApplicationBuilder
        except ImportError as exc:
            msg = "python-telegram-bot is required for Telegram endpoint support."
            raise RuntimeError(msg) from exc

        token = settings.telegram_bot_token
        if not token:
            msg = "Missing TELEGRAM_BOT_TOKEN"
            raise ValueError(msg)

        self.message_handler = message_handler
        self.allowed_chat_ids = set(settings.telegram_allowed_chat_ids)
        self.require_pairing = settings.telegram_require_pairing
        self.pairings = PairingRegistry(
            storage_path=settings.telegram_pairings_file,
            allowed_devices=settings.telegram_allowed_pairing_devices,
        )
        self.app = ApplicationBuilder().token(token.get_secret_value()).build()

    def register_handlers(self) -> None:
        """Attach Telegram command and message handlers."""
        from telegram.ext import CommandHandler, MessageHandler, filters

        self.app.add_handler(CommandHandler("start", self._on_start))
        self.app.add_handler(CommandHandler("pair", self._on_pair))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

    async def run(self) -> None:
        """Run Telegram bot in long-polling mode."""
        self.register_handlers()
        logger.info("Starting Telegram endpoint (polling mode).")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Stopping Telegram endpoint.")
        finally:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()

    async def _on_start(self, update: "Update", _context: "ContextTypes.DEFAULT_TYPE") -> None:
        if not self._is_chat_allowed(update.effective_chat.id):
            await update.message.reply_text("This chat is not allowed to use this bot.")
            return

        if self.require_pairing:
            await update.message.reply_text("Connected. Pair this chat with `/pair <device_id>` before sending messages.")
            return

        await update.message.reply_text("Connected. Send a message to start chatting.")

    async def _on_pair(self, update: "Update", context: "ContextTypes.DEFAULT_TYPE") -> None:
        chat_id = update.effective_chat.id
        if not self._is_chat_allowed(chat_id):
            await update.message.reply_text("This chat is not allowed to pair devices.")
            return

        if not context.args:
            await update.message.reply_text("Usage: /pair <device_id>")
            return

        device_id = context.args[0].strip()
        ok, message = self.pairings.pair(chat_id=chat_id, device_id=device_id)
        await update.message.reply_text(message)
        if ok:
            logger.info("Chat {} paired to device {}", chat_id, device_id)

    async def _on_message(self, update: "Update", _context: "ContextTypes.DEFAULT_TYPE") -> None:
        chat_id = update.effective_chat.id
        if not self._is_chat_allowed(chat_id):
            await update.message.reply_text("This chat is not allowed to use this bot.")
            return

        if self.require_pairing and not self.pairings.get_device(chat_id):
            await update.message.reply_text("Pair this chat first with `/pair <device_id>`.")
            return

        text = update.message.text or ""
        if not text.strip():
            return

        response = await self.message_handler(text)
        await update.message.reply_text(response)

    def _is_chat_allowed(self, chat_id: int) -> bool:
        if not self.allowed_chat_ids:
            return True
        return chat_id in self.allowed_chat_ids
