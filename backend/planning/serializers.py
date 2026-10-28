from datetime import date

from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import AreaOfInterest, County, PlanningApplication, Route

# Rough bounding box of the island of Ireland (lng/lat)
IRELAND_BBOX = (-11.0, 51.2, -5.3, 55.6)


def check_in_ireland(geom):
    """Reject geometry that isn't in Ireland (catches swapped lat/lng)."""
    min_x, min_y, max_x, max_y = geom.extent
    if (min_x < IRELAND_BBOX[0] or min_y < IRELAND_BBOX[1]
            or max_x > IRELAND_BBOX[2] or max_y > IRELAND_BBOX[3]):
        raise serializers.ValidationError("Geometry must be inside Ireland.")
    return geom


class PlanningApplicationSerializer(GeoFeatureModelSerializer):
    # Filled in by the distance queries only; null on plain list/detail calls
    distance_m = serializers.SerializerMethodField()

    class Meta:
        model = PlanningApplication
        geo_field = "location"
        fields = [
            "id", "reference", "description", "address", "app_type", "status",
            "received_date", "decision_date", "distance_m",
        ]

    def get_distance_m(self, obj):
        distance = getattr(obj, "distance_m", None)
        return round(distance) if distance is not None else None

    def validate_location(self, value):
        return check_in_ireland(value)

    def validate_received_date(self, value):
        if value > date.today():
            raise serializers.ValidationError("Received date can't be in the future.")
        return value

    def validate(self, attrs):
        received = attrs.get("received_date", getattr(self.instance, "received_date", None))
        decided = attrs.get("decision_date")
        if received and decided and decided < received:
            raise serializers.ValidationError(
                {"decision_date": "Decision date can't be before the received date."}
            )
        return attrs


class CountySerializer(GeoFeatureModelSerializer):
    class Meta:
        model = County
        geo_field = "boundary"
        fields = ["id", "name"]


class CountyNameSerializer(serializers.ModelSerializer):
    """Name only, for the 'which county is this in' query."""
    class Meta:
        model = County
        fields = ["id", "name"]


class RouteSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Route
        geo_field = "path"
        fields = ["id", "name", "created_at"]

    def validate_path(self, value):
        if value.num_points < 2:
            raise serializers.ValidationError("A route needs at least 2 points.")
        return check_in_ireland(value)


class AreaOfInterestSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = AreaOfInterest
        geo_field = "area"
        fields = ["id", "name", "created_at"]

    def validate_area(self, value):
        if not value.valid:
            raise serializers.ValidationError(f"Invalid polygon: {value.valid_reason}")
        return check_in_ireland(value)
