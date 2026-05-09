from django.urls import path

from .views import OutboxEventDetailView, OutboxEventListView

app_name = "outbox"

urlpatterns = [
    path("", OutboxEventListView.as_view(), name="list"),
    path("<uuid:pk>/", OutboxEventDetailView.as_view(), name="detail"),
]
