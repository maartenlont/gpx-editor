# Data Structures Reference

This document describes the data structures used in the GPX Editor, with a focus on
Polars DataFrames, their schemas, and typical data examples.

---

## Overview

The application uses **Polars DataFrames** as the primary in-memory data structure for
representing GPS route data. All route information is stored in three DataFrames,
bundled together in a `RouteData` dataclass.

### Core Modules

| Module | Description |
|--------|-------------|
| `models/route.py` | `RouteData` dataclass + canonical schemas |
| `models/route_entry.py` | `RouteEntry` wrapper (display metadata) |
| `io/gpx_reader.py` | GPX → DataFrames |
| `io/tcx_reader.py` | TCX → DataFrames |
| `io/gpx_writer.py` | DataFrames → GPX |
| `io/tcx_writer.py` | DataFrames → TCX |

---

## RouteData Dataclass

**Location:** `src/gpx_editor/models/route.py`

```python
@dataclass
class RouteData:
    track_points: pl.DataFrame  # GPS track points
    cues: pl.DataFrame          # Turn-by-turn navigation cues
    pois: pl.DataFrame          # Points of interest
    source_file: str = ""       # Original file path
```

---

## Polars DataFrame Schemas

### track_points DataFrame

Contains the GPS track — the actual recorded route coordinates.

**Schema (defined as `TRACK_POINTS_SCHEMA`):**

| Column | Polars Dtype | Description |
|--------|--------------|-------------|
| `index` | `Int64` | Sequential row identifier (0-based) |
| `lat` | `Float64` | Latitude in WGS-84 decimal degrees |
| `lon` | `Float64` | Longitude in WGS-84 decimal degrees |
| `elevation` | `Float64` | Altitude in metres (nullable) |
| `time` | `Datetime("us", "UTC")` | UTC timestamp (nullable) |
| `distance` | `Float64` | Cumulative distance from start in metres |
| `hr` | `Int32` | Heart rate in bpm (nullable) |
| `cadence` | `Int32` | Cycling cadence in rpm (nullable) |
| `power` | `Int32` | Power in watts (nullable) |

**Example Data:**

```python
import polars as pl

track_points = pl.DataFrame({
    "index":     [0, 1, 2, 3, 4],
    "lat":       [52.370216, 52.370312, 52.370458, 52.370621, 52.370789],
    "lon":       [4.895168, 4.895342, 4.895521, 4.895698, 4.895891],
    "elevation": [2.5, 2.8, 3.1, 3.5, 3.2],
    "time":      [
        datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 6, 15, 10, 0, 5, tzinfo=timezone.utc),
        datetime(2024, 6, 15, 10, 0, 10, tzinfo=timezone.utc),
        datetime(2024, 6, 15, 10, 0, 15, tzinfo=timezone.utc),
        datetime(2024, 6, 15, 10, 0, 20, tzinfo=timezone.utc),
    ],
    "distance":  [0.0, 15.3, 32.7, 51.2, 72.8],
    "hr":        [120, 122, 125, 128, 130],
    "cadence":   [85, 87, 88, 90, 89],
    "power":     [180, 185, 190, 195, 188],
})

# Rendered table:
# ┌───────┬───────────┬──────────┬───────────┬─────────────────────┬──────────┬─────┬─────────┬───────┐
# │ index ┆ lat       ┆ lon      ┆ elevation ┆ time                ┆ distance ┆ hr  ┆ cadence ┆ power │
# │ ---   ┆ ---       ┆ ---      ┆ ---       ┆ ---                 ┆ ---      ┆ --- ┆ ---     ┆ ---   │
# │ i64   ┆ f64       ┆ f64      ┆ f64       ┆ datetime[μs, UTC]   ┆ f64      ┆ i32 ┆ i32     ┆ i32   │
# ╞═══════╪═══════════╪══════════╪═══════════╪═════════════════════╪══════════╪═════╪═════════╪═══════╡
# │ 0     ┆ 52.370216 ┆ 4.895168 ┆ 2.5       ┆ 2024-06-15 10:00:00 ┆ 0.0      ┆ 120 ┆ 85      ┆ 180   │
# │ 1     ┆ 52.370312 ┆ 4.895342 ┆ 2.8       ┆ 2024-06-15 10:00:05 ┆ 15.3     ┆ 122 ┆ 87      ┆ 185   │
# │ 2     ┆ 52.370458 ┆ 4.895521 ┆ 3.1       ┆ 2024-06-15 10:00:10 ┆ 32.7     ┆ 125 ┆ 88      ┆ 190   │
# │ 3     ┆ 52.370621 ┆ 4.895698 ┆ 3.5       ┆ 2024-06-15 10:00:15 ┆ 51.2     ┆ 128 ┆ 90      ┆ 195   │
# │ 4     ┆ 52.370789 ┆ 4.895891 ┆ 3.2       ┆ 2024-06-15 10:00:20 ┆ 72.8     ┆ 130 ┆ 89      ┆ 188   │
# └───────┴───────────┴──────────┴───────────┴─────────────────────┴──────────┴─────┴─────────┴───────┘
```

---

### cues DataFrame

