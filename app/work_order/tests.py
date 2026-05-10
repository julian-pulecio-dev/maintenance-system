import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from asset.models import Asset
from asset_type.models import AssetType
from tenant.models import Tenant
from work_order.models import WorkOrder
from work_order_type.models import WorkOrderType

WORK_ORDER_LIST_URL = reverse("work_order:list-create")


def work_order_detail_url(pk):
    return reverse("work_order:detail", args=[pk])


def work_order_action_url(pk, action):
    return reverse(f"work_order:{action}", args=[pk])


def create_tenant(name="Test Tenant"):
    return Tenant.objects.create(name=name)


def create_user(tenant, **kwargs):
    defaults = {
        "email": f"user-{uuid.uuid4().hex[:6]}@example.com",
        "password": "testpass123",
    }
    defaults.update(kwargs)
    return get_user_model().objects.create_user(tenant=tenant, **defaults)


def create_asset_type(tenant):
    return AssetType.objects.create(tenant=tenant, name="Pump")


def create_asset(tenant, asset_type, user):
    return Asset.objects.create(
        tenant=tenant,
        asset_type=asset_type,
        supervisor=user,
        name="Main Pump",
        serial_number=uuid.uuid4().hex[:12],
        location="Building A",
        installation_date=date(2020, 1, 1),
        recommended_maintenance_interval_days=30,
    )


def create_work_order_type(tenant, name="Preventive"):
    return WorkOrderType.objects.create(tenant=tenant, name=name)


def create_work_order(tenant, asset, work_order_type, user, **kwargs):
    defaults = {
        "title": "Fix pump",
        "priority": WorkOrder.WorkOrderPriority.MEDIUM,
        "assigned_to": user,
        "created_by": user,
    }
    defaults.update(kwargs)
    return WorkOrder.objects.create(
        tenant=tenant,
        asset=asset,
        work_order_type=work_order_type,
        **defaults,
    )


class WorkOrderListCreateTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type, self.user)
        self.wo_type = create_work_order_type(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_success(self):
        create_work_order(
            self.tenant, self.asset, self.wo_type, self.user, title="WO 1"
        )
        create_work_order(
            self.tenant, self.asset, self.wo_type, self.user, title="WO 2"
        )

        res = self.client.get(
            WORK_ORDER_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_list_only_returns_own_tenant(self):
        other_tenant = create_tenant(name="Other")
        other_user = create_user(other_tenant)
        other_asset_type = create_asset_type(other_tenant)
        other_asset = create_asset(other_tenant, other_asset_type, other_user)
        other_wo_type = create_work_order_type(other_tenant)
        create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        create_work_order(other_tenant, other_asset, other_wo_type, other_user)

        res = self.client.get(
            WORK_ORDER_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_list_excludes_soft_deleted(self):
        wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        wo.soft_delete()

        res = self.client.get(
            WORK_ORDER_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 0)

    def test_list_filter_by_status(self):
        wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        wo.start("Starting work")
        create_work_order(
            self.tenant, self.asset, self.wo_type, self.user, title="WO 2"
        )

        res = self.client.get(
            WORK_ORDER_LIST_URL,
            {"status": "in_progress"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_list_filter_by_priority(self):
        create_work_order(
            self.tenant, self.asset, self.wo_type, self.user,
            priority=WorkOrder.WorkOrderPriority.HIGH,
        )
        create_work_order(
            self.tenant, self.asset, self.wo_type, self.user,
            priority=WorkOrder.WorkOrderPriority.LOW,
        )

        res = self.client.get(
            WORK_ORDER_LIST_URL,
            {"priority": "high"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_list_without_tenant_header_fails(self):
        res = self.client.get(WORK_ORDER_LIST_URL)
        self.assertEqual(res.status_code, 403)

    def test_list_unauthenticated_fails(self):
        self.client.force_authenticate(user=None)
        res = self.client.get(
            WORK_ORDER_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(res.status_code, 401)

    def test_create_success(self):
        payload = {
            "asset": str(self.asset.id),
            "work_order_type": str(self.wo_type.id),
            "assigned_to": str(self.user.id),
            "title": "Inspect pump",
            "priority": "high",
        }

        res = self.client.post(
            WORK_ORDER_LIST_URL,
            payload,
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 201)
        self.assertTrue(
            WorkOrder.objects.filter(
                tenant=self.tenant, title="Inspect pump"
            ).exists()
        )

    def test_create_sets_created_by_from_request_user(self):
        payload = {
            "asset": str(self.asset.id),
            "work_order_type": str(self.wo_type.id),
            "assigned_to": str(self.user.id),
            "title": "Inspect pump",
            "priority": "medium",
        }

        res = self.client.post(
            WORK_ORDER_LIST_URL,
            payload,
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 201)
        wo = WorkOrder.objects.get(id=res.data["id"])
        self.assertEqual(wo.created_by, self.user)

    def test_create_with_other_tenant_asset_fails(self):
        other_tenant = create_tenant(name="Other")
        other_user = create_user(other_tenant)
        other_asset_type = create_asset_type(other_tenant)
        other_asset = create_asset(other_tenant, other_asset_type, other_user)

        payload = {
            "asset": str(other_asset.id),
            "work_order_type": str(self.wo_type.id),
            "assigned_to": str(self.user.id),
            "title": "WO",
            "priority": "medium",
        }

        res = self.client.post(
            WORK_ORDER_LIST_URL,
            payload,
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 400)

    def test_create_without_tenant_header_fails(self):
        res = self.client.post(WORK_ORDER_LIST_URL, {}, format="json")
        self.assertEqual(res.status_code, 403)


class WorkOrderDetailTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type, self.user)
        self.wo_type = create_work_order_type(self.tenant)
        self.wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_success(self):
        res = self.client.get(
            work_order_detail_url(self.wo.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["title"], self.wo.title)

    def test_retrieve_other_tenant_fails(self):
        other_tenant = create_tenant(name="Other")
        other_user = create_user(other_tenant)
        other_asset_type = create_asset_type(other_tenant)
        other_asset = create_asset(other_tenant, other_asset_type, other_user)
        other_wo_type = create_work_order_type(other_tenant)
        other_wo = create_work_order(
            other_tenant, other_asset, other_wo_type, other_user
        )

        res = self.client.get(
            work_order_detail_url(other_wo.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 404)

    def test_update_success(self):
        res = self.client.patch(
            work_order_detail_url(self.wo.id),
            {"title": "Updated title"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.title, "Updated title")

    def test_delete_soft_deletes(self):
        res = self.client.delete(
            work_order_detail_url(self.wo.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 204)
        self.wo.refresh_from_db()
        self.assertTrue(self.wo.is_deleted)


class WorkOrderRestoreTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type, self.user)
        self.wo_type = create_work_order_type(self.tenant)
        self.wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        self.wo.soft_delete()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_restore_success(self):
        res = self.client.post(
            work_order_action_url(self.wo.id, "restore"),
            {"notes": "Restoring after review."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.wo.refresh_from_db()
        self.assertFalse(self.wo.is_deleted)

    def test_restore_not_deleted_fails(self):
        self.wo.restore("Restoring.")
        res = self.client.post(
            work_order_action_url(self.wo.id, "restore"),
            {"notes": "Try restore again."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(res.status_code, 400)

    def test_restore_without_notes_fails(self):
        res = self.client.post(
            work_order_action_url(self.wo.id, "restore"),
            {},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("notes", res.data)


class WorkOrderStartTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type, self.user)
        self.wo_type = create_work_order_type(self.tenant)
        self.wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _url(self):
        return work_order_action_url(self.wo.id, "start")

    def test_start_from_open_success(self):
        res = self.client.post(
            self._url(),
            {"notes": "Starting work now."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.status, WorkOrder.WorkOrderStatus.IN_PROGRESS)

    def test_start_appends_note(self):
        self.client.post(
            self._url(),
            {"notes": "Starting work now."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.wo.refresh_from_db()
        self.assertIn("Starting work now.", self.wo.notes)

    def test_start_from_completed_fails(self):
        self.wo.start("Starting.")
        self.wo.complete("Done.", estimated_hours=2)

        res = self.client.post(
            self._url(),
            {"notes": "Trying to restart."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 409)

    def test_start_without_notes_fails(self):
        res = self.client.post(
            self._url(), {}, HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("notes", res.data)


class WorkOrderHoldTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type, self.user)
        self.wo_type = create_work_order_type(self.tenant)
        self.wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _url(self):
        return work_order_action_url(self.wo.id, "hold")

    def test_hold_from_open_success(self):
        res = self.client.post(
            self._url(),
            {"notes": "Waiting for parts."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.status, WorkOrder.WorkOrderStatus.ON_HOLD)

    def test_hold_from_in_progress_success(self):
        self.wo.start("Starting.")

        res = self.client.post(
            self._url(),
            {"notes": "Putting on hold."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.status, WorkOrder.WorkOrderStatus.ON_HOLD)

    def test_hold_from_cancelled_fails(self):
        self.wo.cancel("Cancelling.")

        res = self.client.post(
            self._url(),
            {"notes": "Trying to hold."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 409)

    def test_hold_without_notes_fails(self):
        res = self.client.post(
            self._url(), {}, HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(res.status_code, 400)


class WorkOrderCompleteTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type, self.user)
        self.wo_type = create_work_order_type(self.tenant)
        self.wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        self.wo.start("Starting.")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _url(self):
        return work_order_action_url(self.wo.id, "complete")

    def test_complete_from_in_progress_success(self):
        res = self.client.post(
            self._url(),
            {"notes": "All done.", "estimated_hours": "3.5"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.status, WorkOrder.WorkOrderStatus.COMPLETED)

    def test_complete_updates_estimated_hours(self):
        self.client.post(
            self._url(),
            {"notes": "Done.", "estimated_hours": "4.0"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.wo.refresh_from_db()
        self.assertEqual(float(self.wo.estimated_hours), 4.0)

    def test_complete_updates_asset_last_maintenance_date(self):
        self.client.post(
            self._url(),
            {"notes": "Done.", "estimated_hours": "2.0"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.asset.refresh_from_db()
        self.wo.refresh_from_db()
        self.assertEqual(self.asset.last_maintenance_date, self.wo.completed_date)

    def test_complete_from_open_fails(self):
        wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)

        res = self.client.post(
            work_order_action_url(wo.id, "complete"),
            {"notes": "Done.", "estimated_hours": "1.0"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 409)

    def test_complete_without_notes_fails(self):
        res = self.client.post(
            self._url(),
            {"estimated_hours": "2.0"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("notes", res.data)

    def test_complete_without_estimated_hours_fails(self):
        res = self.client.post(
            self._url(),
            {"notes": "Done."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("estimated_hours", res.data)


class WorkOrderCancelTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type, self.user)
        self.wo_type = create_work_order_type(self.tenant)
        self.wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _url(self):
        return work_order_action_url(self.wo.id, "cancel")

    def test_cancel_from_open_success(self):
        res = self.client.post(
            self._url(),
            {"notes": "No longer needed."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.status, WorkOrder.WorkOrderStatus.CANCELLED)

    def test_cancel_from_in_progress_success(self):
        self.wo.start("Starting.")
        res = self.client.post(
            self._url(),
            {"notes": "Cancelled mid-work."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)

    def test_cancel_from_completed_fails(self):
        self.wo.start("Starting.")
        self.wo.complete("Done.", estimated_hours=1)

        res = self.client.post(
            self._url(),
            {"notes": "Trying to cancel."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 409)

    def test_cancel_without_notes_fails(self):
        res = self.client.post(
            self._url(), {}, HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("notes", res.data)

    def test_cancel_appends_note(self):
        self.client.post(
            self._url(),
            {"notes": "Reason: budget cut."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.wo.refresh_from_db()
        self.assertIn("Reason: budget cut.", self.wo.notes)


class WorkOrderAssignTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.other_user = create_user(self.tenant)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type, self.user)
        self.wo_type = create_work_order_type(self.tenant)
        self.wo = create_work_order(self.tenant, self.asset, self.wo_type, self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _url(self):
        return work_order_action_url(self.wo.id, "assign")

    def test_assign_success(self):
        res = self.client.post(
            self._url(),
            {"assigned_to": str(self.other_user.id), "notes": "Reassigned."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.wo.refresh_from_db()
        self.assertEqual(self.wo.assigned_to, self.other_user)

    def test_assign_appends_note(self):
        self.client.post(
            self._url(),
            {"assigned_to": str(self.other_user.id), "notes": "Better fit."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.wo.refresh_from_db()
        self.assertIn("Better fit.", self.wo.notes)

    def test_assign_other_tenant_user_fails(self):
        other_tenant = create_tenant(name="Other")
        other_user = create_user(other_tenant)

        res = self.client.post(
            self._url(),
            {"assigned_to": str(other_user.id), "notes": "Assigning."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 400)

    def test_assign_completed_work_order_fails(self):
        self.wo.start("Starting.")
        self.wo.complete("Done.", estimated_hours=1)

        res = self.client.post(
            self._url(),
            {"assigned_to": str(self.other_user.id), "notes": "Assigning."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 409)

    def test_assign_without_notes_fails(self):
        res = self.client.post(
            self._url(),
            {"assigned_to": str(self.other_user.id)},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("notes", res.data)

    def test_assign_without_assigned_to_fails(self):
        res = self.client.post(
            self._url(),
            {"notes": "Missing user."},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("assigned_to", res.data)
