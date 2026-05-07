from django.urls import path
from .views import TenantDetailView, TenantListCreateView

app_name = "tenant"

urlpatterns = [
    path("", TenantListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", TenantDetailView.as_view(), name="detail"),
]
