"""
Logging configuration for KubeMedic.

Provides structured logging with support for console and file output.

Environment Variables:
    LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               Default: INFO
    LOG_FILE: Path to log file (optional)
              Default: None (console only)
    LOG_FORMAT: Log format style ("simple" or "detailed")
                Default: detailed

Example:
    export LOG_LEVEL=DEBUG
    export LOG_FILE=logs/kube-medic.log
    export LOG_FORMAT=detailed
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from kube_medic.config import get_settings


# ============================================================================
# LOGGING LEVEL HELPERS
# ============================================================================

def _parse_log_level(level_str: str) -> int:
    """
    Parse log level from string.

    Args:
        level_str: Log level as string (e.g., 'DEBUG', 'INFO')

    Returns:
        Logging level constant

    Raises:
        ValueError: If invalid level string
    """
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
    }

    level_str = level_str.upper().strip()
    if level_str not in level_map:
        raise ValueError(
            f"Invalid log level '{level_str}'. "
            f"Must be one of: {', '.join(level_map.keys())}"
        )

    return level_map[level_str]


def _get_config_from_env() -> tuple:
    """
    Get logging configuration from environment variables.

    Returns:
        Tuple of (level, log_file, format_style)
    """
    # Get log level from environment or use default
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    try:
        level = _parse_log_level(log_level_str)
    except ValueError as e:
        print(f"Warning: {e}. Using INFO level.")
        level = logging.INFO

    # Get log file from environment (optional)
    log_file = os.getenv('LOG_FILE', None)

    # Get log format style from environment
    log_format = os.getenv('LOG_FORMAT', 'detailed')
    if log_format not in ('simple', 'detailed'):
        print(f"Warning: Invalid LOG_FORMAT '{log_format}'. Using 'detailed'.")
        log_format = 'detailed'

    return level, log_file, log_format


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(
    level: int = None,
    log_file: str = None,
    format_style: str = None,
) -> None:
    """
    Configure logging for the application.

    If arguments are not provided, they will be loaded from environment variables:
    - LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - LOG_FILE: Path to log file (optional)
    - LOG_FORMAT: Log format style ("simple" or "detailed")

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
               If None, loaded from LOG_LEVEL env var (default: INFO)
        log_file: Optional path to log file for file output
                  If None, loaded from LOG_FILE env var
        format_style: Log format style ("simple" or "detailed")
                      If None, loaded from LOG_FORMAT env var (default: detailed)
    """
    # Load from environment if not provided
    env_level, env_log_file, env_format = _get_config_from_env()

    if level is None:
        level = env_level
    if log_file is None:
        log_file = env_log_file
    if format_style is None:
        format_style = env_format

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Define formatters
    if format_style == "detailed":
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(name)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:  # simple
        formatter = logging.Formatter(
            fmt="%(levelname)-8s | %(message)s"
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# ============================================================================
# CONVENIENCE DECORATORS
# ============================================================================

def log_execution(logger: logging.Logger):
    """
    Decorator to log function execution.

    Usage:
        logger = get_logger(__name__)

        @log_execution(logger)
        def my_function():
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Executing {func.__name__}")
            try:
                result = func(*args, **kwargs)
                logger.debug(f"✓ {func.__name__} completed successfully")
                return result
            except Exception as e:
                logger.error(f"✗ {func.__name__} failed: {e}", exc_info=True)
                raise
        return wrapper
    return decorator


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    # Initialize logging
    setup_logging(level=logging.DEBUG, format_style="detailed")

    # Get loggers
    logger = get_logger(__name__)

    # Test different log levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

