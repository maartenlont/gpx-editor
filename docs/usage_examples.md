# Usage Examples

Code examples for reading, writing, and manipulating GPX/TCX route data.

---

## Reading Files

### Read a GPX File

```python
from gpx_editor.io.gpx_reader import read_gpx

# Load a GPX file
route = read_gpx("/path/to/route.gpx")

# Access the data
print(f"Track points: {len(route.track_points)}")
print(f"Cues: {len(route.cues)}")
print(f"POIs: {len(route.pois)}")
print(f"Source file: {route.source_file}")

# View the track points DataFrame
print(route.track_points)
```

**Output:**

```
Track points: 1523
Cues: 12
POIs: 5
Source file: /path/to/route.gpx

shape: (1523, 9)
┌───────┬───────────┬──────────┬───────────┬─────────────────────┬──────────┬─────┬─────────┬───────┐
│ index ┆ lat       ┆ lon      ┆ elevation ┆ time                ┆ distance ┆ hr  ┆ cadence ┆ power │
│ ---   ┆ ---       ┆ ---      ┆ ---       ┆ ---                 ┆ ---      ┆ --- ┆ ---     ┆ ---   │
│ i64   ┆ f64       ┆ f64      ┆ f64       ┆ datetime[μs, UTC]   ┆ f64      ┆ i32 ┆ i32     ┆ i32   │
╞═══════╪═══════════╪══════════╪═══════════╪═════════════════════╪══════════╪═════╪═════════╪═══════╡
│ 0     ┆ 52.370216 ┆ 4.895168 ┆ 2.5       ┆ 2024-06-15 10:00:00 ┆ 0.0      ┆ 120 ┆ 85      ┆ 180   │
│ 1     ┆ 52.370312 ┆ 4.895342 ┆ 2.8       ┆ 2024-06-15 10:00:05 ┆ 15.3     ┆ 122 ┆ 87      ┆ 185   │
│ …     ┆ …         ┆ …        ┆ …         ┆ …                   ┆ …        ┆ …   ┆ …       ┆ …     │
└───────┴───────────┴──────────┴───────────┴─────────────────────┴──────────┴─────┴─────────┴───────┘
```

### Read a TCX File

```python
from gpx_editor.io.tcx_reader import read_tcx

# Load a TCX file
route = read_tcx("/path/to/activity.tcx")

# Access the data
print(f"Track points: {len(route.track_points)}")
print(f"Cues: {len(route.cues)}")
print(f"POIs: {len(route.pois)}")
```

### Read from XML String (Useful for Tests)

```python
from gpx_editor.io.gpx_reader import read_gpx_string
from gpx_editor.io.tcx_reader import read_tcx_string

gpx_xml = """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <trk>
    <trkseg>
      <trkpt lat="52.370216" lon="4.895168">
        <ele>2.5</ele>
      </trkpt>
      <trkpt lat="52.370312" lon="4.895342">
        <ele>2.8</ele>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""

route = read_gpx_string(gpx_xml)
print(route.track_points)
```

---

## Writing Files

### Write to GPX

```python
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.gpx_writer import write_gpx

# Load an existing route
route = read_gpx("/path/to/input.gpx")

# Modify if needed (see examples below)
# ...

# Save to a new GPX file
write_gpx(route, "/path/to/output.gpx")
```

### Write to TCX

```python
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.tcx_writer import write_tcx

# Load a GPX and save as TCX
route = read_gpx("/path/to/input.gpx")
write_tcx(route, "/path/to/output.tcx")
```

### Convert TCX to GPX

```python
from gpx_editor.io.tcx_reader import read_tcx
from gpx_editor.io.gpx_writer import write_gpx

route = read_tcx("/path/to/activity.tcx")
write_gpx(route, "/path/to/activity.gpx")
```

---

## Creating Route Data Programmatically

### Create Empty DataFrames

