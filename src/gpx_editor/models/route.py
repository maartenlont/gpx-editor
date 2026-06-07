from dataclasses import dataclass, field

import polars as pl

# Canonical column schemas — used by readers and tests to ensure consistency.
TRACK_POINTS_SCHEMA: dict[str, type] = {
    "index": pl.Int64,
    "lat": pl.Float64,
    "lon": pl.Float64,
    "elevation": pl.Float64,
    "time": pl.Datetime("us", "UTC"),
    "distance": pl.Float64,
    "hr": pl.Int32,
    "cadence": pl.Int32,
    "power": pl.Int32,
}

CUES_SCHEMA: dict[str, type] = {
    "index": pl.Int64,
    "lat": pl.Float64,
    "lon": pl.Float64,
    "name": pl.String,
    "description": pl.String,
    "cue_type": pl.String,
    "distance": pl.Float64,
}

POIS_SCHEMA: dict[str, type] = {
    "index": pl.Int64,
    "lat": pl.Float64,
    "lon": pl.Float64,
    "name": pl.String,
    "description": pl.String,
    "symbol": pl.String,
    "distance": pl.Float64,
}


def empty_track_points() -> pl.DataFrame:
    return pl.DataFrame(schema=TRACK_POINTS_SCHEMA)


def empty_cues() -> pl.DataFrame:
    return pl.DataFrame(schema=CUES_SCHEMA)


def empty_pois() -> pl.DataFrame:
    return pl.DataFrame(schema=POIS_SCHEMA)


@dataclass
class RouteData:
    track_points: pl.DataFrame = field(default_factory=empty_track_points)
    cues: pl.DataFrame = field(default_factory=empty_cues)
    pois: pl.DataFrame = field(default_factory=empty_pois)
    source_file: str = ""

    def deduplicate(self, distance_precision: int = 0) -> "RouteData":
        """Remove duplicate cues and POIs with the same distance and name.
        
        Args:
            distance_precision: Number of decimal places to round distance for comparison.
                               Default 0 means round to nearest meter.
        
        Returns:
            A new RouteData with duplicates removed.
        """
        def dedup_df(df: pl.DataFrame) -> pl.DataFrame:
            if len(df) == 0:
                return df
            # Round distance for comparison and deduplicate on (distance, name)
            # Use maintain_order=True to preserve original order
            deduped = (
                df.with_columns(pl.col("distance").round(distance_precision).alias("_dist_key"))
                .unique(subset=["_dist_key", "name"], keep="first", maintain_order=True)
                .drop("_dist_key", "index")
                .with_row_index("index")
                .cast({"index": pl.Int64})
            )
            return deduped
        
        return RouteData(
            track_points=self.track_points,
            cues=dedup_df(self.cues),
            pois=dedup_df(self.pois),
            source_file=self.source_file,
        )

    def fix_symbols(self) -> "RouteData":
        """Fix POI symbols by deriving them from names when symbol is empty.
        
        Maps name keywords to appropriate symbols:
        - "food", "cafe", "restaurant", etc. → "food"
        - "water", "drink", "tap", etc. → "water"
        - "summit", "peak" → "summit"
        - etc.
        
        Returns:
            A new RouteData with fixed symbols.
        """
        if len(self.pois) == 0:
            return self
        
        # Keyword to symbol mapping (lowercase)
        keyword_to_symbol: list[tuple[str, str]] = [
            ("water", "water"),
            ("drink", "water"),
            ("tap", "water"),
            ("spring", "water"),
            ("fountain", "water"),
            ("food", "food"),
            ("eat", "food"),
            ("cafe", "food"),
            ("coffee", "food"),
            ("restaurant", "food"),
            ("bar", "food"),
            ("pub", "food"),
            ("shop", "food"),
            ("market", "food"),
            ("bakery", "food"),
            ("snack", "food"),
            ("aid", "first aid"),
            ("hospital", "first aid"),
            ("pharmac", "first aid"),
            ("medical", "first aid"),
            ("doctor", "first aid"),
            ("clinic", "first aid"),
            ("summit", "summit"),
            ("peak", "summit"),
            ("valley", "valley"),
            ("danger", "danger"),
            ("hazard", "danger"),
            ("sprint", "sprint"),
            ("checkpoint", "checkpoint"),
        ]
        
        def derive_symbol(name: str, current_symbol: str) -> str:
            # Only fix if symbol is empty
            if current_symbol:
                return current_symbol
            name_lower = (name or "").lower()
            for keyword, symbol in keyword_to_symbol:
                if keyword in name_lower:
                    return symbol
            return current_symbol
        
        # Apply fix to each row
        fixed_pois = self.pois.with_columns(
            pl.struct(["name", "symbol"])
            .map_elements(
                lambda row: derive_symbol(row["name"], row["symbol"]),
                return_dtype=pl.String,
            )
            .alias("symbol")
        )
        
        return RouteData(
            track_points=self.track_points,
            cues=self.cues,
            pois=fixed_pois,
            source_file=self.source_file,
        )
