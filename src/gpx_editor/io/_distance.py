import numpy as np
import numpy.typing as npt

_EARTH_RADIUS_M = 6_371_000.0


def haversine(
    lat1: npt.ArrayLike,
    lon1: npt.ArrayLike,
    lat2: npt.ArrayLike,
    lon2: npt.ArrayLike,
) -> npt.NDArray[np.float64]:
    """Return great-circle distance in metres between coordinate pairs."""
    lat1, lon1, lat2, lon2 = (
        np.asarray(lat1, dtype=np.float64),
        np.asarray(lon1, dtype=np.float64),
        np.asarray(lat2, dtype=np.float64),
        np.asarray(lon2, dtype=np.float64),
    )
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    return _EARTH_RADIUS_M * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def cumulative_distance(lats: npt.ArrayLike, lons: npt.ArrayLike) -> npt.NDArray[np.float64]:
    """Return cumulative distance array (metres) starting at 0.0."""
    lats = np.asarray(lats, dtype=np.float64)
    lons = np.asarray(lons, dtype=np.float64)
    if len(lats) == 0:
        return np.array([], dtype=np.float64)
    segs = haversine(lats[:-1], lons[:-1], lats[1:], lons[1:])
    return np.concatenate([[0.0], np.cumsum(segs)])


def nearest_index(
    lat: float,
    lon: float,
    track_lats: npt.ArrayLike,
    track_lons: npt.ArrayLike,
) -> tuple[int, float]:
    """Return (index, distance_m) of the closest track point to (lat, lon)."""
    track_lats = np.asarray(track_lats, dtype=np.float64)
    track_lons = np.asarray(track_lons, dtype=np.float64)
    dists = haversine(lat, lon, track_lats, track_lons)
    idx = int(np.argmin(dists))
    return idx, float(dists[idx])
