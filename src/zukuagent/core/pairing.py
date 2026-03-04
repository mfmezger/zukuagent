"""Pairing registry for mapping Telegram chats to allowed device IDs."""

import asyncio
import json

from loguru import logger

from zukuagent.core.storage import StorageBackend, get_storage_backend


class PairingRegistry:
    """Persist and enforce chat-to-device pairing."""

    def __init__(
        self,
        storage_path: str,
        allowed_devices: list[str] | None = None,
        storage_backend: StorageBackend | None = None,
    ) -> None:
        """Initialize registry with storage path and optional allowed devices."""
        self.storage_path = storage_path
        self.storage_backend = storage_backend or get_storage_backend()
        self.allowed_devices = set(allowed_devices or [])
        self._chat_to_device: dict[int, str] = {}
        self._loaded = False
        self._load_lock = asyncio.Lock()

    async def get_device(self, chat_id: int) -> str | None:
        """Return paired device for a chat, if present."""
        await self._ensure_loaded()
        return self._chat_to_device.get(chat_id)

    def is_allowed_device(self, device_id: str) -> bool:
        """Check whether a device can be paired."""
        if not self.allowed_devices:
            return True
        return device_id in self.allowed_devices

    async def pair(self, chat_id: int, device_id: str) -> tuple[bool, str]:
        """Pair a chat with a device ID, enforcing allowlist and uniqueness."""
        await self._ensure_loaded()
        if not self.is_allowed_device(device_id):
            return False, "Device is not in the allowed pairing list."

        current = self._chat_to_device.get(chat_id)
        if current == device_id:
            return True, f"Already paired to `{device_id}`."

        owner = self._device_owner(device_id)
        if owner is not None and owner != chat_id:
            return False, "Device is already paired to another chat."

        self._chat_to_device[chat_id] = device_id
        await self._save()
        return True, f"Paired successfully with `{device_id}`."

    def _device_owner(self, device_id: str) -> int | None:
        for chat_id, paired_device in self._chat_to_device.items():
            if paired_device == device_id:
                return chat_id
        return None

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if self._loaded:
                return
            await self._load()
            self._loaded = True

    async def _load(self) -> None:
        if not await self.storage_backend.exists(self.storage_path):
            return

        try:
            payload_raw = await self.storage_backend.read_text(self.storage_path)
            payload = json.loads(payload_raw)
            chat_to_device = payload.get("chat_to_device", {})
            self._chat_to_device = {int(chat_id): str(device) for chat_id, device in chat_to_device.items()}
        except Exception:
            logger.exception("Failed to load pairing data from {}", self.storage_path)
            self._chat_to_device = {}

    async def _save(self) -> None:
        payload = {
            "chat_to_device": {str(chat_id): device for chat_id, device in self._chat_to_device.items()},
        }
        await self.storage_backend.write_text(
            self.storage_path,
            json.dumps(payload, indent=2, sort_keys=True),
        )
