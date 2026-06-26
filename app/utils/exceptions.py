# Import status codes from FastAPI.
# These are readable names for HTTP status codes like 400, 404, and 500.
from fastapi import status


# Create a base custom exception for our application.
# Other custom exceptions will inherit from this class.
class AppException(Exception):
    """
    Base exception for our application.

    Simple meaning:
    This is our own error type.
    When something goes wrong in services, we can raise this error
    and FastAPI will return a clean JSON response.
    """

    # Constructor method runs when we create the exception.
    def __init__(
        self,
        message: str,
        error_code: str = "APP_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        # Store the human-readable error message.
        self.message = message

        # Store a short machine-readable error code.
        self.error_code = error_code

        # Store the HTTP status code.
        self.status_code = status_code

        # Call the parent Exception class.
        super().__init__(message)


# Custom exception for bad user input.
# Example: user uploads non-PDF file.
class BadRequestException(AppException):
    """
    Use this when the user sends invalid input.
    Returns HTTP 400.
    """

    def __init__(self, message: str = "Bad request"):
        super().__init__(
            message=message,
            error_code="BAD_REQUEST",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# Custom exception for missing resources.
# Example: document_id does not exist.
class NotFoundException(AppException):
    """
    Use this when requested data is not found.
    Returns HTTP 404.
    """

    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


# Custom exception for unexpected server-side errors.
# Example: PDF parsing fails unexpectedly.
class InternalServerException(AppException):
    """
    Use this when something fails inside the server.
    Returns HTTP 500.
    """

    def __init__(self, message: str = "Internal server error"):
        super().__init__(
            message=message,
            error_code="INTERNAL_SERVER_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )