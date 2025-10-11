import logging
import os
from pathlib import Path

from dotenv import load_dotenv

try:
    from pythonjsonlogger import jsonlogger
    HAS_JSON_LOGGER = True
except ImportError:
    HAS_JSON_LOGGER = False

# Load environment variables
load_dotenv()


class CustomFormatter(logging.Formatter):
    """Custom formatter for colored console logs."""

    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_str = "[%(asctime)s] %(levelname)s {%(filename)s:%(lineno)d} - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: blue + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def configure_logger(level: str = "INFO", log_file: str = None) -> None:
    """
    Configure the logger based on environment variables and parameters.
    
    Args:
        level: The log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
    """
    level = os.getenv("LOG_LEVEL", level).upper()
    log_format = os.getenv("LOG_MESSAGES_FORMAT", "text").lower()

    # Get the root logger
    logger = logging.getLogger()
    
    # Remove all handlers to avoid duplicate logging
    for handler in logger.handlers:
        logger.removeHandler(handler)

    logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    
    # Decide format based on LOG_MESSAGES_FORMAT env variable
    if log_format == "json" and HAS_JSON_LOGGER:
        formatter = jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s %(filename)s %(lineno)d',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = CustomFormatter()

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s {%(filename)s:%(lineno)d} - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Configure third-party loggers
    third_party_loggers = ["openai", "selenium", "urllib3", "helium"]
    for lib_logger_name in third_party_loggers:
        lib_logger = logging.getLogger(lib_logger_name)
        lib_logger.setLevel(logging.WARNING)

    # Suppress noisy loggers
    logging.getLogger("matplotlib.pyplot").setLevel(logging.WARNING)
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)
    logging.getLogger("PIL.Image").setLevel(logging.WARNING)


def set_log_level(level: str) -> None:
    """
    Set the log level for the logger.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    configure_logger(level)


# Initialize logger on module import
configure_logger()
