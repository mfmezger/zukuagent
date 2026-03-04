"""Storage backends for runtime state files."""

import asyncio
from pathlib import Path

from loguru import logger

from zukuagent.core.settings import settings


class StorageBackend:
    """Async storage interface used by core runtime services."""

    async def exists(self, path: str) -> bool:
        """Return whether the given path exists."""
        msg = "Storage backend does not implement exists()."
        raise NotImplementedError(msg)

    async def read_text(self, path: str) -> str:
        """Read UTF-8 text content from path."""
        msg = "Storage backend does not implement read_text()."
        raise NotImplementedError(msg)

    async def write_text(self, path: str, content: str) -> None:
        """Write UTF-8 text content to path."""
        msg = "Storage backend does not implement write_text()."
        raise NotImplementedError(msg)


class LocalStorage(StorageBackend):
    """Local filesystem storage backend."""

    async def exists(self, path: str) -> bool:
        """Return whether the given local path exists."""
        return await asyncio.to_thread(Path(path).exists)

    async def read_text(self, path: str) -> str:
        """Read UTF-8 text from a local file."""
        return await asyncio.to_thread(Path(path).read_text, encoding="utf-8")

    async def write_text(self, path: str, content: str) -> None:
        """Write UTF-8 text to a local file, creating parent directories."""
        file_path = Path(path)
        await asyncio.to_thread(file_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(file_path.write_text, content, encoding="utf-8")


class AgentFsStorage(StorageBackend):
    """Turso AgentFS-backed storage.

    This backend is intentionally lazy: AgentFS is only opened when first used.
    """

    def __init__(self) -> None:
        """Initialize lazy AgentFS state."""
        self._agent = None
        self._lock = asyncio.Lock()

    def _normalize_path(self, path: str) -> str:
        candidate = path.replace("\\", "/")
        if not candidate.startswith("/"):
            candidate = f"/{candidate}"
        return candidate

    async def _ensure_agent(self) -> object:
        if self._agent is not None:
            return self._agent

        async with self._lock:
            if self._agent is not None:
                return self._agent

            try:
                from agentfs_sdk import AgentFS, AgentFSOptions
            except ImportError as exc:
                msg = "AGENT_STORAGE=agentfs requires `agentfs-sdk` to be installed."
                raise RuntimeError(msg) from exc

            options_kwargs: dict[str, str] = {}
            if settings.agentfs_id:
                options_kwargs["id"] = settings.agentfs_id
            if settings.agentfs_db_path:
                options_kwargs["path"] = settings.agentfs_db_path

            options = AgentFSOptions(**options_kwargs) if options_kwargs else AgentFSOptions()
            self._agent = await AgentFS.open(options)
            logger.info("Initialized AgentFS storage backend (id={}).", settings.agentfs_id)
            return self._agent

    async def exists(self, path: str) -> bool:
        """Return whether the given AgentFS path exists."""
        agent = await self._ensure_agent()
        normalized = self._normalize_path(path)
        try:
            await agent.fs.stat(normalized)
        except FileNotFoundError:
            return False
        except Exception:
            logger.exception("AgentFS stat failed for {}", normalized)
            return False
        return True

    async def read_text(self, path: str) -> str:
        """Read UTF-8 text from AgentFS."""
        agent = await self._ensure_agent()
        normalized = self._normalize_path(path)
        return await agent.fs.read_file(normalized)

    async def write_text(self, path: str, content: str) -> None:
        """Write UTF-8 text into AgentFS."""
        agent = await self._ensure_agent()
        normalized = self._normalize_path(path)
        await agent.fs.write_file(normalized, content)


def get_storage_backend() -> StorageBackend:
    """Build storage backend from settings."""
    storage_type = settings.agent_storage.lower()
    if storage_type == "local":
        return LocalStorage()
    if storage_type == "agentfs":
        return AgentFsStorage()
    msg = f"Unsupported AGENT_STORAGE value: {settings.agent_storage}. Use `local` or `agentfs`."
    raise ValueError(msg)
