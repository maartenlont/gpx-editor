# GPX Editor — Implementation Plan

## Progress

### Phase 1 — Data layer
- [x] `models/route.py` — RouteData dataclass + column schemas
- [x] `io/_distance.py` — Haversine, cumulative distance, nearest-index
- [x] `io/gpx_reader.py` — parse GPX → 3 DataFrames (incl. Garmin extensions)
- [x] `io/tcx_reader.py` — parse TCX Course/Activity → 3 DataFrames
- [x] `io/gpx_writer.py` — serialise RouteData → GPX 1.1
- [x] `io/tcx_writer.py` — serialise RouteData → TCX Course
- [x] Tests: 71 passing (models, io readers, io round-trips)

### Phase 2 — Merge logic
- [x] `logic/merge.py` — copy cues/POIs by proximity
- [x] Tests: `tests/logic/test_merge.py` (27 passing)

### Phase 3 — GUI skeleton
- [x] `ui/dataframe_table.py` — generic Polars DataFrame model + table widget
- [x] `ui/map_widget.py` — Folium/Leaflet map in QWebEngineView
- [x] `ui/elevation_widget.py` — matplotlib elevation profile
- [x] `ui/right_panel.py` — QTabWidget with counts in tab labels
- [x] `main_window.py` — splitter layout, File → Open, status bar
- [x] `app.py` — QApplication entry point
- [x] `main.py` — thin launcher

### Phase 4 — File I/O integration
- [x] File → Save As (GPX / TCX) with Ctrl+S shortcut
- [x] Dirty indicator (`*`) in window title

### Phase 5 — Merge workflow
- [x] File → Open Second File (enabled after first file is loaded)
- [x] Edit → Merge Cues & POIs… dialog with threshold spinbox, preview, apply, cancel

### Phase 6 — Polish
- [x] Keyboard shortcuts (Ctrl+O, Ctrl+S, Ctrl+Q)
- [x] Error dialogs for malformed files
- [x] Polyline downsampling for large files (>5 000 points)
- [x] README with install, run, workflow, and shortcut docs

### Phase 7 — Multi-route support
- [x] `models/route_entry.py` — `RouteEntry` dataclass wrapping `RouteData` + display color
- [x] `ui/route_list_widget.py` — routes panel: list of loaded routes, color swatch, remove button
- [x] `ui/right_panel.py` — add "Routes" tab containing the route list widget
- [x] `ui/map_widget.py` — render all loaded routes simultaneously; each polyline in its own color; cue/POI markers only for the active route
- [x] `ui/elevation_widget.py` — overlay elevation profiles of all routes; active route highlighted
- [x] `main_window.py` — File → Open adds to route list instead of replacing; switching active route refreshes tables and elevation cursor
- [x] Save As and Merge operate on the active route

---

## Goal

A desktop GUI application (PySide6) that:
1. Loads GPX / TCX files containing track points, cues, and POIs.
2. Displays the route on an interactive map with icons for cues and POIs.
3. Shows an elevation profile below the map.
4. Provides tabbed panels (track points / cues / POIs); clicking a row zooms the map.
5. Stores all loaded data internally as Polars DataFrames.
6. Loads a second GPX / TCX file and copies cues/POIs from the first file into the new
   track when coordinates are within a configurable distance threshold (default 10 m).
7. Saves the result to a GPX or TCX file.

---

## File Hierarchy

