from django.contrib.gis import admin

from .models import AreaOfInterest, County, PlanningApplication, Route


@admin.register(PlanningApplication)
class PlanningApplicationAdmin(admin.GISModelAdmin):
    list_display = ("reference", "app_type", "status", "received_date")
    list_filter = ("status", "app_type")
    search_fields = ("reference", "description")


@admin.register(County)
class CountyAdmin(admin.GISModelAdmin):
    list_display = ("name",)


admin.site.register(Route, admin.GISModelAdmin)
admin.site.register(AreaOfInterest, admin.GISModelAdmin)
