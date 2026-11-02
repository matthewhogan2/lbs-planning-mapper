"""
REST API views the Controller layer in MVC.

Spatial queries:
  1. nearest   - K nearest applications to a point 
  2. within    - applications within X km of a point (ST_DWithin)
  3. locate    - which county contains a point (ST_Contains)
  4. nearby    - applications within X m of a route, plus the buffer (ST_DWithin, ST_Buffer)
  5. inside    - applications inside a drawn area (ST_Within)

Distances are measured with ::geography so they are in real metres on the earths surface. Each distance query first runs a cheap degree-based ST_DWithin
on the geometry column; that part can use the GiST index and cuts the rows down before the exact metre calculation.
"""
import json

from django.contrib.gis.geos import Point
from django.db.models.expressions import RawSQL
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from .models import AreaOfInterest, County, PlanningApplication, Route
from .serializers import (
    AreaOfInterestSerializer,
    CountyNameSerializer,
    CountySerializer,
    PlanningApplicationSerializer,
    RouteSerializer,
)

# Metres per degree of longitude at Ireland's latitude is ~65 km, of latitude ~111 km.
# Dividing by 60 km over-covers slightly, so the index pre-filter never drops a real match.
METRES_PER_DEGREE_SAFE = 60_000


#Helper functions for querys

def get_float(params, name, lo, hi, default=None):
    raw = params.get(name, default)

    if raw is None:
        raise ValidationError({name: "This query parameter is required."})
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError({name: "Must be a number."})
    if not lo <= value <= hi:
        raise ValidationError({name: f"Must be between {lo} and {hi}."})
    return value


def get_point(params):
    lat = get_float(params, "lat", 51.2, 55.6)
    lng = get_float(params, "lng", -11.0, -5.3)
    return Point(lng, lat, srid=4326)


def distance_to(geom):
    """SQL expression: distance in metres from each application to geom."""
    return RawSQL(
        "ST_Distance(location::geography, ST_GeomFromEWKT(%s)::geography)",
        (geom.ewkt,),
    )


def within_metres(queryset, geom, metres):
    """Index-assisted pre-filter, then an exact metre filter."""
    return (
        queryset.filter(location__dwithin=(geom, metres / METRES_PER_DEGREE_SAFE))
        .annotate(distance_m=distance_to(geom))
        .filter(distance_m__lte=metres)
        .order_by("distance_m")
    )


#permissions
class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


#view sets

class PlanningApplicationViewSet(viewsets.ModelViewSet):
    """CRUD on applications. Reading is public; writing needs a login."""
    serializer_class = PlanningApplicationSerializer

    def get_queryset(self):
        qs = PlanningApplication.objects.all()
        status = self.request.query_params.get("status")
        if status:
            valid = PlanningApplication.Status.values
            if status.upper() not in valid:
                raise ValidationError({"status": f"Must be one of {valid}."})
            qs = qs.filter(status=status.upper())
        return qs

    @action(detail=False)
    def nearest(self, request):
        """GET /api/applications/nearest/?lat=53.8&lng=-9.5&n=10"""
        point = get_point(request.query_params)
        n = int(get_float(request.query_params, "n", 1, 100, default=10))
        qs = (
            self.get_queryset()
            # <-> is PostGIS's KNN operator; the GiST index finds the closest rows directly
            .annotate(knn=RawSQL("location <-> ST_GeomFromEWKT(%s)", (point.ewkt,)))
            .order_by("knn")[:n]
        )
        qs = PlanningApplication.objects.filter(pk__in=[a.pk for a in qs]).annotate(
            distance_m=distance_to(point)
        ).order_by("distance_m")
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False)
    def within(self, request):
        """GET /api/applications/within/?lat=53.8&lng=-9.5&km=2"""
        point = get_point(request.query_params)
        km = get_float(request.query_params, "km", 0.1, 50, default=2)
        qs = within_metres(self.get_queryset(), point, km * 1000)
        return Response(self.get_serializer(qs, many=True).data)


class CountyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = County.objects.all()
    serializer_class = CountySerializer

    @action(detail=False)
    def locate(self, request):
        """GET /api/counties/locate/?lat=53.8&lng=-9.5 -> the county containing that point"""
        point = get_point(request.query_params)
        county = County.objects.filter(boundary__contains=point).first()
        if county is None:
            raise NotFound("That point isn't inside any loaded county.")
        return Response(CountyNameSerializer(county).data)


class RouteViewSet(viewsets.ModelViewSet):
    """A user's own proposed routes (LINESTRING)."""
    serializer_class = RouteSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Route.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

   #query 4 nearby
    @action(detail=True)
    def nearby(self, request, pk=None):
        
        route = self.get_object()
        metres = get_float(request.query_params, "m", 10, 10_000, default=500)
        apps = within_metres(PlanningApplication.objects.all(), route.path, metres)

        buffer_geojson = (
            Route.objects.filter(pk=route.pk)
            .annotate(buf=RawSQL(
                "ST_AsGeoJSON(ST_Buffer(path::geography, %s)::geometry)", (metres,)
            ))
            .values_list("buf", flat=True)
            .first()
        )
        return Response({
            "buffer": json.loads(buffer_geojson),
            "applications": PlanningApplicationSerializer(apps, many=True).data,
        })

#query 5 inside
class AreaOfInterestViewSet(viewsets.ModelViewSet):
    """A users own watched areas POLYGON)"""
    serializer_class = AreaOfInterestSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return AreaOfInterest.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True)
    def applications(self, request, pk=None):
        """GET /api/areas/3/applications/ -> applications inside the polygon"""
        area = self.get_object()
        apps = PlanningApplication.objects.filter(location__within=area.area)
        return Response(PlanningApplicationSerializer(apps, many=True).data)
