"""OpenLIT tracing integration."""

from __future__ import annotations

from loguru import logger

from zukuagent.core.settings import settings

try:
    import openlit
except ImportError:  # pragma: no cover - optional runtime dependency fallback
    openlit = None


class OpenlitTracingService:
    """Optional tracing service that configures OpenLIT auto-instrumentation."""

    def __init__(self) -> None:
        """Initialize optional OpenLIT instrumentation from runtime settings."""
        self.enabled = bool(settings.openlit_enabled)

        if not self.enabled:
            return

        if openlit is None:
            logger.warning("OPENLIT_ENABLED is true but openlit package is not installed. Tracing is disabled.")
            self.enabled = False
            return

        try:
            openlit.init(otlp_endpoint=settings.openlit_otlp_endpoint)
            logger.info("OpenLIT tracing enabled with OTLP endpoint: {}", settings.openlit_otlp_endpoint)
        except Exception:
            logger.exception("Failed to initialize OpenLIT instrumentation. Tracing is disabled.")
            self.enabled = False

    def start_chat_trace(self, *, provider: str, model: str, message: str) -> dict[str, str]:
        """No-op method kept for compatibility with existing chat instrumentation."""
        return {"provider": provider, "model": model, "message": message}

    def end_chat_trace(self, context: object, *, output: str, error: Exception | None = None) -> None:
        """No-op method kept for compatibility with existing chat instrumentation."""
        _ = (context, output, error)

    def flush(self) -> None:
        """Flush pending events when OpenLIT exposes a flush hook."""
        if not self.enabled or openlit is None:
            return
        flush_fn = getattr(openlit, "flush", None)
        if callable(flush_fn):
            flush_fn()
