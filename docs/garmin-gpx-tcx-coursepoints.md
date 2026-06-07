# Garmin GPX & TCX Format: Course Points Reference

## GPX vs TCX: The Key Distinction

Standard GPX 1.1 does not natively support course points. GPX does not support course points — you need to export as either TCX or FIT to get course points in the file.

GPX files use the standard `<wpt>` (waypoint) element, but Garmin’s Edge devices treat waypoints and course points as fundamentally different things. Course points are properly encoded in **TCX** (Training Center XML) format.

-----

## The TCX Format and Course Points

TCX is a data exchange format introduced in 2007 as part of Garmin’s Training Center product. It is similar to GPX since it exchanges GPS tracks, but treats a track as an Activity rather than simply a series of GPS points.

Official schema: `https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd`

### CoursePoint Structure

```xml
<CoursePoint>
  <Name>...</Name>                       <!-- max 10 characters -->
  <Time>...</Time>                       <!-- xsd:dateTime, UTC -->
  <Position>
    <LatitudeDegrees>...</LatitudeDegrees>
    <LongitudeDegrees>...</LongitudeDegrees>
  </Position>
  <AltitudeMeters>...</AltitudeMeters>   <!-- optional -->
  <PointType>...</PointType>             <!-- see enum below -->
  <Notes>...</Notes>                     <!-- optional, free text -->
  <Extensions/>                          <!-- optional -->
</CoursePoint>
```

#### Real-world example

```xml
<CoursePoint>
  <Name>Roch Treve</Name>
  <Time>2024-09-12T14:35:30Z</Time>
  <Position>
    <LatitudeDegrees>48.411522</LatitudeDegrees>
    <LongitudeDegrees>-3.890157</LongitudeDegrees>
  </Position>
  <PointType>Generic</PointType>
  <Notes>Roc'h Trevezel</Notes>
</CoursePoint>
```

-----

## All Supported PointType Values

From the official `CoursePointType_t` enum in `TrainingCenterDatabasev2.xsd`:

|Value          |Use Case                    |
|---------------|----------------------------|
|`Generic`      |General-purpose POI         |
|`Summit`       |Mountain top / high point   |
|`Valley`       |Valley / low point          |
|`Water`        |Water source                |
|`Food`         |Food stop                   |
|`Danger`       |Hazard                      |
|`Left`         |Turn left (navigation cue)  |
|`Right`        |Turn right (navigation cue) |
|`Straight`     |Go straight (navigation cue)|
|`First Aid`    |Medical / aid station       |
|`4th Category` |Cycling climb category      |
|`3rd Category` |Cycling climb category      |
|`2nd Category` |Cycling climb category      |
|`1st Category` |Cycling climb category      |
|`Hors Category`|HC climb (hardest category) |
|`Sprint`       |Sprint segment              |

The three turn types (`Left`, `Right`, `Straight`) are used for turn-by-turn navigation cues. The rest are informational POIs displayed along the course.

-----

## Full TCX Course File Structure

```
TrainingCenterDatabase
  └── Courses
        └── Course
              ├── Name              (max 15 characters)
              ├── Lap               (summary stats)
              ├── Track
              │     └── Trackpoint[]   ← GPS track points
              └── CoursePoint[]        ← POIs / cues
```

-----

## Garmin Connect Caveat

When you download a course from Garmin Connect to a GPX file, the Course Points are stripped out. If you need course points to survive transfer between devices, use TCX or transfer via FIT file directly to the device’s `NewFiles` folder over USB.

-----

## Schema Locations

|Schema                    |URL                                                              |
|--------------------------|-----------------------------------------------------------------|
|GPX 1.1 base              |`http://www.topografix.com/GPX/1/1/gpx.xsd`                      |
|Garmin GPX Extensions v3  |`https://www8.garmin.com/xmlschemas/GpxExtensionsv3.xsd`         |
|TrackPoint Extension v1   |`https://www8.garmin.com/xmlschemas/TrackPointExtensionv1.xsd`   |
|**TCX v2 (course points)**|`https://www8.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd`|

-----

## Summary for Bikepacking / Edge 840

- Use **GPX track** for just following a route line on the device
- Use **TCX** if you want typed POIs (water, food, summit, etc.) to appear as course points
- Create courses in **Garmin Connect web** and sync natively for best course point support
- Alternatively, hand-craft a TCX file and drop it in the device’s `NewFiles` folder via USB