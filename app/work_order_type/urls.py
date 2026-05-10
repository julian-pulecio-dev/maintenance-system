from django.urls import path

from .views import WorkOrderTypeDetailView, WorkOrderTypeListCreateView

app_name = "work_order_type"

urlpatterns = [
    path("", WorkOrderTypeListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", WorkOrderTypeDetailView.as_view(), name="detail"),
]
