from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("planning.urls")),
    path("api-auth/", include("rest_framework.urls")),  # login/logout for the browsable API
]
