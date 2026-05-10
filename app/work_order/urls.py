from django.urls import path

from .views import (
    WorkOrderAssignView,
    WorkOrderCancelView,
    WorkOrderCompleteView,
    WorkOrderDetailView,
    WorkOrderHoldView,
    WorkOrderListCreateView,
    WorkOrderRestoreView,
    WorkOrderStartView,
)

app_name = "work_order"

urlpatterns = [
    path("", WorkOrderListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>/", WorkOrderDetailView.as_view(), name="detail"),
    path("<uuid:pk>/restore/", WorkOrderRestoreView.as_view(), name="restore"),
    path("<uuid:pk>/start/", WorkOrderStartView.as_view(), name="start"),
    path("<uuid:pk>/hold/", WorkOrderHoldView.as_view(), name="hold"),
    path("<uuid:pk>/complete/", WorkOrderCompleteView.as_view(), name="complete"),
    path("<uuid:pk>/cancel/", WorkOrderCancelView.as_view(), name="cancel"),
    path("<uuid:pk>/assign/", WorkOrderAssignView.as_view(), name="assign"),
]
