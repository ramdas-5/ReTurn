"""Admin analytics and estimated sustainability endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..domain import ROLE_ADMIN
from ..security import role_required
from ..services import analytics

bp = Blueprint("analytics", __name__, url_prefix="/api/v1/analytics")


@bp.get("/summary")
@role_required(ROLE_ADMIN)
def summary():
    return jsonify({"data": analytics.summary()})


@bp.get("/sustainability")
@role_required(ROLE_ADMIN)
def sustainability():
    return jsonify({"data": analytics.sustainability()})
