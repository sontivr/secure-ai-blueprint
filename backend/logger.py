import logging
import os

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()

        formatter = logging.Formatter(
            "%(asctime)s level=%(levelname)s module=%(name)s message=\"%(message)s\""
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

        level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, level_name, logging.INFO))

    return logger
