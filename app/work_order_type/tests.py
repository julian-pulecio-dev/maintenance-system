import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from asset.models import Asset
from asset_type.models import AssetType
from tenant.models import Tenant
from work_order.models import WorkOrder
from work_order_type.models import WorkOrderType

WORK_ORDER_TYPE_LIST_URL = reverse("work_order_type:list-create")


def work_order_type_detail_url(pk):
    return reverse("work_order_type:detail", args=[pk])


def create_tenant(name="Test Tenant"):
    return Tenant.objects.create(name=name)


def create_user(tenant, **kwargs):
    defaults = {"email": "user@example.com", "password": "testpass123"}
    defaults.update(kwargs)
    return get_user_model().objects.create_user(tenant=tenant, **defaults)


def create_work_order_type(tenant, **kwargs):
    defaults = {"name": "Preventive"}
    defaults.update(kwargs)
    return WorkOrderType.objects.create(tenant=tenant, **defaults)


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
        installation_date="2020-01-01",
        recommended_maintenance_interval_days=30,
    )


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


class WorkOrderTypeListCreateTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_work_order_types_success(self):
        create_work_order_type(self.tenant, name="Preventive")
        create_work_order_type(self.tenant, name="Corrective")

        res = self.client.get(
            WORK_ORDER_TYPE_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_list_only_returns_own_tenant_types(self):
        other_tenant = create_tenant(name="Other Tenant")
        create_work_order_type(self.tenant, name="Preventive")
        create_work_order_type(other_tenant, name="Corrective")

        res = self.client.get(
            WORK_ORDER_TYPE_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_list_without_tenant_header_fails(self):
        res = self.client.get(WORK_ORDER_TYPE_LIST_URL)
        self.assertEqual(res.status_code, 403)

    def test_list_unauthenticated_fails(self):
        self.client.force_authenticate(user=None)
        res = self.client.get(
            WORK_ORDER_TYPE_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(res.status_code, 401)

    def test_create_work_order_type_success(self):
        payload = {"name": "Preventive", "description": "Scheduled maintenance"}

        res = self.client.post(
            WORK_ORDER_TYPE_LIST_URL,
            payload,
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 201)
        self.assertTrue(
            WorkOrderType.objects.filter(
                tenant=self.tenant, name="Preventive"
            ).exists()
        )

    def test_create_duplicate_name_fails(self):
        create_work_order_type(self.tenant, name="Preventive")

        res = self.client.post(
            WORK_ORDER_TYPE_LIST_URL,
            {"name": "Preventive"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 400)

    def test_duplicate_name_allowed_across_tenants(self):
        other_tenant = create_tenant(name="Other Tenant")
        create_work_order_type(other_tenant, name="Preventive")

        res = self.client.post(
            WORK_ORDER_TYPE_LIST_URL,
            {"name": "Preventive"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 201)

    def test_create_without_tenant_header_fails(self):
        res = self.client.post(WORK_ORDER_TYPE_LIST_URL, {"name": "Preventive"})
        self.assertEqual(res.status_code, 403)


class WorkOrderTypeDetailTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant)
        self.work_order_type = create_work_order_type(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_success(self):
        res = self.client.get(
            work_order_type_detail_url(self.work_order_type.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["name"], self.work_order_type.name)

    def test_retrieve_other_tenant_fails(self):
        other_tenant = create_tenant(name="Other Tenant")
        other_type = create_work_order_type(other_tenant, name="Corrective")

        res = self.client.get(
            work_order_type_detail_url(other_type.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 404)

    def test_update_success(self):
        res = self.client.patch(
            work_order_type_detail_url(self.work_order_type.id),
            {"name": "Corrective"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.work_order_type.refresh_from_db()
        self.assertEqual(self.work_order_type.name, "Corrective")

    def test_update_duplicate_name_fails(self):
        create_work_order_type(self.tenant, name="Corrective")

        res = self.client.patch(
            work_order_type_detail_url(self.work_order_type.id),
            {"name": "Corrective"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 400)

    def test_delete_success(self):
        res = self.client.delete(
            work_order_type_detail_url(self.work_order_type.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 204)
        self.assertFalse(
            WorkOrderType.objects.filter(id=self.work_order_type.id).exists()
        )

    def test_delete_with_work_orders_fails(self):
        asset_type = create_asset_type(self.tenant)
        asset = create_asset(self.tenant, asset_type, self.user)
        create_work_order(
            self.tenant, asset, self.work_order_type, self.user
        )

        res = self.client.delete(
            work_order_type_detail_url(self.work_order_type.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 409)

    def test_delete_without_tenant_header_fails(self):
        res = self.client.delete(
            work_order_type_detail_url(self.work_order_type.id)
        )
        self.assertEqual(res.status_code, 403)