Contains turn-by-turn navigation cues (turn left, turn right, etc.).

**Schema (defined as `CUES_SCHEMA`):**

| Column | Polars Dtype | Description |
|--------|--------------|-------------|
| `index` | `Int64` | Sequential row identifier |
| `lat` | `Float64` | Latitude (snapped to nearest track point) |
| `lon` | `Float64` | Longitude (snapped to nearest track point) |
| `name` | `String` | Cue name (e.g., street name) |
| `description` | `String` | Additional description (nullable) |
| `cue_type` | `String` | Type: `Left`, `Right`, `Straight`, `Generic`, etc. |
| `distance` | `Float64` | Distance from route start in metres |

**Example Data:**

```python
cues = pl.DataFrame({
    "index":       [0, 1, 2],
    "lat":         [52.370312, 52.375821, 52.382145],
    "lon":         [4.895342, 4.901234, 4.908567],
    "name":        ["Turn onto Main St", "Continue on Park Ave", "Arrive at destination"],
    "description": ["At the traffic light", None, "End of route"],
    "cue_type":    ["Left", "Straight", "Generic"],
    "distance":    [15.3, 1250.0, 3580.5],
})

# Rendered table:
# ┌───────┬───────────┬──────────┬───────────────────────┬────────────────────┬──────────┬──────────┐
# │ index ┆ lat       ┆ lon      ┆ name                  ┆ description        ┆ cue_type ┆ distance │
# │ ---   ┆ ---       ┆ ---      ┆ ---                   ┆ ---                ┆ ---      ┆ ---      │
# │ i64   ┆ f64       ┆ f64      ┆ str                   ┆ str                ┆ str      ┆ f64      │
# ╞═══════╪═══════════╪══════════╪═══════════════════════╪════════════════════╪══════════╪══════════╡
# │ 0     ┆ 52.370312 ┆ 4.895342 ┆ Turn onto Main St     ┆ At the traffic li… ┆ Left     ┆ 15.3     │
# │ 1     ┆ 52.375821 ┆ 4.901234 ┆ Continue on Park Ave  ┆ null               ┆ Straight ┆ 1250.0   │
# │ 2     ┆ 52.382145 ┆ 4.908567 ┆ Arrive at destination ┆ End of route       ┆ Generic  ┆ 3580.5   │
# └───────┴───────────┴──────────┴───────────────────────┴────────────────────┴──────────┴──────────┘
```

**Valid `cue_type` values (from GPX/TCX standards):**

- `Left`, `Right`, `Straight`
- `SharpLeft`, `SharpRight`
- `SlightLeft`, `SlightRight`
- `UTurn`
- `Generic`

---

### pois DataFrame

Contains points of interest (water stations, food stops, scenic viewpoints, etc.).

**Schema (defined as `POIS_SCHEMA`):**

| Column | Polars Dtype | Description |
|--------|--------------|-------------|
| `index` | `Int64` | Sequential row identifier |
| `lat` | `Float64` | Latitude (snapped to nearest track point) |
| `lon` | `Float64` | Longitude (snapped to nearest track point) |
| `name` | `String` | POI name |
| `description` | `String` | Additional description (nullable) |
| `symbol` | `String` | Icon/symbol identifier (nullable) |
| `distance` | `Float64` | Distance from route start in metres |

**Example Data:**

```python
pois = pl.DataFrame({
    "index":       [0, 1, 2],
    "lat":         [52.371500, 52.378200, 52.385900],
    "lon":         [4.897100, 4.903400, 4.912300],
    "name":        ["Water Station", "Café De Hoek", "Scenic Viewpoint"],
    "description": ["Refill bottles here", "Great coffee!", None],
    "symbol":      ["water", "food", "scenic"],
    "distance":    [450.0, 2100.5, 4200.8],
})

# Rendered table:
# ┌───────┬───────────┬──────────┬──────────────────┬─────────────────────┬────────┬──────────┐
# │ index ┆ lat       ┆ lon      ┆ name             ┆ description         ┆ symbol ┆ distance │
# │ ---   ┆ ---       ┆ ---      ┆ ---              ┆ ---                 ┆ ---    ┆ ---      │
# │ i64   ┆ f64       ┆ f64      ┆ str              ┆ str                 ┆ str    ┆ f64      │
# ╞═══════╪═══════════╪══════════╪══════════════════╪═════════════════════╪════════╪══════════╡
# │ 0     ┆ 52.3715   ┆ 4.8971   ┆ Water Station    ┆ Refill bottles here ┆ water  ┆ 450.0    │
# │ 1     ┆ 52.3782   ┆ 4.9034   ┆ Café De Hoek     ┆ Great coffee!       ┆ food   ┆ 2100.5   │
# │ 2     ┆ 52.3859   ┆ 4.9123   ┆ Scenic Viewpoint ┆ null                ┆ scenic ┆ 4200.8   │
# └───────┴───────────┴──────────┴──────────────────┴─────────────────────┴────────┴──────────┘
```

---

## RouteEntry Dataclass

**Location:** `src/gpx_editor/models/route_entry.py`

Wraps `RouteData` with display metadata for multi-route support in the GUI.

