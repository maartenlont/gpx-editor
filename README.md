# GPX Editor

A desktop application for viewing and editing GPX/TCX route files, with a focus on managing cues and POIs — in particular copying them from one route onto a different track.

## Features

- Load GPX and TCX files (track points, cues, POIs)
- Interactive Leaflet map with icons per cue/POI type
- Elevation profile with clickable cursor
- Sortable tables for track points, cues, and POIs — click any row to zoom the map
- Click the elevation chart to jump to that location on the map and in the tables
- **Merge workflow**: load a second route file and copy cues/POIs from the first file into the second track based on a configurable distance threshold (default 10 m)
- Save the result as GPX or TCX

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
git clone <repo-url>
cd gpx_editor
uv sync
```

## Running

```bash
uv run python main.py
```

## Workflow: merging cues from one route into another

1. **File → Open** — load the route that has the cues and POIs you want to keep.
2. **File → Open Second File** — load the new route whose track you want to use.
3. **Edit → Merge Cues & POIs…** — opens the merge dialog.
   - Adjust the snap radius (default 10 m): cues/POIs within this distance of any point on the second track will be copied across.
   - Click **Preview** to see the result on the map without committing.
   - Click **Apply** to confirm, or **Cancel** to revert.
4. **File → Save As…** — save the merged route as GPX or TCX.

## Development

Run the test suite:

```bash
uv run pytest
```

Run with coverage:

```bash
uv run pytest --cov=src
```

## Keyboard shortcuts

| Key | Action |
|-----|--------|
| Ctrl+O | Open file |
| Ctrl+S | Save As |
| Ctrl+Q | Quit |
