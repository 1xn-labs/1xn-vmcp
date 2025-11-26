"""
Logging configuration for vMCP.

Provides structured logging with proper log levels (DEBUG, INFO, WARNING, ERROR).
Just clean, standard Python logging.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Union

from vmcp.config import settings


# ANSI escape codes for styling
class Style:
    """ANSI escape codes for terminal styling."""
    # Reset
    RESET = '\033[0m'

    # Text styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'

    # Colors (foreground)
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Background colors
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'


def syntax_highlight(text: str) -> str:
    """Apply syntax highlighting to debug log messages."""
    # Highlight strings (both single and double quoted)
    text = re.sub(
        r'(["\'])([^"\']*)\1',
        f'{Style.BRIGHT_GREEN}\\1\\2\\1{Style.RESET}',
        text
    )
    # Highlight numbers (standalone)
    text = re.sub(
        r'(?<![a-zA-Z0-9_])(\d+\.?\d*)(?![a-zA-Z0-9_])',
        f'{Style.BRIGHT_YELLOW}\\1{Style.RESET}',
        text
    )
    # Highlight True/False/None
    text = re.sub(
        r'\b(True|False|None)\b',
        f'{Style.BRIGHT_MAGENTA}\\1{Style.RESET}',
        text
    )
    # Highlight key= patterns (for kwargs)
    text = re.sub(
        r'\b([a-zA-Z_]\w*)=',
        f'{Style.BRIGHT_CYAN}\\1{Style.RESET}=',
        text
    )
    return text


# Custom formatter with colors for console
class ColoredFormatter(logging.Formatter):
    """Sexy formatter with colors, icons, and style for different log levels."""

    LEVEL_STYLES = {
        'DEBUG': {
            'icon': '🔍',
            'color': f'{Style.DIM}{Style.CYAN}',
            'label_color': f'{Style.BOLD}{Style.CYAN}',
        },
        'INFO': {
            'icon': '✨',
            'color': f'{Style.GREEN}',
            'label_color': f'{Style.BOLD}{Style.BRIGHT_GREEN}',
        },
        'WARNING': {
            'icon': '⚠️ ',
            'color': f'{Style.YELLOW}',
            'label_color': f'{Style.BOLD}{Style.BRIGHT_YELLOW}',
        },
        'ERROR': {
            'icon': '❌',
            'color': f'{Style.RED}',
            'label_color': f'{Style.BOLD}{Style.BRIGHT_RED}',
        },
        'CRITICAL': {
            'icon': '🔥',
            'color': f'{Style.BOLD}{Style.WHITE}{Style.BG_RED}',
            'label_color': f'{Style.BOLD}{Style.WHITE}{Style.BG_RED}',
        },
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with sexy colors and icons."""
        style = self.LEVEL_STYLES.get(record.levelname, {
            'icon': '•',
            'color': '',
            'label_color': '',
        })

        # Format timestamp
        timestamp = self.formatTime(record, self.datefmt)
        time_str = f"{Style.DIM}{Style.BRIGHT_BLACK}{timestamp}{Style.RESET}"

        # Format level with icon and color
        level_str = f"{style['icon']} {style['label_color']}{record.levelname:<8}{Style.RESET}"

        # Format logger name
        name_str = f"{Style.BOLD}{Style.BLUE}{record.name}{Style.RESET}"

        # Build the final formatted string
        separator = f"{Style.DIM}│{Style.RESET}"

        # Format message with level-appropriate color (and syntax highlighting for DEBUG)
        message = record.getMessage()
        if record.levelname in ("DEBUG", "CRITICAL", "ERROR"):
            # For DEBUG, apply syntax highlighting (no base color wrap to avoid conflicts)
            location = f" {Style.DIM}{record.filename}:{record.lineno}{Style.RESET}"
            msg_str = syntax_highlight(message)
        else:
            location = ""
            msg_str = f"{style['color']}{message}{Style.RESET}"

        return f"{time_str} {separator} {level_str} {separator} {name_str} {separator} {msg_str}{location}"


def _setup_logging(name: str = "vmcp", log_file: Optional[Path] = None) -> logging.Logger:
    """
    Setup logging configuration.

    Args:
        name: Logger name (typically module name)
        log_file: Optional file path for logging

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Prevent propagation to root logger to avoid duplicates
    # logger.propagate = False

    # Set level from settings (ensure uppercase for compatibility)
    log_level = settings.log_level.upper()
    logger.setLevel(log_level)



    # # Console handler with colors
    # console_handler = logging.StreamHandler(sys.stdout)
    # console_handler.setLevel(log_level)

    # # Use colored formatter for terminals, plain formatter otherwise
    # console_formatter: Union[ColoredFormatter, logging.Formatter]
    # if sys.stdout.isatty():  # Only use colors if output is a terminal
    #     console_formatter = ColoredFormatter(datefmt='%H:%M:%S')
    # else:
    #     console_formatter = logging.Formatter(
    #         '%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s',
    #         datefmt='%H:%M:%S'
    #     )

    # console_handler.setFormatter(console_formatter)
    # logger.addHandler(console_handler)

    # # File handler if specified
    # if log_file:
    #     log_file.parent.mkdir(parents=True, exist_ok=True)
    #     file_handler = logging.FileHandler(log_file)
    #     file_handler.setLevel(log_level)
    #     file_formatter = logging.Formatter(
    #         '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    #         datefmt='%Y-%m-%d %H:%M:%S'
    #     )
    #     file_handler.setFormatter(file_formatter)
    #     logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return _setup_logging(name)


def get_uvicorn_logging_config() -> dict:
    """
    Get logging configuration for uvicorn using the ColoredFormatter.

    Returns:
        Dictionary compatible with uvicorn's log_config parameter
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "colored": {
                "()": logging.Formatter,
                # "datefmt": "%H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "colored",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "formatter": "colored",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": settings.log_level.upper()},
            "uvicorn.access": {"handlers": ["access"], "level": settings.log_level.upper(), "propagate": False},
        },
    }


# Setup root logger
# root_logger = logging.getLogger("vmcp")
