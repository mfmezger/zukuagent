"""Langfuse tracing integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from zukuagent.core.settings import settings

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - optional runtime dependency fallback
    Langfuse = None


@dataclass
class LangfuseTraceContext:
    """Container for Langfuse trace objects used during a chat turn."""

    trace: Any | None = None
    generation: Any | None = None


class LangfuseTracingService:
    """Optional tracing service that records agent chat turns in Langfuse."""

    def __init__(self) -> None:
        """Initialize an optional Langfuse client from runtime settings."""
        self.enabled = bool(settings.langfuse_enabled)
        self.client: Any | None = None

        if not self.enabled:
            return

        if Langfuse is None:
            logger.warning("LANGFUSE_ENABLED is true but langfuse package is not installed. Tracing is disabled.")
            self.enabled = False
            return

        if not settings.langfuse_public_key or not settings.langfuse_secret_key:
            logger.warning("LANGFUSE_ENABLED is true but public/secret key is missing. Tracing is disabled.")
            self.enabled = False
            return

        try:
            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            logger.info("Langfuse tracing enabled with host: {}", settings.langfuse_host)
        except Exception:
            logger.exception("Failed to initialize Langfuse client. Tracing is disabled.")
            self.enabled = False
            self.client = None

    def start_chat_trace(self, *, provider: str, model: str, message: str) -> LangfuseTraceContext:
        """Create a Langfuse trace + generation for a chat turn."""
        if not self.enabled or self.client is None:
            return LangfuseTraceContext()

        try:
            trace = self.client.trace(
                name="zukuagent.chat",
                input={"message": message},
                metadata={"provider": provider},
            )
            generation = trace.generation(
                name="llm-chat",
                model=model,
                input={"message": message},
                metadata={"provider": provider},
            )
            return LangfuseTraceContext(trace=trace, generation=generation)
        except Exception:
            logger.exception("Failed to start Langfuse trace for chat turn.")
            return LangfuseTraceContext()

    def end_chat_trace(
        self,
        context: LangfuseTraceContext,
        *,
        output: str,
        error: Exception | None = None,
    ) -> None:
        """Finalize a Langfuse generation and flush asynchronously."""
        if not context.generation:
            return

        try:
            if error is None:
                context.generation.update(output=output)
            else:
                context.generation.update(output=f"[ERROR] {error}")
        except Exception:
            logger.exception("Failed to finalize Langfuse trace for chat turn.")
        finally:
            try:
                self.flush()
            except Exception:
                logger.exception("Failed to flush Langfuse events.")

    def flush(self) -> None:
        """Flush pending events to Langfuse."""
        if self.enabled and self.client is not None:
            self.client.flush()
