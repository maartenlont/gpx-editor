"""Serialise a RouteData to a FIT course file (binary format)."""

from __future__ import annotations

import struct
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from gpx_editor.io._course_point_types import (
    garmin_to_fit_int,
    symbol_to_garmin,
)
from gpx_editor.models.route import RouteData

# FIT epoch: 1989-12-31 00:00:00 UTC (seconds from Unix epoch)
_FIT_EPOCH = 631065600

# Degrees to FIT semicircles conversion
_DEG_TO_SC = 2**31 / 180.0

# FIT base types (field definition byte)
_ENUM   = 0x00   # 1 byte, invalid=0xFF
_UINT8  = 0x02   # 1 byte, invalid=0xFF
_UINT16 = 0x84   # 2 bytes, invalid=0xFFFF
_SINT32 = 0x85   # 4 bytes, invalid=0x7FFFFFFF
_UINT32 = 0x86   # 4 bytes, invalid=0xFFFFFFFF
_STRING = 0x07   # N bytes, padded with 0x00

# FIT global message numbers
_MSG_FILE_ID      = 0
_MSG_COURSE       = 31
_MSG_LAP          = 19
_MSG_EVENT        = 21
_MSG_RECORD       = 20
_MSG_COURSE_POINT = 32


# CRC lookup table from Garmin FIT SDK
_CRC_TABLE = [
    0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
    0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
]


def _crc16(data: bytes, crc: int = 0) -> int:
    for byte in data:
        tmp = _CRC_TABLE[crc & 0x0F]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ _CRC_TABLE[byte & 0x0F]
        tmp = _CRC_TABLE[crc & 0x0F]
        crc = (crc >> 4) & 0x0FFF
        crc ^= tmp ^ _CRC_TABLE[(byte >> 4) & 0x0F]
    return crc


def _to_sc(degrees: float) -> int:
    return int(round(degrees * _DEG_TO_SC))


def _to_fit_ts(dt: datetime | None, fallback: int = 0) -> int:
    if dt is None:
        return fallback
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return max(0, int(dt.timestamp()) - _FIT_EPOCH)


def _encode_string(text: str, size: int) -> bytes:
    """Encode text as a null-padded FIT string field of exactly *size* bytes."""
    raw = text.encode("utf-8", errors="replace")[:size - 1]
    return raw + b"\x00" * (size - len(raw))


def _def_msg(local: int, global_num: int, fields: list[tuple[int, int, int]]) -> bytes:
    """Build a FIT definition message (little-endian)."""
    hdr = bytes([0x40 | (local & 0x0F)])
    reserved = b"\x00"
    arch = b"\x00"  # little-endian
    gnum = struct.pack("<H", global_num)
    nfields = bytes([len(fields)])
    fld_bytes = b"".join(struct.pack("BBB", fdn, sz, bt) for fdn, sz, bt in fields)
    return hdr + reserved + arch + gnum + nfields + fld_bytes


def _data_msg(local: int, values: bytes) -> bytes:
    return bytes([local & 0x0F]) + values


def _file_header(data_size: int) -> bytes:
    hdr_no_crc = struct.pack("<BBHI4s", 14, 0x10, 2132, data_size, b".FIT")
    return hdr_no_crc + struct.pack("<H", _crc16(hdr_no_crc))


# ---------------------------------------------------------------------------
# Message definitions (field_def_num, size, base_type)
# ---------------------------------------------------------------------------

_DEF_FILE_ID = [
    (0, 1, _ENUM),    # type
    (1, 2, _UINT16),  # manufacturer
    (4, 4, _UINT32),  # time_created
]

_DEF_COURSE = [
    (4, 16, _STRING),  # name
]

_DEF_LAP = [
    (254, 2, _UINT16),  # message_index
    (253, 4, _UINT32),  # timestamp
    (2,   4, _UINT32),  # start_time
    (3,   4, _SINT32),  # start_position_lat
    (4,   4, _SINT32),  # start_position_long
    (5,   4, _SINT32),  # end_position_lat
    (6,   4, _SINT32),  # end_position_long
    (11,  4, _UINT32),  # total_distance (cm)
]

_DEF_EVENT = [
    (253, 4, _UINT32),  # timestamp
    (0,   1, _ENUM),    # event: 0=timer
    (1,   1, _ENUM),    # event_type: 0=start, 4=stop_all
]

_DEF_RECORD = [
    (253, 4, _UINT32),  # timestamp
    (0,   4, _SINT32),  # position_lat
    (1,   4, _SINT32),  # position_long
    (2,   2, _UINT16),  # altitude: (m + 500) * 5, invalid=0xFFFF
    (3,   1, _UINT8),   # heart_rate
    (4,   1, _UINT8),   # cadence
    (7,   2, _UINT16),  # power
]

_DEF_COURSE_POINT = [
    (254, 2, _UINT16),  # message_index
    (1,   4, _UINT32),  # timestamp
    (2,   4, _SINT32),  # position_lat
    (3,   4, _SINT32),  # position_long
    (5,   1, _ENUM),    # type
    (6,  16, _STRING),  # name
]

# Local message numbers
_L_FILE_ID      = 0
_L_COURSE       = 1
_L_LAP          = 2
_L_EVENT        = 3
_L_RECORD       = 4
_L_COURSE_POINT = 5


