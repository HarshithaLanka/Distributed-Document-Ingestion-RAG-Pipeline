# app/utils/logger.py

"""
This file creates reusable loggers for the whole project.

Simple meaning:
Instead of using print(), we use logger.info(), logger.error(),
logger.exception(), etc.

This file supports both styles:

1. New style:
   from app.utils.logger import logger

2. Existing project style:
   from app.utils.logger import get_logger
   logger = get_logger(__name__)

Your app/main.py is using the second style, so get_logger must accept a name.
"""

# Import Python's built-in logging module.
import logging

# Import sys so logs can be printed to the terminal.
import sys


def get_logger(name: str = "document_intelligence_rag") -> logging.Logger:
    """
    Create and return a logger.

    Parameter:
    - name: logger name. Example: __name__

    Why name is useful:
    If app/main.py calls get_logger(__name__), the logger name becomes app.main.
    If a service calls get_logger(__name__), the logger name becomes that service name.
    This helps identify where logs are coming from.
    """

    # Create or get logger with the given name.
    project_logger = logging.getLogger(name)

    # Set minimum log level.
    project_logger.setLevel(logging.INFO)

    # Prevent duplicate logs from propagating to root logger.
    project_logger.propagate = False

    # If logger already has handlers, return it.
    # This avoids duplicate logs during uvicorn reload or pytest.
    if project_logger.handlers:
        return project_logger

    # Create a console handler.
    # This prints logs to PowerShell/terminal.
    console_handler = logging.StreamHandler(sys.stdout)

    # Set handler log level.
    console_handler.setLevel(logging.INFO)

    # Create log format.
    log_format = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Attach format to handler.
    console_handler.setFormatter(log_format)

    # Attach handler to logger.
    project_logger.addHandler(console_handler)

    # Return final logger.
    return project_logger


# Default logger for files that import:
# from app.utils.logger import logger
logger = get_logger("document_intelligence_rag")