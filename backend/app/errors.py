"""Consistent JSON error envelope and pagination helpers."""
from __future__ import annotations

from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 400,
        fields: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields or {}
        self.details = details or {}

    def to_response(self):
        payload: dict[str, Any] = {"error": {"code": self.code, "message": self.message}}
        if self.fields:
            payload["error"]["fields"] = self.fields
        if self.details:
            payload["error"]["details"] = self.details
        return jsonify(payload), self.status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(error: ApiError):
        return error.to_response()

    @app.errorhandler(HTTPException)
    def _http_error(error: HTTPException):
        messages = {
            404: ("not_found", "The requested resource does not exist."),
            405: ("method_not_allowed", "This HTTP method is not allowed for the endpoint."),
            413: ("payload_too_large", "The request payload is too large."),
        }
        code, message = messages.get(
            error.code or 500, ("http_error", error.description or "Request failed.")
        )
        return jsonify({"error": {"code": code, "message": message}}), error.code or 500

    @app.errorhandler(Exception)
    def _unexpected(error: Exception):  # pragma: no cover - safety net
        app.logger.exception("Unhandled API error: %s", error)
        return (
            jsonify(
                {
                    "error": {
                        "code": "internal_error",
                        "message": "An unexpected error occurred. Please try again.",
                    }
                }
            ),
            500,
        )


def paginate(query, page: int, per_page: int, serializer) -> tuple[dict, int]:
    page = max(1, page)
    per_page = min(max(1, per_page), 100)
    total = query.order_by(None).count()
    rows = query.limit(per_page).offset((page - 1) * per_page).all()
    return (
        {
            "data": [serializer(row) for row in rows],
            "meta": {"page": page, "per_page": per_page, "total": total},
        },
        200,
    )
