"""
Load Irish county boundaries (POLYGON data) from the Tailte Éireann GeoJSON.

Usage:
    python manage.py load_counties data/counties.geojson

The source stores each island as its own feature, so features are grouped by
county name and merged (ST_Union) into one MultiPolygon per county. Boundaries
are simplified (~50 m) so the map stays fast.
"""
import json
from collections import defaultdict

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from planning.models import County

# The name column has changed between releases, so try each.
NAME_FIELDS = ["ENG_NAME_VALUE", "COUNTY", "ENGLISH", "COUNTYNAME", "NAME_TAG", "NAME"]
SIMPLIFY_TOLERANCE = 0.0005  # degrees, roughly 50 m


def polygons_in(geom):
    """Pull the polygons out of any geometry (make_valid can return a collection)."""
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type in ("MultiPolygon", "GeometryCollection"):
        return [p for g in geom for p in polygons_in(g)]
    return []  # stray lines or points left over from a repair


def merge_parts(geoms):
    """Repair each polygon, merge them into one valid MultiPolygon, simplify."""
    polys = []
    for g in geoms:
        if not g.valid:
            g = g.make_valid()  # ST_MakeValid: fixes self-touching edges
        polys.extend(polygons_in(g))
    merged = MultiPolygon(polys, srid=4326).unary_union  # dissolve overlaps
    merged = merged.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
    if not merged.valid:
        merged = merged.make_valid()
    polys = polygons_in(merged)
    return MultiPolygon(polys, srid=4326)


class Command(BaseCommand):
    help = "Load county boundaries from a GeoJSON file"

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the counties GeoJSON file")

    def handle(self, *args, **options):
        try:
            with open(options["path"], encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read {options['path']}: {exc}")

        if "error" in data:
            raise CommandError(f"The download is an ArcGIS error, not data: {data['error']}")
        if data.get("properties", {}).get("exceededTransferLimit"):
            self.stdout.write(self.style.WARNING(
                "Warning: the download was cut short by the server; some areas may be missing."
            ))

        features = data.get("features", [])
        if not features:
            raise CommandError("No features in the file.")
        props = features[0].get("properties") or {}
        name_field = next((f for f in NAME_FIELDS if f in props), None)
        if name_field is None:
            raise CommandError(f"No county name field found. Fields are: {list(props)}")

        # Group every polygon (mainland + islands) under its county name
        parts = defaultdict(list)
        for feature in features:
            name = str((feature.get("properties") or {}).get(name_field, "")).strip().title()
            if feature.get("geometry") and name:
                parts[name].append(GEOSGeometry(json.dumps(feature["geometry"]), srid=4326))

        with transaction.atomic():
            for name, geoms in parts.items():
                merged = merge_parts(geoms)
                County.objects.update_or_create(name=name, defaults={"boundary": merged})

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(parts)} counties from {len(features)} polygons"
        ))
