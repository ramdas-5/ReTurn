"""Private media delivery for parcel photographs and delivery evidence.

Bytes never live on a public path. A request is served only when either:

* the URL carries a valid, unexpired HMAC signature issued by the API, or
* the signed-in account can view an order the asset belongs to (owner consumer,
  assigned driver, responsible manager, administrator).

Proof and parcel photographs are never exposed in public listings.
"""
from __future__ import annotations

from flask import Blueprint, request, send_file

from .. import domain
from ..access import can_view_order
from ..errors import ApiError
from ..extensions import db
from ..models import MediaAsset, Order, ParcelImage, ProofMedia
from ..security import current_user
from ..services.storage import open_media, verify_media_signature

bp = Blueprint("media", __name__, url_prefix="/api/v1/media")


def _order_ids_for_asset(asset_id: int) -> set[int]:
    ids = {row.order_id for row in ParcelImage.query.filter_by(media_id=asset_id).all()}
    ids |= {row.order_id for row in ProofMedia.query.filter_by(media_id=asset_id).all()}
    return ids


def _can_view_asset(user, asset: MediaAsset) -> bool:
    if user is None:
        return False
    if user.role == domain.ROLE_ADMIN:
        return True
    if asset.uploaded_by_id == user.id:
        return True
    for order_id in _order_ids_for_asset(asset.id):
        order = db.session.get(Order, order_id)
        if order is not None and can_view_order(user, order):
            return True
    return False


@bp.get("/<int:asset_id>")
def serve_media(asset_id: int):
    asset = db.session.get(MediaAsset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise ApiError("not_found", "That image does not exist.", 404)

    signed = verify_media_signature(
        asset_id, request.args.get("expires"), request.args.get("signature")
    )
    if not signed and not _can_view_asset(current_user(), asset):
        raise ApiError("forbidden", "You do not have access to that image.", 403)

    stream, content_type = open_media(asset)
    response = send_file(
        stream,
        mimetype=content_type,
        download_name=asset.original_filename or f"return-{asset.id}",
        as_attachment=False,
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, max-age=60"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
