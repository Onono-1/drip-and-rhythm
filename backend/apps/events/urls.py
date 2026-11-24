from django.urls import path

from .views import EventSettingsView, PublicEventView

urlpatterns = [
    path("public/", PublicEventView.as_view(), name="event-public"),
    path("settings/", EventSettingsView.as_view(), name="event-settings"),
]
