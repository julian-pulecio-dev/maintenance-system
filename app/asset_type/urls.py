from django.urls import path

from .views import AssetTypeDetailView, AssetTypeListCreateView

app_name = "asset_type"

urlpatterns = [
    path("", AssetTypeListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", AssetTypeDetailView.as_view(), name="detail"),
]
