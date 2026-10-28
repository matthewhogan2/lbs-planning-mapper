"""
Load Irish county boundaries (POLYGON data) from the Tailte Éireann GeoJSON.

Usage:
    python manage.py load_counties data/counties.geojson

The boundaries are simplified (~50 m tolerance) so the map stays fast;
statutory-level detail isn't needed for "which county is this point in".
"""
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import MultiPolygon
from django.core.management.base import BaseCommand, CommandError

from planning.models import County

# The source file's name column has changed between releases, so try each.
NAME_FIELDS = ["ENG_NAME_VALUE", "COUNTY", "ENGLISH", "COUNTYNAME", "NAME_TAG", "NAME"]
SIMPLIFY_TOLERANCE = 0.0005  # degrees, roughly 50 m


class Command(BaseCommand):
    help = "Load county boundaries from a GeoJSON file"

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the counties GeoJSON file")

    def handle(self, *args, **options):
        try:
            layer = DataSource(options["path"])[0]
        except Exception as exc:
            raise CommandError(f"Could not open {options['path']}: {exc}")

        name_field = next((f for f in NAME_FIELDS if f in layer.fields), None)
        if name_field is None:
            raise CommandError(f"No county name field found. Fields are: {layer.fields}")

        loaded = 0
        for feature in layer:
            name = str(feature.get(name_field)).strip().title()

            geom = feature.geom
            if geom.srid != 4326:
                geom.transform(4326)  # e.g. Irish Transverse Mercator -> WGS84
            geos = geom.geos.simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)
            if geos.geom_type == "Polygon":
                geos = MultiPolygon(geos, srid=4326)

            # update_or_create makes the command safe to run more than once
            County.objects.update_or_create(name=name, defaults={"boundary": geos})
            loaded += 1

        self.stdout.write(self.style.SUCCESS(f"Loaded {loaded} counties"))