```
gpx_editor/
├── docs/
│   └── plan.md                  # this file
├── resources/
│   └── icons/                   # cue icons (turn_left.png, turn_right.png, etc.)
├── src/
│   └── gpx_editor/
│       ├── __init__.py
│       ├── app.py               # QApplication entry point
│       ├── main_window.py       # MainWindow — assembles all widgets
│       │
│       ├── io/
│       │   ├── __init__.py
│       │   ├── gpx_reader.py    # parse GPX → DataFrames
│       │   ├── tcx_reader.py    # parse TCX → DataFrames
│       │   ├── gpx_writer.py    # write DataFrames → GPX
│       │   └── tcx_writer.py    # write DataFrames → TCX
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── route.py         # RouteData dataclass holding the three DataFrames
│       │   └── route_entry.py   # RouteEntry (RouteData + color + label + visible)
│       │
│       ├── logic/
│       │   ├── __init__.py
│       │   └── merge.py         # copy cues/POIs by proximity between two routes
│       │
│       └── ui/
│           ├── __init__.py
│           ├── map_widget.py        # interactive map (QWebEngineView + Leaflet)
│           ├── elevation_widget.py  # matplotlib FigureCanvas elevation profile
│           ├── dataframe_table.py   # generic Polars DataFrame model + table widget
│           ├── right_panel.py       # QTabWidget: Routes + Track Points + Cues + POIs
│           ├── route_list_widget.py # per-route list with colour swatches (Phase 7)
│           └── merge_dialog.py      # dialog to pick second file + distance threshold
├── tests/
│   ├── conftest.py              # shared fixtures (sample DataFrames, tmp file paths)
│   ├── io/
│   │   ├── test_gpx_reader.py
│   │   ├── test_tcx_reader.py
│   │   ├── test_gpx_writer.py
│   │   └── test_tcx_writer.py
│   ├── logic/
│   │   └── test_merge.py
│   └── models/
│       └── test_route.py
├── main.py                      # thin launcher: `from src.gpx_editor.app import run; run()`
├── pyproject.toml
└── README.md
```

---

## Data Model

All file content is stored in three Polars DataFrames inside a `RouteData` dataclass
(defined in `src/gpx_editor/models/route.py`).

### `track_points` DataFrame

| column      | dtype    | notes                        |
|-------------|----------|------------------------------|
| `index`     | Int64    | sequential, 0-based          |
| `lat`       | Float64  |                              |
| `lon`       | Float64  |                              |
| `elevation` | Float64  | metres, nullable             |
| `time`      | Datetime | UTC, nullable                |
| `distance`  | Float64  | cumulative metres from start |
| `hr`        | Int32    | heart rate, nullable         |
| `cadence`   | Int32    | nullable                     |
| `power`     | Int32    | nullable                     |

### `cues` DataFrame

| column        | dtype   | notes                              |
|---------------|---------|------------------------------------|
| `index`       | Int64   |                                    |
| `lat`         | Float64 |                                    |
| `lon`         | Float64 |                                    |
| `name`        | String  |                                    |
| `description` | String  | nullable                           |
| `cue_type`    | String  | e.g. `turn_left`, `turn_right`, … |
| `distance`    | Float64 | cumulative metres from start       |

### `pois` DataFrame

| column        | dtype   | notes        |
|---------------|---------|--------------|
| `index`       | Int64   |              |
| `lat`         | Float64 |              |
| `lon`         | Float64 |              |
| `name`        | String  |              |
| `description` | String  | nullable     |
| `symbol`      | String  | icon/symbol  |
| `distance`    | Float64 | cumulative m |

---

## GPX / TCX Mapping

### GPX source elements

| DataFrame     | GPX element                                                    |
|---------------|----------------------------------------------------------------|
| track_points  | `<trkpt>` inside `<trk>/<trkseg>`                             |
| cues          | `<wpt>` with `<type>` matching a cue category, **or** Garmin  |
|               | `<extensions><gpxx:WaypointExtension><gpxx:Categories>`       |
| pois          | `<wpt>` elements that are not classified as cues               |

### TCX source elements

| DataFrame     | TCX element                                                    |
|---------------|----------------------------------------------------------------|
| track_points  | `<Trackpoint>` inside `<Track>`                               |
| cues          | `<CoursePoint>` (type ≠ `Generic`)                            |
| pois          | `<CoursePoint>` with type `Generic`                            |

---

