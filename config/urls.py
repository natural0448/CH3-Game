from django.contrib import admin
from django.urls import include, path
from server.analytics import views as analytics_views


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("game.urls")),
    path("api/analytics/",include("analytics.urls")),
    path("api/analytics/actions/", analytics_views.actions_snapshot, name="action-summary"),

]