```python
@dataclass
class RouteEntry:
    route: RouteData   # The actual route data
    color: str         # CSS hex colour, e.g. "#1565C0"
    label: str         # Display name (usually filename stem)
    visible: bool = True  # Whether to show on map/elevation chart
```

**Colour Palette:**

New routes are assigned colours from a predefined palette:

| Colour | Hex | Name |
|--------|-----|------|
| 🔵 | `#1565C0` | Blue (primary) |
| 🔴 | `#B71C1C` | Red |
| 🟢 | `#2E7D32` | Green |
| 🟠 | `#E65100` | Orange |
| 🟣 | `#6A1B9A` | Purple |
| 🔵 | `#00695C` | Teal |
| 🟡 | `#F9A825` | Amber |
| 🟤 | `#4E342E` | Brown |
| 🔵 | `#00BCD4` | Cyan |
| 🔴 | `#EC407A` | Pink |
| ⬛ | `#546E7A` | Slate |
| ⬛ | `#000000` | Black |

---

## Polars Usage Patterns

### Creating Empty DataFrames

Factory functions ensure consistent schema for empty DataFrames:

```python
from gpx_editor.models.route import (
    empty_track_points,
    empty_cues,
    empty_pois,
    TRACK_POINTS_SCHEMA,
)

# Create empty DataFrame with correct schema
tp = empty_track_points()  # pl.DataFrame(schema=TRACK_POINTS_SCHEMA)
```

### Iterating Over Rows

The codebase uses `iter_rows(named=True)` for row-by-row processing:

```python
for row in track_points.iter_rows(named=True):
    lat = row["lat"]
    lon = row["lon"]
    # Process each track point...
```

### Column Access

```python
# Extract column as NumPy array (for distance calculations)
lats = track_points["lat"].to_numpy()
lons = track_points["lon"].to_numpy()

# Single value access
first_lat = float(track_points["lat"][0])
```

### Filtering

```python
# Remove a row by index value
new_df = df.filter(pl.col("index") != index_val)
```

### Sorting

```python
# Sort by distance (always done before display)
sorted_tp = track_points.sort("distance")
```

### Column Selection and Reordering

```python
def _reorder(df: pl.DataFrame, order: list[str]) -> pl.DataFrame:
    """Reorder visible columns; unknown/extra columns appended."""
    ordered = [c for c in order if c in df.columns]
    extra = [c for c in df.columns if c not in set(order) and c != "index"]
    return df.select(["index"] + ordered + extra)
```

### Concatenation

```python
# Merge two DataFrames vertically
combined = pl.concat([existing, new_poi])
```

### Schema-Aware Construction

```python
new_poi = pl.DataFrame(
    {
        "index":       [next_idx],
        "lat":         [snap_lat],
        "lon":         [snap_lon],
        "name":        [name],
        "description": [vals.get("description")],
        "symbol":      [vals.get("symbol")],
        "distance":    [snap_dist],
    },
    schema=POIS_SCHEMA,  # Ensures correct dtypes
)
```

### Distance Calculations

```python
# Find nearest row to a given distance
idx = int((df["distance"] - distance_m).abs().arg_min())
```

### Re-indexing After Operations

```python
# Reset index column after sorting/merging
combined = combined.with_columns(
    pl.Series("index", list(range(len(combined))), dtype=pl.Int64)
)
```

---

## Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  GPX File   │────▶│ gpx_reader  │────▶│             │
└─────────────┘     └─────────────┘     │             │
                                        │  RouteData  │
┌─────────────┐     ┌─────────────┐     │  ├─ track   │
│  TCX File   │────▶│ tcx_reader  │────▶│  ├─ cues    │
└─────────────┘     └─────────────┘     │  └─ pois    │
                                        │             │
                                        └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
                    ▼                          ▼                          ▼
            ┌───────────────┐          ┌───────────────┐          ┌───────────────┐
            │  Map Widget   │          │ Elevation     │          │ Table Views   │
            │  (Polylines,  │          │ Widget        │          │ (DataFrameModel)
            │   Markers)    │          │ (matplotlib)  │          │               │
            └───────────────┘          └───────────────┘          └───────────────┘
```

---

## Key Invariants

1. **All distances are in metres** — cumulative from route start
2. **All coordinates are WGS-84 decimal degrees**
3. **`index` column is sequential and 0-based** — reset after sort/merge
4. **DataFrames are immutable** — operations return new DataFrames
5. **Nullable columns** — `elevation`, `time`, `hr`, `cadence`, `power`, `description`, `symbol` can be `null`

---

## File Format Mapping

### GPX Elements

| DataFrame | GPX Source Element |
|-----------|-------------------|
| `track_points` | `<trkpt>` inside `<trk>/<trkseg>` |
| `cues` | `<wpt>` with cue-type `<type>` or Garmin extensions |
| `pois` | `<wpt>` elements not classified as cues |

### TCX Elements

| DataFrame | TCX Source Element |
|-----------|-------------------|
| `track_points` | `<Trackpoint>` inside `<Track>` |
| `cues` | `<CoursePoint>` (type ≠ `Generic`) |
| `pois` | `<CoursePoint>` with type `Generic` |
