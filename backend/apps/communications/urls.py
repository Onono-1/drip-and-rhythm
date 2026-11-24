from django.urls import path

from .views import ResendWebhookView

urlpatterns = [
    path("resend/", ResendWebhookView.as_view(), name="webhook-resend"),
]
