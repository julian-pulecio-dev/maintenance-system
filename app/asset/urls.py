from django.urls import path

from .views import AssetDetailView, AssetListCreateView, AssetRestoreView, AssetSupervisorView

app_name = "asset"

urlpatterns = [
    path("", AssetListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", AssetDetailView.as_view(), name="detail"),
    path("<uuid:pk>/restore/", AssetRestoreView.as_view(), name="restore"),
    path("<uuid:pk>/supervisor/", AssetSupervisorView.as_view(), name="supervisor"),
]
