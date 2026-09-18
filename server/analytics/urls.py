from django.urls import path
from analytics import views
from .ingest_views import ingest_summary_view


app_name = "analytics"
urlpatterns = [
    path("", views.summary_view, name="summary"),
    path("ingest/", ingest_summary_view, name="ingest-summary"),
    ]