def write_fit(route: RouteData, path: str | Path) -> None:
    """Write *route* to *path* as a FIT course file."""
    records = _build_records(route)
    header = _file_header(len(records))
    file_crc = struct.pack("<H", _crc16(header + records))
    Path(path).write_bytes(header + records + file_crc)


def _build_records(route: RouteData) -> bytes:
    tp = route.track_points
    has_tp = len(tp) > 0

    # Generate synthetic FIT timestamps if track points have no time data.
    # Assume 25 km/h average speed for courses without timing.
    def _timestamps(df: pl.DataFrame) -> list[int]:
        base_fit_ts = _to_fit_ts(datetime(2024, 1, 1, tzinfo=UTC))
        if "time" in df.columns and df["time"][0] is not None:
            return [_to_fit_ts(t) for t in df["time"].to_list()]
        dists = df["distance"].to_list() if "distance" in df.columns else [0.0] * len(df)
        speed_ms = 25_000 / 3600
        return [base_fit_ts + int(d / speed_ms) for d in dists]

    ts_list = _timestamps(tp) if has_tp else []
    start_ts = ts_list[0] if ts_list else _to_fit_ts(datetime(2024, 1, 1, tzinfo=UTC))
    end_ts = ts_list[-1] if ts_list else start_ts

    buf = bytearray()

    # --- Definition messages ---
    buf += _def_msg(_L_FILE_ID,      _MSG_FILE_ID,      _DEF_FILE_ID)
    buf += _def_msg(_L_COURSE,       _MSG_COURSE,       _DEF_COURSE)
    buf += _def_msg(_L_LAP,          _MSG_LAP,          _DEF_LAP)
    buf += _def_msg(_L_EVENT,        _MSG_EVENT,        _DEF_EVENT)
    buf += _def_msg(_L_RECORD,       _MSG_RECORD,       _DEF_RECORD)
    buf += _def_msg(_L_COURSE_POINT, _MSG_COURSE_POINT, _DEF_COURSE_POINT)

    # --- FileId ---
    buf += _data_msg(_L_FILE_ID, struct.pack("<BHI", 6, 255, start_ts))

    # --- Course ---
    name = (route.source_file and Path(route.source_file).stem) or "Route"
    buf += _data_msg(_L_COURSE, _encode_string(name, 16))

    # --- Lap ---
    if has_tp:
        start_lat = _to_sc(float(tp["lat"][0]))
        start_lon = _to_sc(float(tp["lon"][0]))
        end_lat   = _to_sc(float(tp["lat"][-1]))
        end_lon   = _to_sc(float(tp["lon"][-1]))
        total_dist_cm = int(float(tp["distance"][-1]) * 100)
    else:
        start_lat = start_lon = end_lat = end_lon = 0x7FFFFFFF
        total_dist_cm = 0

    buf += _data_msg(_L_LAP, struct.pack(
        "<HIIiiiII",
        0,             # message_index
        end_ts,        # timestamp
        start_ts,      # start_time
        start_lat,     # start_position_lat
        start_lon,     # start_position_long
        end_lat,       # end_position_lat
        end_lon,       # end_position_long
        total_dist_cm, # total_distance
    ))

    # --- Event: timer start ---
    buf += _data_msg(_L_EVENT, struct.pack("<IBB", start_ts, 0, 0))

    # --- Record messages ---
    for i, row in enumerate(tp.iter_rows(named=True)):
        ts = ts_list[i]
        lat_sc = _to_sc(row["lat"])
        lon_sc = _to_sc(row["lon"])

        ele = row.get("elevation")
        if ele is not None:
            alt_raw = max(0, min(0xFFFE, int(round((float(ele) + 500) * 5))))
        else:
            alt_raw = 0xFFFF  # invalid

        hr  = int(row["hr"])      if row.get("hr")      is not None else 0xFF
        cad = int(row["cadence"]) if row.get("cadence") is not None else 0xFF
        pwr = int(row["power"])   if row.get("power")   is not None else 0xFFFF

        buf += _data_msg(_L_RECORD, struct.pack(
            "<IiiHBBH",
            ts, lat_sc, lon_sc, alt_raw, hr, cad, pwr,
        ))

    # --- CoursePoint messages (cues first, then POIs) ---
    tp_lats = tp["lat"].to_numpy() if has_tp else None
    tp_lons = tp["lon"].to_numpy() if has_tp else None
    from gpx_editor.io._distance import nearest_index as _nearest

    cp_idx = 0
    for df, is_cue_df in [(route.cues, True), (route.pois, False)]:
        for row in df.iter_rows(named=True):
            if ts_list and tp_lats is not None:
                snap_i, _ = _nearest(row["lat"], row["lon"], tp_lats, tp_lons)
                cp_ts = ts_list[snap_i]
            else:
                cp_ts = start_ts

            raw_type = row.get("cue_type") if is_cue_df else symbol_to_garmin(row.get("symbol") or "")
            cp_type = garmin_to_fit_int(raw_type or "Generic")
            cp_name = str(row.get("name") or "")

            buf += _data_msg(_L_COURSE_POINT, struct.pack("<HIii B",
                cp_idx,
                cp_ts,
                _to_sc(row["lat"]),
                _to_sc(row["lon"]),
                cp_type,
            ) + _encode_string(cp_name, 16))
            cp_idx += 1

    # --- Event: timer stop ---
    buf += _data_msg(_L_EVENT, struct.pack("<IBB", end_ts, 0, 4))

    return bytes(buf)
