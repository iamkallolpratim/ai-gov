"""Domain exceptions and the consistent error envelope."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error rendered as a consistent JSON envelope."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "Resource conflict."


class ValidationError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Request validation failed."


class RateLimitError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Too many requests."


class AuthenticationError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Authentication required."


class PermissionDeniedError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


class ImmutableRecordError(AppError):
    status_code = 409
    code = "IMMUTABLE_RECORD"
    message = "Audit records cannot be modified or deleted."


class UpstreamServiceError(AppError):
    status_code = 502
    code = "UPSTREAM_ERROR"
    message = "An upstream dependency failed."


class PolicyEvaluationError(UpstreamServiceError):
    code = "POLICY_EVALUATION_FAILED"
    message = "Policy evaluation failed."


class TaskQueueError(UpstreamServiceError):
    status_code = 503
    code = "TASK_QUEUE_UNAVAILABLE"
    message = (
        "Background processing is unavailable, so this job could not be queued. "
        "Check that Redis and the Celery worker are running, then try again."
    )


class StorageError(UpstreamServiceError):
    code = "STORAGE_ERROR"
    message = "Evidence storage operation failed."
