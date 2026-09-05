import logging.config
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog
from pytz import utc


def setup_logging(config: Any) -> None:
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    log_dir = Path(config.LOG_DIR) if config.LOG_DIR else None
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)


    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    handlers: dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "colored" if config.ENVIRONMENT != "production" else "json",
            "level": log_level,
            "stream": sys.stdout,
        }
    }
    if log_dir:
        log_file = log_dir / f"app_{datetime.now(utc).strftime('%Y%m%d_%H%M%S')}.json"
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "json",
            "level": log_level,
            "filename": log_file,
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        }

    logging_config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "colored": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.dev.ConsoleRenderer(colors=True),
                "foreign_pre_chain": shared_processors,
            },
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
                "foreign_pre_chain": shared_processors,
            },
        },
        "handlers": handlers,
        "root": {"handlers": list(handlers.keys()), "level": log_level},
        "loggers": {
            "uvicorn.access": {"handlers": [], "propagate": False, "level": "WARNING"},
            "sqlalchemy.engine": {"level": "WARNING" if config.ENVIRONMENT == "production" else "INFO"},
        },
    }
    logging.config.dictConfig(logging_config)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
