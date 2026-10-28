from rest_framework.routers import DefaultRouter

from .views import (
    AreaOfInterestViewSet,
    CountyViewSet,
    PlanningApplicationViewSet,
    RouteViewSet,
)

router = DefaultRouter()
router.register("applications", PlanningApplicationViewSet, basename="application")
router.register("counties", CountyViewSet, basename="county")
router.register("routes", RouteViewSet, basename="route")
router.register("areas", AreaOfInterestViewSet, basename="area")

urlpatterns = router.urls