```python
from gpx_editor.models.route import (
    RouteData,
    empty_track_points,
    empty_cues,
    empty_pois,
)

# Create an empty route
route = RouteData(
    track_points=empty_track_points(),
    cues=empty_cues(),
    pois=empty_pois(),
    source_file="",
)
```

### Create a Route with Data

```python
from datetime import datetime, timezone
import polars as pl
from gpx_editor.models.route import (
    RouteData,
    TRACK_POINTS_SCHEMA,
    CUES_SCHEMA,
    POIS_SCHEMA,
)

# Create track points
track_points = pl.DataFrame({
    "index":     [0, 1, 2],
    "lat":       [52.370216, 52.370312, 52.370458],
    "lon":       [4.895168, 4.895342, 4.895521],
    "elevation": [2.5, 2.8, 3.1],
    "time":      [
        datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2024, 6, 15, 10, 0, 5, tzinfo=timezone.utc),
        datetime(2024, 6, 15, 10, 0, 10, tzinfo=timezone.utc),
    ],
    "distance":  [0.0, 15.3, 32.7],
    "hr":        [120, 122, 125],
    "cadence":   [85, 87, 88],
    "power":     [180, 185, 190],
}, schema=TRACK_POINTS_SCHEMA)

# Create cues
cues = pl.DataFrame({
    "index":       [0],
    "lat":         [52.370312],
    "lon":         [4.895342],
    "name":        ["Turn Left onto Main St"],
    "description": ["At the traffic light"],
    "cue_type":    ["Left"],
    "distance":    [15.3],
}, schema=CUES_SCHEMA)

# Create POIs
pois = pl.DataFrame({
    "index":       [0],
    "lat":         [52.370458],
    "lon":         [4.895521],
    "name":        ["Coffee Shop"],
    "description": ["Great espresso"],
    "symbol":      ["food"],
    "distance":    [32.7],
}, schema=POIS_SCHEMA)

# Assemble the route
route = RouteData(
    track_points=track_points,
    cues=cues,
    pois=pois,
    source_file="custom_route",
)
```

---

## Snapping POIs to Track Points

The `nearest_index` function finds the closest track point to any coordinate.

### Basic Snapping

```python
from gpx_editor.io._distance import nearest_index
from gpx_editor.io.gpx_reader import read_gpx

# Load a route
route = read_gpx("/path/to/route.gpx")
tp = route.track_points

# Extract arrays for fast lookup
track_lats = tp["lat"].to_numpy()
track_lons = tp["lon"].to_numpy()
track_dists = tp["distance"].to_numpy()

# POI location (not on the track)
poi_lat = 52.371500
poi_lon = 4.897100

# Find nearest track point
snap_idx, distance_m = nearest_index(poi_lat, poi_lon, track_lats, track_lons)

print(f"Nearest track point index: {snap_idx}")
print(f"Distance from POI to track: {distance_m:.1f} metres")

# Get snapped coordinates
snapped_lat = float(track_lats[snap_idx])
snapped_lon = float(track_lons[snap_idx])
snapped_distance = float(track_dists[snap_idx])

print(f"Snapped lat/lon: ({snapped_lat}, {snapped_lon})")
print(f"Distance along route: {snapped_distance:.1f} metres")
```

### Add a New POI Snapped to Track

