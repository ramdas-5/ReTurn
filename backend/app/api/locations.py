"""Sample location gazetteer for the demo map picker."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..models import Location
from ..security import login_required
from ..serializers import serialize_location

bp = Blueprint("locations", __name__, url_prefix="/api/v1/locations")


@bp.get("/suggestions")
@login_required
def suggestions():
    query_text = (request.args.get("q") or "").strip()
    query = Location.query.filter(Location.is_sample.is_(True))
    if query_text:
        like = f"%{query_text}%"
        query = query.filter(
            Location.label.ilike(like) | Location.area.ilike(like) | Location.city.ilike(like)
        )
    rows = query.order_by(Location.label.asc()).limit(12).all()
    return jsonify({"data": [serialize_location(row) for row in rows]})
