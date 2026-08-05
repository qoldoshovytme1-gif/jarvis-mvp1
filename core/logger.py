"""
Logging System
================
Centralized logger factory. Every module gets its own named logger
(so log lines show exactly which module — Planner, Executor,
Verifier, etc. — produced them) but all share the same format,
level, and output targets (console + rotating file).

Usage:
    from core.logger import get_logger
    log = get_logger(__name__)
    log.info("Plan created with %d steps", len(plan.steps))
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from core.config import get_config

_CONFIGURED = False


def _configure_root_logger():
    global _CONFIGURED
    if _CONFIGURED:
        return

    config = get_config()
    os.makedirs(os.path.dirname(config.log_file), exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        config.log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger("jarvis")
    root.setLevel(config.log_level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Returns a namespaced logger under the shared 'jarvis' root, e.g.
    'jarvis.core.planner'. Call this at module level in every file:
        log = get_logger(__name__)
    """
    _configure_root_logger()
    return logging.getLogger(f"jarvis.{name}")