```python
import polars as pl
from gpx_editor.io._distance import nearest_index
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.gpx_writer import write_gpx
from gpx_editor.models.route import RouteData, POIS_SCHEMA

# Load route
route = read_gpx("/path/to/route.gpx")
tp = route.track_points

# POI to add (raw coordinates)
new_poi_lat = 52.378200
new_poi_lon = 4.903400
new_poi_name = "Water Station"
new_poi_symbol = "water"

# Snap to track
track_lats = tp["lat"].to_numpy()
track_lons = tp["lon"].to_numpy()
track_dists = tp["distance"].to_numpy()

snap_idx, dist_m = nearest_index(new_poi_lat, new_poi_lon, track_lats, track_lons)

# Reject if too far from track (optional)
MAX_SNAP_DISTANCE_M = 50.0
if dist_m > MAX_SNAP_DISTANCE_M:
    print(f"POI is {dist_m:.1f}m from track - too far to snap!")
else:
    # Create snapped POI
    snapped_lat = float(track_lats[snap_idx])
    snapped_lon = float(track_lons[snap_idx])
    snapped_dist = float(track_dists[snap_idx])

    # Determine next index
    existing_pois = route.pois
    if len(existing_pois) > 0:
        next_idx = int(existing_pois["index"].max()) + 1
    else:
        next_idx = 0

    # Build new POI row
    new_poi = pl.DataFrame({
        "index":       [next_idx],
        "lat":         [snapped_lat],
        "lon":         [snapped_lon],
        "name":        [new_poi_name],
        "description": [None],
        "symbol":      [new_poi_symbol],
        "distance":    [snapped_dist],
    }, schema=POIS_SCHEMA)

    # Concatenate and sort by distance
    updated_pois = pl.concat([existing_pois, new_poi]).sort("distance")

    # Reset index column
    updated_pois = updated_pois.with_columns(
        pl.Series("index", list(range(len(updated_pois))), dtype=pl.Int64)
    )

    # Create new RouteData (immutable pattern)
    updated_route = RouteData(
        track_points=route.track_points,
        cues=route.cues,
        pois=updated_pois,
        source_file=route.source_file,
    )

    # Save
    write_gpx(updated_route, "/path/to/output.gpx")
    print(f"Added POI '{new_poi_name}' at {snapped_dist:.0f}m along route")
```

### Snap Multiple POIs from a List

```python
import polars as pl
from gpx_editor.io._distance import nearest_index
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.models.route import RouteData, POIS_SCHEMA

# Load route
route = read_gpx("/path/to/route.gpx")
tp = route.track_points
track_lats = tp["lat"].to_numpy()
track_lons = tp["lon"].to_numpy()
track_dists = tp["distance"].to_numpy()

# POIs to add
raw_pois = [
    {"lat": 52.371500, "lon": 4.897100, "name": "Water Station", "symbol": "water"},
    {"lat": 52.378200, "lon": 4.903400, "name": "Café", "symbol": "food"},
    {"lat": 52.385900, "lon": 4.912300, "name": "Viewpoint", "symbol": "scenic"},
]

# Snap each POI
snapped_rows = []
for i, poi in enumerate(raw_pois):
    snap_idx, dist_m = nearest_index(poi["lat"], poi["lon"], track_lats, track_lons)
    
    snapped_rows.append({
        "index": i,
        "lat": float(track_lats[snap_idx]),
        "lon": float(track_lons[snap_idx]),
        "name": poi["name"],
        "description": None,
        "symbol": poi["symbol"],
        "distance": float(track_dists[snap_idx]),
    })
    print(f"'{poi['name']}' snapped to track ({dist_m:.1f}m away)")

# Create DataFrame and sort
new_pois = pl.DataFrame(snapped_rows, schema=POIS_SCHEMA).sort("distance")

# Reset index after sorting
new_pois = new_pois.with_columns(
    pl.Series("index", list(range(len(new_pois))), dtype=pl.Int64)
)

# Create updated route
updated_route = RouteData(
    track_points=route.track_points,
    cues=route.cues,
    pois=new_pois,
    source_file=route.source_file,
)
```

---

## Distance Calculations

### Calculate Distance Between Two Points

```python
from gpx_editor.io._distance import haversine

# Single point pair
lat1, lon1 = 52.370216, 4.895168
lat2, lon2 = 52.370312, 4.895342

distance_m = haversine(lat1, lon1, lat2, lon2)
print(f"Distance: {float(distance_m):.1f} metres")
```

### Vectorized Distance Calculation

