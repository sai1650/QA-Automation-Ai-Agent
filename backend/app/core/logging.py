import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure console logging without including request or secret values."""
    normalized_level = getattr(logging, level.upper(), None)
    if not isinstance(normalized_level, int):
        raise ValueError(f"Invalid logging level: {level}")

    logging.basicConfig(
        level=normalized_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
