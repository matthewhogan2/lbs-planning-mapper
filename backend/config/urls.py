from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="planning/map.html"), name="map"),
    path("admin/", admin.site.urls),
    path("api/", include("planning.urls")),
    path("api-auth/", include("rest_framework.urls")),
]
