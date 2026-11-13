"""Route matrix and geometry estimation.

OSRM is used when reachable. Otherwise a deterministic local estimate is used
and explicitly labelled as an estimate: no invented road navigation.
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass, field

EARTH_RADIUS_KM = 6371.0088

# Small in-process cache to avoid repeated identical OSRM calls per worker.
_CACHE: dict[tuple, "MatrixResult"] = {}
_CACHE_LIMIT = 32


@dataclass
class MatrixResult:
    distances_km: dict[tuple[int, int], float]
    durations_minutes: dict[tuple[int, int], float]
    source: str
    source_label: str
    fallback_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    def distance(self, a: int, b: int) -> float:
        return self.distances_km.get((a, b), 0.0)

    def duration(self, a: int, b: int) -> float:
        return self.durations_minutes.get((a, b), 0.0)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _cache_key(points, provider: str, config: dict) -> tuple:
    rounded = tuple(sorted((pid, round(lat, 5), round(lng, 5)) for pid, lat, lng in points))
    return (rounded, provider, round(config.get("avg_speed_kmh", 24), 2), round(config.get("road_factor", 1.32), 3))


def build_matrix(points: list[tuple[int, float, float]], config: dict) -> MatrixResult:
    """points: list of (identity, latitude, longitude). Identity is usually location id."""
    provider = str(config.get("provider", "auto")).lower()
    key = _cache_key(points, provider, config)
    if key in _CACHE:
        return _CACHE[key]

    if provider not in {"auto", "osrm"} or len(points) == 0:
        result = _estimated_matrix(points, config)
    else:
        try:
            result = _osrm_matrix(points, config)
        except Exception as exc:  # network, timeout, malformed response
            result = _estimated_matrix(points, config)
            result.fallback_reason = f"OSRM unavailable ({type(exc).__name__})"
            result.notes.append(
                "Road routing was unavailable, so travel is estimated from distances × road factor "
                f"{config.get('road_factor', 1.32)} at {config.get('avg_speed_kmh', 24)} km/h."
            )

    if len(_CACHE) >= _CACHE_LIMIT:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = result
    return result


def _estimated_matrix(points: list[tuple[int, float, float]], config: dict) -> MatrixResult:
    factor = float(config.get("road_factor", 1.32))
    speed = max(1.0, float(config.get("avg_speed_kmh", 24)))
    distances: dict[tuple[int, int], float] = {}
    durations: dict[tuple[int, int], float] = {}
    for a_id, a_lat, a_lng in points:
        for b_id, b_lat, b_lng in points:
            if a_id == b_id:
                distances[(a_id, b_id)] = 0.0
                durations[(a_id, b_id)] = 0.0
                continue
            km = haversine_km(a_lat, a_lng, b_lat, b_lng) * factor
            distances[(a_id, b_id)] = round(km, 3)
            durations[(a_id, b_id)] = round(km / speed * 60, 2)
    return MatrixResult(
        distances_km=distances,
        durations_minutes=durations,
        source="estimated",
        source_label=(
            "Estimated distance (haversine × road factor "
            f"{factor}) and travel time at {speed:g} km/h — not road navigation"
        ),
        notes=[
            "Distance figures are modelled estimates for planning, not measured road kilometres.",
        ],
    )


def _osrm_matrix(points: list[tuple[int, float, float]], config: dict) -> MatrixResult:
    base = str(config.get("osrm_base_url", "https://router.project-osrm.org")).rstrip("/")
    timeout = float(config.get("timeout_seconds", 3))
    coords = ";".join(f"{lng:.6f},{lat:.6f}" for _, lat, lng in points)
    url = f"{base}/table/v1/driving/{coords}?annotations=distance,duration"
    request = urllib.request.Request(url, headers={"User-Agent": "ReTurn/1.0 (demo route planner)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != "Ok" or "distances" not in payload:
        raise ValueError("OSRM returned no comparable route matrix")
    raw_distances = payload["distances"]
    raw_durations = payload.get("durations")
    if raw_durations is None:
        raise ValueError("OSRM returned no durations")
    distances: dict[tuple[int, int], float] = {}
    durations: dict[tuple[int, int], float] = {}
    for i, (a_id, _, _) in enumerate(points):
        for j, (b_id, _, _) in enumerate(points):
            d = raw_distances[i][j]
            t = raw_durations[i][j]
            if d is None or t is None:
                raise ValueError("OSRM matrix contained an unreachable pair")
            distances[(a_id, b_id)] = round(d / 1000.0, 3)
            durations[(a_id, b_id)] = round(t / 60.0, 2)
    return MatrixResult(
        distances_km=distances,
        durations_minutes=durations,
        source="osrm",
        source_label="OSRM road routing",
        notes=["Road distance and duration supplied by the configured OSRM service."],
    )


def route_geometry(stops: list[dict], config: dict) -> tuple[dict, str]:
    """Return (GeoJSON LineString, source). Fallback is explicitly illustrative."""
    coords = [(float(stop["latitude"]), float(stop["longitude"])) for stop in stops]
    if len(coords) < 2:
        return (
            {
                "type": "LineString",
                "coordinates": [[lng, lat] for lat, lng in coords],
            },
            "estimated",
        )
    provider = str(config.get("provider", "auto")).lower()
    if provider in {"auto", "osrm"}:
        try:
            return _osrm_geometry(coords, config), "osrm"
        except Exception:
            pass
    return (
        {
            "type": "LineString",
            "coordinates": [[lng, lat] for lat, lng in coords],
        },
        "estimated",
    )


def _osrm_geometry(coords: list[tuple[float, float]], config: dict) -> dict:
    base = str(config.get("osrm_base_url", "https://router.project-osrm.org")).rstrip("/")
    timeout = float(config.get("timeout_seconds", 3))
    path = ";".join(f"{lng:.6f},{lat:.6f}" for lat, lng in coords)
    url = f"{base}/route/v1/driving/{path}?overview=full&geometries=geojson&steps=false"
    request = urllib.request.Request(url, headers={"User-Agent": "ReTurn/1.0 (demo route planner)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise ValueError("No OSRM route")
    geometry = payload["routes"][0]["geometry"]
    if geometry.get("type") != "LineString" or len(geometry.get("coordinates") or []) < 2:
        raise ValueError("Invalid geometry")
    return geometry