```python
import numpy as np
from gpx_editor.io._distance import haversine

# Multiple point pairs (vectorized)
lats1 = np.array([52.370216, 52.371000, 52.372000])
lons1 = np.array([4.895168, 4.896000, 4.897000])
lats2 = np.array([52.370312, 52.371100, 52.372100])
lons2 = np.array([4.895342, 4.896200, 4.897200])

distances = haversine(lats1, lons1, lats2, lons2)
print(f"Distances: {distances}")  # Array of distances in metres
```

### Calculate Cumulative Distance for a Track

```python
import numpy as np
from gpx_editor.io._distance import cumulative_distance

# Coordinates of a track
lats = np.array([52.370216, 52.370312, 52.370458, 52.370621])
lons = np.array([4.895168, 4.895342, 4.895521, 4.895698])

distances = cumulative_distance(lats, lons)
print(f"Cumulative distances: {distances}")
# Output: [0.0, 15.3, 32.7, 51.2]

print(f"Total route length: {distances[-1]:.1f} metres")
```

---

## Merging Cues/POIs Between Routes

Use the merge module to copy cues and POIs from one route to another.

```python
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.gpx_writer import write_gpx
from gpx_editor.logic.merge import copy_cues_pois

# Load source route (has cues/POIs)
source = read_gpx("/path/to/original_route.gpx")

# Load target route (new track, no cues/POIs)
target = read_gpx("/path/to/new_track.gpx")

# Merge: copy cues/POIs within 10 metres of the new track
merged = copy_cues_pois(source, target, threshold_m=10.0)

print(f"Copied {len(merged.cues)} cues")
print(f"Copied {len(merged.pois)} POIs")

# Save the merged route
write_gpx(merged, "/path/to/merged_route.gpx")
```

---

## Querying OpenStreetMap for POIs

The `osm_reader` module provides functions to query the Overpass API for amenities
near your route (water taps, fuel stations, cafes, etc.).

### Available POI Categories

```python
from gpx_editor.io.osm_reader import OSM_CATEGORIES

# View all available categories
for category, tags in OSM_CATEGORIES.items():
    print(f"{category}: {tags}")
```

**Output:**

```
Drinking Water: [('amenity', 'drinking_water')]
Fuel Station: [('amenity', 'fuel')]
Hotel: [('tourism', 'hotel')]
Motel: [('tourism', 'motel')]
Convenience Store: [('shop', 'convenience')]
Supermarket: [('shop', 'supermarket')]
Restaurant: [('amenity', 'restaurant')]
Cafe: [('amenity', 'cafe')]
Parking: [('amenity', 'parking')]
Campsite: [('tourism', 'camp_site')]
Pharmacy: [('amenity', 'pharmacy')]
```

### Query Water Taps Along a Route

```python
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.osm_reader import track_bbox, query_osm_pois, OSM_CATEGORIES

# Load your route
route = read_gpx("/path/to/route.gpx")

# Calculate bounding box with 100m buffer around the track
buffer_m = 100
south, west, north, east = track_bbox(route.track_points, buffer_m)

# Query OSM for drinking water points
tags = OSM_CATEGORIES["Drinking Water"]  # [("amenity", "drinking_water")]
water_pois = query_osm_pois(south, west, north, east, tags)

print(f"Found {len(water_pois)} water taps near the route")
print(water_pois)
```

**Output:**

```
Found 8 water taps near the route

shape: (8, 5)
┌───────────┬──────────┬────────────────────┬─────────────┬────────┐
│ lat       ┆ lon      ┆ name               ┆ description ┆ symbol │
│ ---       ┆ ---      ┆ ---                ┆ ---         ┆ ---    │
│ f64       ┆ f64      ┆ str                ┆ str         ┆ str    │
╞═══════════╪══════════╪════════════════════╪═════════════╪════════╡
│ 52.371234 ┆ 4.896543 ┆ Park Fountain      ┆ 24/7        ┆ water  │
│ 52.378901 ┆ 4.902345 ┆                    ┆             ┆ water  │
│ 52.385678 ┆ 4.911234 ┆ Sports Field Water ┆ 08:00-20:00 ┆ water  │
│ …         ┆ …        ┆ …                  ┆ …           ┆ …      │
└───────────┴──────────┴────────────────────┴─────────────┴────────┘
```

