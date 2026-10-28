from django.conf import settings
from django.contrib.gis.db import models

# SRID 4326 = WGS84 lat/lng, which is what Leaflet uses.
# GeoDjango creates a GiST spatial index on every geometry field by default
# (spatial_index=True), which covers the "properly indexed" requirement.


class County(models.Model):
    """Irish county / local authority boundary. POLYGON data, imported once."""
    name = models.CharField(max_length=100, unique=True)
    boundary = models.MultiPolygonField(srid=4326)

    class Meta:
        verbose_name_plural = "counties"
        ordering = ["name"]

    def __str__(self):
        return self.name


class PlanningApplication(models.Model):
    """A planning application site. POINT data."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending decision"
        GRANTED = "GRANTED", "Granted"
        REFUSED = "REFUSED", "Refused"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"

    class AppType(models.TextChoices):
        RESIDENTIAL = "RESIDENTIAL", "Residential"
        COMMERCIAL = "COMMERCIAL", "Commercial"
        AGRICULTURAL = "AGRICULTURAL", "Agricultural"
        OTHER = "OTHER", "Other"

    reference = models.CharField(max_length=30, unique=True)
    description = models.TextField()
    address = models.CharField(max_length=255, blank=True)
    app_type = models.CharField(max_length=20, choices=AppType.choices, default=AppType.RESIDENTIAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    received_date = models.DateField()
    decision_date = models.DateField(null=True, blank=True)
    location = models.PointField(srid=4326)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_date"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return self.reference


class Route(models.Model):
    """A proposed route (greenway, road) drawn by a user. LINESTRING data."""
    name = models.CharField(max_length=100)
    path = models.LineStringField(srid=4326)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="routes")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class AreaOfInterest(models.Model):
    """A user-drawn area to watch for applications. POLYGON data."""
    name = models.CharField(max_length=100)
    area = models.PolygonField(srid=4326)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="areas")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
