"""Shared fixtures for GPX editor tests."""

import pytest

# ---------------------------------------------------------------------------
# Minimal valid GPX string with track points, one cue, one POI
# ---------------------------------------------------------------------------
SAMPLE_GPX = """\
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test"
     xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="52.3702" lon="4.8952">
    <name>Turn Left</name>
    <desc>Sharp corner</desc>
    <type>Left</type>
  </wpt>
  <wpt lat="52.3710" lon="4.8960">
    <name>Coffee stop</name>
    <desc>Great espresso</desc>
    <sym>Coffee</sym>
  </wpt>
  <trk>
    <trkseg>
      <trkpt lat="52.3700" lon="4.8950">
        <ele>5.0</ele>
        <time>2024-01-01T09:00:00Z</time>
      </trkpt>
      <trkpt lat="52.3701" lon="4.8951">
        <ele>5.5</ele>
        <time>2024-01-01T09:00:10Z</time>
      </trkpt>
      <trkpt lat="52.3702" lon="4.8952">
        <ele>6.0</ele>
        <time>2024-01-01T09:00:20Z</time>
      </trkpt>
      <trkpt lat="52.3710" lon="4.8960">
        <ele>7.0</ele>
        <time>2024-01-01T09:01:00Z</time>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""

# GPX with Garmin TrackPointExtension (HR + cadence)
SAMPLE_GPX_WITH_EXTENSIONS = """\
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <trk>
    <trkseg>
      <trkpt lat="52.3700" lon="4.8950">
        <ele>5.0</ele>
        <time>2024-01-01T09:00:00Z</time>
        <extensions>
          <gpxtpx:TrackPointExtension>
            <gpxtpx:hr>145</gpxtpx:hr>
            <gpxtpx:cad>90</gpxtpx:cad>
          </gpxtpx:TrackPointExtension>
        </extensions>
      </trkpt>
      <trkpt lat="52.3701" lon="4.8951">
        <ele>5.5</ele>
        <time>2024-01-01T09:00:10Z</time>
        <extensions>
          <gpxtpx:TrackPointExtension>
            <gpxtpx:hr>148</gpxtpx:hr>
            <gpxtpx:cad>92</gpxtpx:cad>
          </gpxtpx:TrackPointExtension>
        </extensions>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""

# GPX with no cues or POIs
SAMPLE_GPX_NO_WAYPOINTS = """\
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test"
     xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <trkseg>
      <trkpt lat="52.3700" lon="4.8950">
        <ele>5.0</ele>
      </trkpt>
      <trkpt lat="52.3701" lon="4.8951">
        <ele>5.5</ele>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
"""

# GPX with no elevation or timestamps
SAMPLE_GPX_MINIMAL = """\
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test"
     xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <trkseg>
      <trkpt lat="52.3700" lon="4.8950"/>
      <trkpt lat="52.3701" lon="4.8951"/>
      <trkpt lat="52.3702" lon="4.8952"/>
    </trkseg>
  </trk>
</gpx>
"""

# ---------------------------------------------------------------------------
# Minimal valid TCX string
# ---------------------------------------------------------------------------
_TCX_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"

SAMPLE_TCX = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="{_TCX_NS}">
  <Courses>
    <Course>
      <Name>Test Course</Name>
      <CoursePoint>
        <Name>Turn Right</Name>
        <Position>
          <LatitudeDegrees>52.3702</LatitudeDegrees>
          <LongitudeDegrees>4.8952</LongitudeDegrees>
        </Position>
        <PointType>Right</PointType>
        <Notes>Go right here</Notes>
      </CoursePoint>
      <CoursePoint>
        <Name>Water fountain</Name>
        <Position>
          <LatitudeDegrees>52.3710</LatitudeDegrees>
          <LongitudeDegrees>4.8960</LongitudeDegrees>
        </Position>
        <PointType>Generic</PointType>
      </CoursePoint>
      <Track>
        <Trackpoint>
          <Time>2024-01-01T09:00:00Z</Time>
          <Position>
            <LatitudeDegrees>52.3700</LatitudeDegrees>
            <LongitudeDegrees>4.8950</LongitudeDegrees>
          </Position>
          <AltitudeMeters>5.0</AltitudeMeters>
          <HeartRateBpm><Value>140</Value></HeartRateBpm>
          <Cadence>88</Cadence>
        </Trackpoint>
        <Trackpoint>
          <Time>2024-01-01T09:00:10Z</Time>
          <Position>
            <LatitudeDegrees>52.3701</LatitudeDegrees>
            <LongitudeDegrees>4.8951</LongitudeDegrees>
          </Position>
          <AltitudeMeters>5.5</AltitudeMeters>
          <HeartRateBpm><Value>142</Value></HeartRateBpm>
          <Cadence>89</Cadence>
        </Trackpoint>
        <Trackpoint>
          <Time>2024-01-01T09:00:20Z</Time>
          <Position>
            <LatitudeDegrees>52.3702</LatitudeDegrees>
            <LongitudeDegrees>4.8952</LongitudeDegrees>
          </Position>
          <AltitudeMeters>6.0</AltitudeMeters>
          <HeartRateBpm><Value>145</Value></HeartRateBpm>
        </Trackpoint>
        <Trackpoint>
          <Time>2024-01-01T09:01:00Z</Time>
          <Position>
            <LatitudeDegrees>52.3710</LatitudeDegrees>
            <LongitudeDegrees>4.8960</LongitudeDegrees>
          </Position>
          <AltitudeMeters>7.0</AltitudeMeters>
        </Trackpoint>
      </Track>
    </Course>
  </Courses>
</TrainingCenterDatabase>
"""

SAMPLE_TCX_NO_COURSE_POINTS = f"""\
<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="{_TCX_NS}">
  <Courses>
    <Course>
      <Name>Empty Course</Name>
      <Track>
        <Trackpoint>
          <Position>
            <LatitudeDegrees>52.3700</LatitudeDegrees>
            <LongitudeDegrees>4.8950</LongitudeDegrees>
          </Position>
          <AltitudeMeters>5.0</AltitudeMeters>
        </Trackpoint>
        <Trackpoint>
          <Position>
            <LatitudeDegrees>52.3701</LatitudeDegrees>
            <LongitudeDegrees>4.8951</LongitudeDegrees>
          </Position>
          <AltitudeMeters>5.5</AltitudeMeters>
        </Trackpoint>
      </Track>
    </Course>
  </Courses>
</TrainingCenterDatabase>
"""