## Implementation Phases

### Phase 1 — Data layer (`src/gpx_editor/io/`, `src/gpx_editor/models/`)

**Goal:** parse files into DataFrames; no GUI yet.

Tasks:
1. Define `RouteData` in `models/route.py`.
2. Implement `gpx_reader.py`:
   - Parse XML with `xml.etree.ElementTree`.
   - Produce the three DataFrames.
   - Compute `distance` column using the Haversine formula.
3. Implement `tcx_reader.py` with the same output contract.
4. Implement `gpx_writer.py` — serialise DataFrames back to valid GPX.
5. Implement `tcx_writer.py` — serialise DataFrames back to valid TCX.

Tests (`tests/io/`):
- Round-trip: `read → write → read` and assert DataFrames are equal.
- Edge cases: empty cues/POIs, missing elevation, missing timestamps.
- `conftest.py` provides minimal valid GPX/TCX strings and `tmp_path` fixtures.

---

### Phase 2 — Merge logic (`src/gpx_editor/logic/merge.py`)

**Goal:** given two `RouteData` objects and a threshold (metres), return a new
`RouteData` where cues and POIs from `source` are copied into `target` whenever the
nearest track point in `target` is within the threshold.

Algorithm:
1. For each cue/POI in `source`, find the nearest track point in `target` using
   Haversine distance (vectorised with Polars/NumPy).
2. If distance ≤ threshold, add the cue/POI to `target`'s DataFrame with the
   snapped lat/lon and recalculated `distance` value.
3. Re-sort by `distance`.
4. Return a new `RouteData` (immutable; do not mutate the originals).

Tests (`tests/logic/test_merge.py`):
- Cue within threshold → copied.
- Cue outside threshold → not copied.
- Threshold boundary (exactly 10 m) → copied.
- Empty source cues → output identical to target.
- Distance column recalculated correctly after merge.

---

### Phase 3 — GUI skeleton (`src/gpx_editor/ui/`, `src/gpx_editor/main_window.py`)

**Goal:** a working window with the correct layout; data can be loaded and displayed.

Layout:

```
┌──────────────────────────────────────────────────────────────┐
│  Menu bar:  File | Edit | Help                               │
├──────────────────────────┬───────────────────────────────────┤
│                          │  ┌─ Tabs ──────────────────────┐  │
│   Map widget             │  │  Track Points │ Cues │ POIs  │  │
│   (QWebEngineView        │  │                              │  │
│    + Leaflet JS)         │  │  <QTableView>                │  │
│                          │  └──────────────────────────────┘  │
├──────────────────────────┤                                    │
│   Elevation profile      │                                    │
│   (matplotlib canvas)    │                                    │
└──────────────────────────┴───────────────────────────────────┘
```

Splitter ratios: map + elevation on the left (50 % width), tabs on the right (50 %).
The left side is itself a vertical QSplitter: map (~75 %) / elevation (~25 %).

Tasks:
1. `map_widget.py` — embed a Leaflet map via **Folium** in `QWebEngineView`.
   - On `load_route(route: RouteData)`: generate map HTML with Folium and load via
     `setHtml(map._repr_html_())`.
   - `zoom_to(lat, lon, zoom=16)` — callable from table row clicks via
     `page().runJavaScript("map.setView([lat, lon], zoom)")`.
   - **Cue markers**: use `folium.CustomIcon` with bundled PNG/SVG icons per `cue_type`
     (e.g. `turn_left.png`, `turn_right.png`). Store icons in `resources/icons/`.
   - **POI markers**: use `folium.Icon(prefix="fa")` mapped from the `symbol` column
     (e.g. `food` → `cutlery`, `water` → `tint`). Fallback to a generic pin icon.
   - **Polyline**: render track points with `folium.PolyLine`. For large files (100k+
     points), simplify with Ramer-Douglas-Peucker before rendering.
