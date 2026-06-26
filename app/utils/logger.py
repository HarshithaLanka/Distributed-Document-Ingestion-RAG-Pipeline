# Import Python's built-in logging module.
# Logging is used to record what is happening inside the application.
import logging

# Import sys so logs can be printed clearly in the terminal.
import sys

# Import LOG_LEVEL from config.py.
# LOG_LEVEL controls whether we show INFO, DEBUG, ERROR, etc.
from app.config import LOG_LEVEL


# Create a reusable function that returns a logger object.
def get_logger(name: str) -> logging.Logger:
    """
    Create and return a logger for a specific file/module.

    Simple meaning:
    A logger is like a better print().
    It helps us see what happened, where it happened, and whether it was normal or an error.
    """

    # Create a logger using the file/module name.
    logger = logging.getLogger(name)

    # Set the minimum log level.
    # Example: INFO means show INFO, WARNING, ERROR, and CRITICAL logs.
    logger.setLevel(LOG_LEVEL)

    # This prevents duplicate logs when FastAPI reloads during development.
    if logger.handlers:
        return logger

    # Create a console handler.
    # This means logs will be printed in the terminal.
    console_handler = logging.StreamHandler(sys.stdout)

    # Set the same log level for the console output.
    console_handler.setLevel(LOG_LEVEL)

    # Define how each log message should look.
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Attach the format to the console handler.
    console_handler.setFormatter(formatter)

    # Attach the console handler to the logger.
    logger.addHandler(console_handler)

    # Stop logs from being duplicated by the root logger.
    logger.propagate = False

    # Return the logger so other files can use it.
    return logger