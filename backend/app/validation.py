"""Payload validation helpers (authoritative server-side validation)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from flask import request

from .errors import ApiError

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("invalid_json", "Send a JSON object body.", 400)
    return data


class Validator:
    def __init__(self, data: dict):
        self.data = data
        self.errors: dict[str, str] = {}

    def _fail(self, key: str, message: str):
        self.errors.setdefault(key, message)

    def fail(self, key: str, message: str):
        self._fail(key, message)

    def string(
        self,
        key: str,
        *,
        required: bool = False,
        default: str | None = None,
        min_length: int = 1,
        max_length: int = 255,
        allow_blank: bool = False,
    ) -> str | None:
        raw = self.data.get(key, default)
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            if required:
                self._fail(key, "This field is required.")
            return None
        if not isinstance(raw, str):
            self._fail(key, "Expected text.")
            return None
        value = raw.strip()
        if not allow_blank and len(value) < min_length:
            self._fail(key, f"Use at least {min_length} characters.")
            return None
        if len(value) > max_length:
            self._fail(key, f"Use at most {max_length} characters.")
            return None
        return value

    def email(self, key: str, *, required: bool = True) -> str | None:
        value = self.string(key, required=required, max_length=255)
        if value is None:
            return None
        value = value.lower()
        if not EMAIL_RE.match(value):
            self._fail(key, "Enter a valid email address.")
            return None
        return value

    def integer(
        self, key: str, *, required: bool = False, default: int | None = None,
        minimum: int | None = None, maximum: int | None = None,
    ) -> int | None:
        raw = self.data.get(key, default)
        if raw is None or raw == "":
            if required:
                self._fail(key, "This field is required.")
            return None
        if isinstance(raw, bool):
            self._fail(key, "Expected a whole number.")
            return None
        try:
            value = int(raw)
            if isinstance(raw, float) and not raw.is_integer():
                raise ValueError
        except (TypeError, ValueError):
            self._fail(key, "Expected a whole number.")
            return None
        if minimum is not None and value < minimum:
            self._fail(key, f"Must be at least {minimum}.")
        if maximum is not None and value > maximum:
            self._fail(key, f"Must be at most {maximum}.")
        return value

    def number(
        self, key: str, *, required: bool = False, default: float | None = None,
        minimum: float | None = None, maximum: float | None = None,
    ) -> float | None:
        raw = self.data.get(key, default)
        if raw is None or raw == "":
            if required:
                self._fail(key, "This field is required.")
            return None
        if isinstance(raw, bool):
            self._fail(key, "Expected a number.")
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError):
            self._fail(key, "Expected a number.")
            return None
        if minimum is not None and value < minimum:
            self._fail(key, f"Must be at least {minimum}.")
        if maximum is not None and value > maximum:
            self._fail(key, f"Must be at most {maximum}.")
        return value

    def boolean(self, key: str, default: bool = False) -> bool:
        raw = self.data.get(key, default)
        if isinstance(raw, bool):
            return raw
        if raw in (0, 1):
            return bool(raw)
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return default

    def choice(self, key: str, options, *, required: bool = False, default=None):
        raw = self.data.get(key, default)
        if raw is None or raw == "":
            if required:
                self._fail(key, "This field is required.")
            return default
        value = str(raw)
        if value not in options:
            self._fail(key, f"Choose one of: {', '.join(options)}.")
            return None
        return value

    def datetime(self, key: str, *, required: bool = False) -> datetime | None:
        raw = self.data.get(key)
        if raw is None or raw == "":
            if required:
                self._fail(key, "This field is required.")
            return None
        if not isinstance(raw, str):
            self._fail(key, "Use an ISO-8601 date-time.")
            return None
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            self._fail(key, "Use an ISO-8601 date-time.")
            return None
        if value.tzinfo is None:
            self._fail(key, "Include a time zone offset.")
            return None
        return value.astimezone(timezone.utc)

    def string_list(self, key: str, *, options: tuple[str, ...] | None = None) -> list[str]:
        raw = self.data.get(key, [])
        if raw is None:
            return []
        if not isinstance(raw, list):
            self._fail(key, "Expected a list.")
            return []
        values: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                self._fail(key, "Expected a list of text values.")
                return []
            value = item.strip().lower()
            if options and value not in options:
                self._fail(key, f"Unsupported value: {value}.")
                return []
            if value and value not in values:
                values.append(value)
        return values

    def location(self, prefix: str, *, required: bool = True) -> dict | None:
        """Accept either a sample location id or an explicit address + coordinates."""
        raw = self.data.get(prefix)
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            self._fail(prefix, "Provide location details.")
            return None
        location_id = raw.get("location_id")
        if location_id is not None:
            try:
                return {"location_id": int(location_id)}
            except (TypeError, ValueError):
                self._fail(f"{prefix}.location_id", "Invalid location id.")
                return None
        address_line = str(raw.get("address_line") or "").strip()
        area = str(raw.get("area") or "").strip()
        lat = raw.get("latitude")
        lng = raw.get("longitude")
        if not address_line or not area:
            if required:
                self._fail(prefix, "Address and area are required.")
            return None
        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            self._fail(prefix, "A map pin (latitude and longitude) is required.")
            return None
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            self._fail(prefix, "Coordinates are out of range.")
            return None
        return {
            "address_line": address_line[:255],
            "area": area[:120],
            "city": str(raw.get("city") or "Kolkata")[:120],
            "postal_code": str(raw.get("postal_code") or "")[:20] or None,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "label": str(raw.get("label") or address_line)[:160],
        }

    def finish(self) -> None:
        if self.errors:
            raise ApiError(
                "validation_failed",
                "Some fields need attention.",
                422,
                fields=self.errors,
            )


def as_bool(value: Any) -> bool:
    return bool(value)


def pagination_args() -> tuple[int, int]:
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get("per_page", "20"))
    except ValueError:
        per_page = 20
    return max(1, page), min(max(1, per_page), 100)