2. `elevation_widget.py` — matplotlib `FigureCanvas`.
   - Plots distance (x) vs elevation (y).
   - A vertical cursor line updates when a track-point row is selected.
3. `track_table.py`, `cue_table.py`, `poi_table.py` — each wraps a
   `QTableView` backed by a read-only `QAbstractTableModel` over a Polars DataFrame.
   - `rowSelected` signal emitted with `(lat, lon)` on row click.
4. `right_panel.py` — `QTabWidget` containing the three table widgets.
5. `main_window.py` — wires everything together; holds the current `RouteData`;
   connects table `rowSelected` → `map_widget.zoom_to` and elevation cursor.

---

### Phase 4 — File I/O integration (menu actions)

**Goal:** File → Open / Save / Save As work end-to-end.

Tasks:
1. `File > Open` — `QFileDialog` filtered to `*.gpx *.tcx`; dispatch to the correct
   reader; call `load_route` on all widgets.
2. `File > Save As` — `QFileDialog` to choose output path and format; dispatch to
   the correct writer.
3. Window title reflects the open file name and a `*` dirty indicator.

---

### Phase 5 — Merge workflow

**Goal:** load a second file, merge cues/POIs, preview, then save.

Tasks:
1. `File > Open Second File` — loads a second `RouteData`; stores it separately.
2. `Edit > Merge Cues & POIs…` opens `merge_dialog.py`:
   - Shows the file names for both routes.
   - Spin box for the distance threshold (default 10 m, min 1 m, max 500 m).
   - `Preview` button: runs `merge.copy_cues_pois(source, target, threshold)` and
     refreshes all widgets with the merged result (without overwriting the originals).
   - `Apply` button: commits the merged result as the active route.
   - `Cancel` button: reverts to the previous active route.
3. After apply, `File > Save As` saves the merged route.

---

### Phase 6 — Polish

- Status bar showing number of track points / cues / POIs, and total distance.
- Keyboard shortcut `Ctrl+O` to open, `Ctrl+S` to save.
- Error dialogs for malformed files.
- Polyline downsampling for large files (>5 000 track points).
- `README.md` with install, run, and merge workflow instructions.

---

### Phase 7 — Multi-route support

**Goal:** load any number of GPX/TCX files simultaneously; view all routes on the
map in different colours; switch the "active" route to inspect its tables and
elevation; change per-route colours interactively.

#### Data model

Add `src/gpx_editor/models/route_entry.py`:

```python
@dataclass
class RouteEntry:
    route: RouteData
    color: str        # CSS hex colour, e.g. "#1565C0"
    label: str        # display name — defaults to filename stem
    visible: bool = True
```

`MainWindow` replaces the single `_route` field with a list of `RouteEntry` objects
and an `_active_index: int`.  The active entry drives the tables, elevation chart, and
zoom behaviour; all visible entries are rendered on the map.

#### New file

**`src/gpx_editor/ui/route_list_widget.py`** — a `QWidget` that contains a
`QListWidget` where each item shows:
- A coloured rectangle (the route colour).
- The route label (filename stem).
- A remove button (×).

Interactions:
- **Single click** → set active route; tables and elevation chart update.
- **Double-click colour swatch** → open `QColorDialog`; update the swatch and
  re-render the map.
- **Remove button** → remove the route from the list; if it was active, activate the
  previous route (or clear the view if the list is empty).

Signals emitted by `RouteListWidget`:
| Signal | Payload | When |
|---|---|---|
| `active_changed` | `int` index | user selects a different route |
| `color_changed` | `int` index, `str` hex | user picks a new colour |
| `route_removed` | `int` index | user removes a route |

#### Right panel changes

Add a **"Routes"** tab (first tab) to `RightPanel` containing the `RouteListWidget`.
The existing Track Points / Cues / POIs tabs continue to show data for the active
route only.

#### Map widget changes

