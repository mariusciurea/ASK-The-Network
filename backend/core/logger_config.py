"""Logging config"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.core.settings import settings


# One line per HTTP call, per model request and per internal step adds up fast.
NOISY_LIBRARIES = (
    "google_adk",
    "google.adk",
    "google_genai",
    "httpx",
    "httpcore",
    "urllib3",
    "matplotlib",
    "opentelemetry",
    "sqlalchemy.engine",
)


def _make_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )


def _make_file_handler(
    file_path: Path,
    level: int = logging.INFO,
) -> RotatingFileHandler:
    """Create file handler"""

    handler = RotatingFileHandler(
        file_path,
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(_make_formatter())
    return handler


def _make_console_handler(level: int = logging.INFO) -> logging.StreamHandler:
    """Create console handler"""

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(_make_formatter())
    return handler


def _quiet_noisy_libraries(level: int) -> None:
    """Raise the level of libraries that log one line per internal step.

    In production these produced hundreds of lines per agent turn and Railway
    started dropping messages ("rate limit of 500 logs/sec reached"), which
    takes the useful lines down with them.
    """

    for name in NOISY_LIBRARIES:
        logging.getLogger(name).setLevel(level)


def setup_logging() -> None:
    """Setup logging"""

    log_dir = Path(settings.WORKING_DIR) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    root_logger.addHandler(_make_console_handler())
    root_logger.addHandler(_make_file_handler(log_dir / "app.log"))

    _quiet_noisy_libraries(logging.getLevelNamesMapping().get(
        settings.LIBRARY_LOG_LEVEL.strip().upper(), logging.INFO
    ))

    # SQL command logger
    sql_command_logger = logging.getLogger("audit.sql.commands")
    sql_command_logger.setLevel(logging.INFO)
    sql_command_logger.handlers.clear()
    sql_command_logger.propagate = False
    sql_command_logger.addHandler(
        _make_file_handler(log_dir / "sql_commands.log")
    )

    # SQL result logger
    sql_result_logger = logging.getLogger("audit.sql.results")
    sql_result_logger.setLevel(logging.INFO)
    sql_result_logger.handlers.clear()
    sql_result_logger.propagate = False
    sql_result_logger.addHandler(
        _make_file_handler(log_dir / "sql_results.log")
    )

    # prompt logger
    user_prompt_logger = logging.getLogger("audit.user.prompts")
    user_prompt_logger.setLevel(logging.INFO)
    user_prompt_logger.handlers.clear()
    user_prompt_logger.propagate = False
    user_prompt_logger.addHandler(
        _make_file_handler(log_dir / "user_prompts.log")
    )
