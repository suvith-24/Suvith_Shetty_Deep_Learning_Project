
import logging

from lexisync.config import LOG_DIR


# Create log directory
LOG_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LOG_FILE = LOG_DIR / "lexisync.log"


def get_logger(name: str) -> logging.Logger:
    """
    Create a configured logger.

    Logs are written to both console and file.
    """

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