`load_routes(entries: list[RouteEntry])` replaces `load_route`:
- Renders one `folium.PolyLine` per visible entry using each entry's colour.
- Renders cue and POI markers **only for the active entry** (to avoid visual clutter).
- Accepts a separate `active_index` parameter so the map knows which markers to show.

`update_route_color(index: int, color: str)` — re-renders only the affected polyline
via `runJavaScript` without reloading the full map.

#### Elevation widget changes

`load_routes(entries: list[RouteEntry], active_index: int)`:
- Plots one elevation line per visible entry using each entry's colour, at reduced
  opacity (0.4) for inactive routes.
- The active route is drawn at full opacity with the red cursor line.

#### Main window changes

- **File → Open** appends a new `RouteEntry` with an auto-assigned colour (cycling
  through a palette) instead of replacing the current route.
- **File → Close Route** removes the active route from the list.
- Active-route switching updates tables, elevation, and map markers.
- **Save As**, **Merge**, and all row-selection interactions continue to operate on the
  active route only.

#### Colour palette

Assign colours from a fixed palette for new routes (cycling if more than 8 are
loaded):

```python
_PALETTE = [
    "#1565C0",  # blue      (primary)
    "#B71C1C",  # red
    "#2E7D32",  # green
    "#E65100",  # orange
    "#6A1B9A",  # purple
    "#00695C",  # teal
    "#F9A825",  # amber
    "#4E342E",  # brown
]
```

---

## Technology Choices

| Concern           | Choice                                   | Reason                                      |
|-------------------|------------------------------------------|---------------------------------------------|
| GUI framework     | PySide6                                  | specified; LGPL; best Python Qt binding     |
| Map rendering     | Folium (Leaflet.js) via QWebEngineView   | OSM tiles, custom icons, easy Python API    |
| Elevation chart   | matplotlib FigureCanvas (in PySide6)     | already in dependencies                     |
| Data storage      | Polars DataFrames                        | specified; fast; expressive                 |
| File parsing      | `xml.etree.ElementTree` (stdlib)         | no extra dep; sufficient for GPX/TCX        |
| Distance calc     | Haversine (pure Python / NumPy vectorised) | accurate for cycling distances             |
| Tests             | pytest + pytest-qt                       | specified; pytest-qt for widget tests       |

---

## Dependency Updates Needed

Add to `pyproject.toml`:

```toml
dependencies = [
    "folium>=0.19.0",
    "matplotlib>=3.10.9",
    "numpy>=2.4.6",
    "polars>=1.41.2",
    "pyside6>=6.11.1",
]

[dependency-groups]
dev = [
    "pytest>=9.0.3",
    "pytest-qt>=4.4.0",
]
```

---

## Key Invariants

- Readers and writers are pure functions (no global state). Each returns / accepts a
  `RouteData`; they never mutate it.
- All distance values are in **metres**.
- All coordinates are **WGS-84 decimal degrees**.
- The merge operation returns a **new** `RouteData`; originals are never modified.
- GUI widgets are dumb: they only render what they are given. Business logic lives in
  `io/` and `logic/`.

---

## Open Questions (to resolve before building)

1. **Cue type vocabulary** — GPX has no standard cue type; Garmin extensions use
   strings like `"Left"`, `"Right"`, `"Straight"`. TCX `<CoursePoint>` has an
   enumerated `<PointType>`. Decide on a canonical internal enum or string set.
2. **Offline maps** — Leaflet needs a tile server. Use OpenStreetMap tiles
   (requires internet) or bundle a local tile provider (MBTiles). Default to OSM
   with a note in the UI when offline.
3. **Large files** — GPX files can have 100 k+ track points. The map widget should
   simplify the polyline (e.g. Ramer-Douglas-Peucker) for rendering performance.
   The tables should use a virtual model (`canFetchMore` / `fetchMore`).
4. **Second-file coordinate system** — both files are assumed WGS-84. Add a warning
   if the bounding boxes do not overlap.
