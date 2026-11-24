from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ApplicationError(APIException):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_code = code
        self.error_message = message
        self.error_details = details or {}
        super().__init__(detail=message, code=code)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    if isinstance(exc, ApplicationError):
        return Response(
            {
                "error": {
                    "code": exc.error_code,
                    "message": exc.error_message,
                    "details": exc.error_details,
                }
            },
            status=exc.status_code,
        )

    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, ValidationError):
            first_msg = "Please review the highlighted fields and try again."
            if isinstance(response.data, dict):
                for val in response.data.values():
                    if isinstance(val, list) and val:
                        first_msg = str(val[0])
                        break
                    if isinstance(val, str):
                        first_msg = val
                        break
            elif isinstance(response.data, list) and response.data:
                first_msg = str(response.data[0])
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": first_msg,
                        "details": response.data if isinstance(response.data, dict) else {"errors": response.data},
                    }
                },
                status=response.status_code,
            )

        if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
            return Response(
                {
                    "error": {
                        "code": "AUTHENTICATION_REQUIRED",
                        "message": "Authentication is required to perform this action.",
                        "details": {},
                    }
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if isinstance(exc, (PermissionDenied, DjangoPermissionDenied)):
            detail_str = str(getattr(exc, "detail", "You do not have permission to perform this action."))
            if "CSRF" in detail_str.upper():
                return Response(
                    {
                        "error": {
                            "code": "CSRF_FAILED",
                            "message": "Security token missing or expired. Please refresh and try again.",
                            "details": {},
                        }
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            return Response(
                {
                    "error": {
                        "code": "PERMISSION_DENIED",
                        "message": "You do not have permission to perform this action.",
                        "details": {},
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if isinstance(exc, (NotFound, Http404)):
            return Response(
                {
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "The requested resource was not found.",
                        "details": {},
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if isinstance(exc, Throttled):
            return Response(
                {
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Please wait a moment and try again.",
                        "details": {},
                    }
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        return Response(
            {
                "error": {
                    "code": "REQUEST_ERROR",
                    "message": str(getattr(exc, "detail", "Unable to process request.")),
                    "details": {},
                }
            },
            status=response.status_code,
        )

    logger.exception("Unhandled exception in API view: %s", type(exc).__name__)
    return Response(
        {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected server error occurred. Please try again shortly.",
                "details": {},
            }
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
