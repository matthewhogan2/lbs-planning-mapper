"""
Load planning applications (POINT data) from a National Planning
Application Database GeoJSON extract (queried with outSR=4326).

Usage:
    python manage.py load_applications data/mayo_applications.geojson
"""
import json
from datetime import datetime, timezone

from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from planning.models import PlanningApplication

Status = PlanningApplication.Status
AppType = PlanningApplication.AppType

# Keyword rules for turning free-text descriptions into a category.
# Checked in order; first match wins.
TYPE_KEYWORDS = [
    (AppType.RESIDENTIAL, ["DWELLING", "HOUSE", "APARTMENT", "RESIDENTIAL", "EXTENSION"]),
    (AppType.COMMERCIAL, ["SHOP", "RETAIL", "OFFICE", "HOTEL", "RESTAURANT", "COMMERCIAL", "SIGNAGE"]),
    (AppType.AGRICULTURAL, ["AGRICULTUR", "FARM", "SLATTED", "CATTLE", "SLURRY", "HAY"]),
]


def ms_to_date(value):
    """ArcGIS stores dates as milliseconds since 1970."""
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()


def map_status(decision, app_status):
    decision = (decision or "").upper()
    app_status = (app_status or "").upper()
    if "REFUS" in decision:
        return Status.REFUSED
    if "WITHDRAW" in decision or "WITHDRAW" in app_status or "INVALID" in decision:
        return Status.WITHDRAWN
    if "GRANT" in decision or "CONDITIONAL" in decision:
        return Status.GRANTED
    return Status.PENDING


def map_type(description):
    text = (description or "").upper()
    for app_type, words in TYPE_KEYWORDS:
        if any(word in text for word in words):
            return app_type
    return AppType.OTHER


class Command(BaseCommand):
    help = "Load planning applications from a GeoJSON file"

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to the applications GeoJSON file")

    def handle(self, *args, **options):
        try:
            with open(options["path"], encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Could not read {options['path']}: {exc}")

        if "error" in data:
            raise CommandError(f"The download is an ArcGIS error, not data: {data['error']}")

        loaded = skipped = 0
        with transaction.atomic():  # all-or-nothing import
            for feature in data.get("features", []):
                props = feature.get("properties") or {}
                geometry = feature.get("geometry")
                reference = (props.get("ApplicationNumber") or "").strip()
                received = ms_to_date(props.get("ReceivedDate"))

                # Skip rows we can't map or identify
                if not geometry or not reference or not received:
                    skipped += 1
                    continue

                PlanningApplication.objects.update_or_create(
                    reference=reference,
                    defaults={
                        "description": (props.get("DevelopmentDescription") or "").strip().capitalize(),
                        "address": (props.get("DevelopmentAddress") or "").strip().title()[:255],
                        "status": map_status(props.get("Decision"), props.get("ApplicationStatus")),
                        "app_type": map_type(props.get("DevelopmentDescription")),
                        "received_date": received,
                        "decision_date": ms_to_date(props.get("DecisionDate")),
                        "location": GEOSGeometry(json.dumps(geometry), srid=4326),
                    },
                )
                loaded += 1

        self.stdout.write(self.style.SUCCESS(f"Loaded {loaded} applications ({skipped} skipped)"))