### Query Fuel Stations

```python
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.osm_reader import track_bbox, query_osm_pois, OSM_CATEGORIES

route = read_gpx("/path/to/route.gpx")

# Use a larger buffer for fuel stations (500m)
south, west, north, east = track_bbox(route.track_points, buffer_m=500)

tags = OSM_CATEGORIES["Fuel Station"]  # [("amenity", "fuel")]
fuel_pois = query_osm_pois(south, west, north, east, tags)

print(f"Found {len(fuel_pois)} fuel stations")
for row in fuel_pois.iter_rows(named=True):
    print(f"  - {row['name'] or 'Unnamed'} at ({row['lat']:.5f}, {row['lon']:.5f})")
```

### Query Multiple Categories at Once

```python
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.osm_reader import track_bbox, query_osm_pois
import polars as pl

route = read_gpx("/path/to/route.gpx")
south, west, north, east = track_bbox(route.track_points, buffer_m=200)

# Query multiple amenity types in one call using custom tags
tags = [
    ("amenity", "drinking_water"),
    ("amenity", "fuel"),
    ("amenity", "cafe"),
]
all_pois = query_osm_pois(south, west, north, east, tags)

# Group by symbol to see counts
print(all_pois.group_by("symbol").len())
```

### Add OSM POIs to Your Route (Snapped to Track)

```python
import polars as pl
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.gpx_writer import write_gpx
from gpx_editor.io.osm_reader import track_bbox, query_osm_pois, OSM_CATEGORIES
from gpx_editor.io._distance import nearest_index
from gpx_editor.models.route import RouteData, POIS_SCHEMA

# 1. Load route
route = read_gpx("/path/to/route.gpx")
tp = route.track_points
track_lats = tp["lat"].to_numpy()
track_lons = tp["lon"].to_numpy()
track_dists = tp["distance"].to_numpy()

# 2. Query OSM for water taps
south, west, north, east = track_bbox(tp, buffer_m=100)
osm_pois = query_osm_pois(south, west, north, east, OSM_CATEGORIES["Drinking Water"])

if len(osm_pois) == 0:
    print("No water taps found near route")
else:
    # 3. Snap each OSM POI to the track
    snapped_rows = []
    for row in osm_pois.iter_rows(named=True):
        snap_idx, dist_m = nearest_index(row["lat"], row["lon"], track_lats, track_lons)
        
        # Only add if within 100m of track
        if dist_m <= 100:
            snapped_rows.append({
                "index": len(snapped_rows),
                "lat": float(track_lats[snap_idx]),
                "lon": float(track_lons[snap_idx]),
                "name": row["name"] or "Water Tap",
                "description": row["description"],
                "symbol": row["symbol"],
                "distance": float(track_dists[snap_idx]),
            })
    
    if snapped_rows:
        # 4. Create DataFrame and merge with existing POIs
        new_pois = pl.DataFrame(snapped_rows, schema=POIS_SCHEMA)
        combined = pl.concat([route.pois, new_pois]).sort("distance")
        combined = combined.with_columns(
            pl.Series("index", list(range(len(combined))), dtype=pl.Int64)
        )
        
        # 5. Save updated route
        updated = RouteData(
            track_points=tp,
            cues=route.cues,
            pois=combined,
            source_file=route.source_file,
        )
        write_gpx(updated, "/path/to/route_with_water.gpx")
        print(f"Added {len(snapped_rows)} water taps to route")
```

### Query with Custom Bounding Box

