import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_langfuse_client: Any | None = None
_langfuse_enabled = False
_langfuse_initialized = False


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def configure_langfuse(service_name: str = "fin-pdf-agent") -> bool:
    """Initialize Langfuse + OpenAI Agents instrumentation if credentials exist."""
    global _langfuse_client, _langfuse_enabled, _langfuse_initialized

    if _langfuse_initialized:
        return _langfuse_enabled

    _langfuse_initialized = True

    base_url = os.getenv("LANGFUSE_BASE_URL", "").strip()
    if base_url and not os.getenv("LANGFUSE_HOST"):
        os.environ["LANGFUSE_HOST"] = base_url

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    host = os.getenv("LANGFUSE_HOST", "").strip()
    if not (public_key and secret_key and host):
        logger.info("Langfuse tracing is disabled because credentials are incomplete.")
        return False

    try:
        import logfire
        from langfuse import get_client

        logfire.configure(service_name=service_name, send_to_logfire=False)
        logfire.instrument_openai_agents()

        _langfuse_client = get_client()
        _langfuse_enabled = True
    except Exception:
        logger.exception("Failed to initialize Langfuse tracing.")
        _langfuse_client = None
        _langfuse_enabled = False
        return False

    if _env_flag("LANGFUSE_AUTH_CHECK_ON_STARTUP"):
        try:
            if not _langfuse_client.auth_check():
                logger.warning("Langfuse auth check failed. Traces may not be exported.")
        except Exception:
            logger.exception("Langfuse auth check failed.")

    logger.info("Langfuse tracing is enabled for OpenAI Agents.")
    return True


def get_langfuse_client() -> Any | None:
    return _langfuse_client if _langfuse_enabled else None


def is_langfuse_enabled() -> bool:
    return _langfuse_enabled


def flush_langfuse() -> None:
    if _langfuse_client is None:
        return

    try:
        _langfuse_client.flush()
    except Exception:
        logger.exception("Failed to flush Langfuse events.")
