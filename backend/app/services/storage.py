"""Private media storage for parcel photographs and delivery proof.

The local adapter is the documented development fallback. Both adapters keep
files private: bytes are only served through the authenticated API, never from a
predictable public URL.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import os
import time
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.datastructures import FileStorage

from ..errors import ApiError
from ..extensions import db
from ..models import MediaAsset

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
}


def _sniff_image_type(head: bytes) -> str | None:
    for magic, mime in _MAGIC.items():
        if head.startswith(magic):
            return mime
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def _local_root() -> Path:
    root = Path(current_app.config["MEDIA_LOCAL_DIR"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def _storage_key(filename: str) -> str:
    now = time.gmtime()
    return f"{now.tm_year:04d}/{now.tm_mon:02d}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


def save_image(
    upload: FileStorage,
    *,
    uploaded_by=None,
    error_prefix: str = "image",
) -> MediaAsset:
    if upload is None or not getattr(upload, "filename", None):
        raise ApiError(f"{error_prefix}_required", "Choose an image to upload.", 400)

    content_type = (upload.mimetype or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ApiError(
            f"{error_prefix}_type_invalid",
            "Upload a JPEG, PNG or WebP image.",
            400,
        )

    data = upload.read()
    max_bytes = int(current_app.config["MAX_CONTENT_LENGTH"])
    if not data:
        raise ApiError(f"{error_prefix}_empty", "The uploaded image is empty.", 400)
    if len(data) > max_bytes:
        raise ApiError(
            f"{error_prefix}_too_large",
            f"The image must be smaller than {max_bytes // (1024 * 1024)} MB.",
            400,
        )

    sniffed = _sniff_image_type(data[:16])
    if sniffed != content_type:
        raise ApiError(
            f"{error_prefix}_type_invalid",
            "The file content does not match a supported image type.",
            400,
        )

    checksum = hashlib.sha256(data).hexdigest()
    suffix = ALLOWED_IMAGE_TYPES[content_type]
    key = _storage_key(f"upload{suffix}")
    backend = current_app.config.get("MEDIA_BACKEND", "local")

    if backend == "local":
        path = _local_root() / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    elif backend == "s3":
        _s3_put(key, data, content_type)
    else:
        raise ApiError(
            "media_backend_unconfigured",
            "Image storage is not configured on this deployment.",
            503,
        )

    asset = MediaAsset(
        storage_backend=backend,
        storage_key=key,
        original_filename=(upload.filename or "")[:255],
        content_type=content_type,
        byte_size=len(data),
        checksum_sha256=checksum,
        uploaded_by_id=getattr(uploaded_by, "id", None),
        visibility="private",
    )
    db.session.add(asset)
    db.session.flush()
    return asset


def open_media(asset: MediaAsset) -> tuple[io.BufferedIOBase, str]:
    """Return (stream, content_type). Caller must close the stream."""
    if asset.deleted_at is not None:
        raise ApiError("media_missing", "That image is no longer available.", 404)
    if asset.storage_backend == "local":
        path = _local_root() / asset.storage_key
        if not path.exists():
            raise ApiError("media_missing", "That image is no longer available.", 404)
        return open(path, "rb"), asset.content_type
    if asset.storage_backend == "s3":
        return _s3_get(asset.storage_key), asset.content_type
    raise ApiError("media_missing", "That image is no longer available.", 404)


def delete_media(asset: MediaAsset) -> None:
    asset.deleted_at = domain_now()
    if asset.storage_backend == "local":
        path = _local_root() / asset.storage_key
        try:
            path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - filesystem edge case
            pass


# ------------------------------------------------------------------ signatures
def _signing_secret() -> bytes:
    secret = current_app.config.get("MEDIA_SIGNING_SECRET") or current_app.config["SECRET_KEY"]
    return secret.encode("utf-8")


def sign_media_id(asset_id: int, ttl_seconds: int | None = None) -> str:
    ttl = int(ttl_seconds or current_app.config["MEDIA_SIGNED_URL_TTL_SECONDS"])
    expires = int(time.time()) + ttl
    message = f"{asset_id}:{expires}".encode("utf-8")
    signature = hmac.new(_signing_secret(), message, hashlib.sha256).hexdigest()
    return f"expires={expires}&signature={signature}"


def verify_media_signature(asset_id: int, expires: str | None, signature: str | None) -> bool:
    if not expires or not signature:
        return False
    try:
        expires_int = int(expires)
    except ValueError:
        return False
    if expires_int < int(time.time()):
        return False
    message = f"{asset_id}:{expires_int}".encode("utf-8")
    expected = hmac.new(_signing_secret(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def media_url(asset: MediaAsset | None) -> str | None:
    if asset is None:
        return None
    return f"/api/v1/media/{asset.id}?{sign_media_id(asset.id)}"


# ------------------------------------------------------------------------ S3
def _s3_client():
    try:
        import boto3  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on deployment extras
        raise ApiError(
            "media_backend_unconfigured",
            "S3 storage requires the boto3 package on this deployment.",
            503,
        ) from exc
    return boto3.client(
        "s3",
        region_name=current_app.config.get("S3_REGION") or None,
        endpoint_url=current_app.config.get("S3_ENDPOINT_URL") or None,
        aws_access_key_id=current_app.config.get("S3_ACCESS_KEY_ID") or None,
        aws_secret_access_key=current_app.config.get("S3_SECRET_ACCESS_KEY") or None,
    )


def _s3_put(key: str, data: bytes, content_type: str) -> None:  # pragma: no cover
    bucket = current_app.config.get("S3_BUCKET")
    if not bucket:
        raise ApiError("media_backend_unconfigured", "S3 bucket is not configured.", 503)
    _s3_client().put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        ServerSideEncryption="AES256",
        ACL="private",
    )


def _s3_get(key: str):  # pragma: no cover
    bucket = current_app.config.get("S3_BUCKET")
    if not bucket:
        raise ApiError("media_backend_unconfigured", "S3 bucket is not configured.", 503)
    response = _s3_client().get_object(Bucket=bucket, Key=key)
    return io.BytesIO(response["Body"].read())


def domain_now():
    from ..domain import utcnow

    return utcnow()