```python
from gpx_editor.io.osm_reader import query_osm_pois

# Manual bounding box (south, west, north, east)
# Example: Amsterdam city center
south, west = 52.35, 4.85
north, east = 52.40, 4.95

# Query for supermarkets
supermarkets = query_osm_pois(
    south, west, north, east,
    tags=[("shop", "supermarket")],
    timeout=30,  # Increase timeout for large areas
)

print(f"Found {len(supermarkets)} supermarkets")
```

### Query with Custom OSM Tags

```python
from gpx_editor.io.osm_reader import query_osm_pois, track_bbox
from gpx_editor.io.gpx_reader import read_gpx

route = read_gpx("/path/to/route.gpx")
bbox = track_bbox(route.track_points, buffer_m=500)

# Query for bicycle repair stations (not in predefined categories)
bike_repair = query_osm_pois(
    *bbox,
    tags=[("amenity", "bicycle_repair_station")],
)

# Query for public toilets
toilets = query_osm_pois(
    *bbox,
    tags=[("amenity", "toilets")],
)

# Query for multiple custom tags
supplies = query_osm_pois(
    *bbox,
    tags=[
        ("shop", "bicycle"),      # Bike shops
        ("shop", "sports"),       # Sports shops
        ("amenity", "pharmacy"),  # Pharmacies
    ],
)
```

---

## Working with Route Entries (GUI Context)

When working with multiple routes in the GUI, routes are wrapped in `RouteEntry`.

```python
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.models.route_entry import RouteEntry, next_color
from pathlib import Path

# Load multiple routes
paths = ["/path/to/route1.gpx", "/path/to/route2.gpx", "/path/to/route3.gpx"]
entries: list[RouteEntry] = []
used_colors: list[str] = []

for path in paths:
    route = read_gpx(path)
    color = next_color(used_colors)
    used_colors.append(color)
    
    entry = RouteEntry(
        route=route,
        color=color,
        label=Path(path).stem,
        visible=True,
    )
    entries.append(entry)

# Access route data from an entry
active_entry = entries[0]
print(f"Label: {active_entry.label}")
print(f"Color: {active_entry.color}")
print(f"Track points: {len(active_entry.route.track_points)}")
```

---

## Complete Example: Load, Modify, Save

```python
from gpx_editor.io.gpx_reader import read_gpx
from gpx_editor.io.gpx_writer import write_gpx
from gpx_editor.io._distance import nearest_index
from gpx_editor.models.route import RouteData, POIS_SCHEMA
import polars as pl

# 1. Load route
route = read_gpx("/path/to/input.gpx")
print(f"Loaded {len(route.track_points)} track points, {len(route.pois)} POIs")

# 2. Add a new POI snapped to track
tp = route.track_points
track_lats = tp["lat"].to_numpy()
track_lons = tp["lon"].to_numpy()
track_dists = tp["distance"].to_numpy()

# New POI coordinates
poi_lat, poi_lon = 52.375000, 4.900000
snap_idx, _ = nearest_index(poi_lat, poi_lon, track_lats, track_lons)

new_poi = pl.DataFrame({
    "index": [len(route.pois)],
    "lat": [float(track_lats[snap_idx])],
    "lon": [float(track_lons[snap_idx])],
    "name": ["Rest Stop"],
    "description": ["Midway break point"],
    "symbol": ["rest"],
    "distance": [float(track_dists[snap_idx])],
}, schema=POIS_SCHEMA)

# 3. Combine POIs
updated_pois = pl.concat([route.pois, new_poi]).sort("distance")
updated_pois = updated_pois.with_columns(
    pl.Series("index", list(range(len(updated_pois))), dtype=pl.Int64)
)

# 4. Create updated route (immutable)
updated_route = RouteData(
    track_points=route.track_points,
    cues=route.cues,
    pois=updated_pois,
    source_file=route.source_file,
)

# 5. Save
write_gpx(updated_route, "/path/to/output.gpx")
print(f"Saved with {len(updated_route.pois)} POIs")
```
