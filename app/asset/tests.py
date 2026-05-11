import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from asset.models import Asset
from asset_type.models import AssetType
from tenant.models import Tenant

ASSET_LIST_URL = reverse("asset:list-create")


def asset_detail_url(asset_id):
    return reverse("asset:detail", args=[asset_id])


def asset_restore_url(asset_id):
    return reverse("asset:restore", args=[asset_id])


def asset_sensor_alert_url(asset_id):
    return reverse("asset:sensor-alert", args=[asset_id])


def create_tenant(name="Test Tenant"):
    return Tenant.objects.create(name=name)


def create_user(tenant, **kwargs):
    defaults = {"email": "user@example.com", "password": "testpass123"}
    defaults.update(kwargs)
    return get_user_model().objects.create_user(tenant=tenant, **defaults)


def create_asset_type(tenant, name="Pump"):
    return AssetType.objects.create(tenant=tenant, name=name)


def create_asset(tenant, asset_type, **kwargs):
    if "supervisor" not in kwargs:
        kwargs["supervisor"] = get_user_model().objects.create_user(
            tenant=tenant,
            email=f"supervisor-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
    defaults = {
        "name": "Main Pump",
        "serial_number": uuid.uuid4().hex[:12],
        "location": "Building A",
        "installation_date": date(2020, 1, 1),
        "recommended_maintenance_interval_days": 30,
        "metadata": {"spec_version": 1},
    }
    defaults.update(kwargs)
    return Asset.objects.create(
        tenant=tenant, asset_type=asset_type, **defaults
    )


class AssetListCreateTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant, is_staff=True)
        self.asset_type = create_asset_type(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_assets_success(self):
        create_asset(self.tenant, self.asset_type, name="Pump A")
        create_asset(self.tenant, self.asset_type, name="Pump B")

        res = self.client.get(
            ASSET_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_list_only_returns_own_tenant_assets(self):
        other_tenant = create_tenant(name="Other Tenant")
        other_asset_type = create_asset_type(other_tenant, name="Motor")
        create_asset(self.tenant, self.asset_type, name="Pump A")
        create_asset(other_tenant, other_asset_type, name="Motor B")

        res = self.client.get(
            ASSET_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_list_excludes_soft_deleted_assets(self):
        asset = create_asset(self.tenant, self.asset_type)
        asset.soft_delete()

        res = self.client.get(
            ASSET_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 0)

    def test_list_without_tenant_header_fails(self):
        res = self.client.get(ASSET_LIST_URL)

        self.assertEqual(res.status_code, 403)

    def test_list_unauthenticated_fails(self):
        self.client.force_authenticate(user=None)

        res = self.client.get(
            ASSET_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 401)

    def test_create_asset_success(self):
        payload = {
            "name": "New Pump",
            "serial_number": "SN-001",
            "asset_type": str(self.asset_type.id),
            "supervisor": str(self.user.id),
            "location": "Building B",
            "installation_date": "2021-06-01",
            "recommended_maintenance_interval_days": 60,
            "metadata": {"spec_version": 1},
        }

        res = self.client.post(
            ASSET_LIST_URL,
            payload,
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 201)
        self.assertTrue(
            Asset.objects.filter(tenant=self.tenant, name="New Pump").exists()
        )

    def test_create_asset_with_other_tenant_type_fails(self):
        other_tenant = create_tenant(name="Other Tenant")
        other_asset_type = create_asset_type(other_tenant, name="Motor")
        payload = {
            "name": "New Pump",
            "asset_type": str(other_asset_type.id),
            "supervisor": str(self.user.id),
            "location": "Building B",
            "installation_date": "2021-06-01",
            "recommended_maintenance_interval_days": 60,
            "metadata": {"spec_version": 1},
        }

        res = self.client.post(
            ASSET_LIST_URL,
            payload,
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 400)

    def test_create_asset_without_tenant_header_fails(self):
        payload = {
            "name": "New Pump",
            "asset_type": str(self.asset_type.id),
            "supervisor": str(self.user.id),
            "location": "Building B",
            "installation_date": "2021-06-01",
            "recommended_maintenance_interval_days": 60,
            "metadata": {"spec_version": 1},
        }

        res = self.client.post(ASSET_LIST_URL, payload, format="json")

        self.assertEqual(res.status_code, 403)

    def test_non_staff_cannot_create_asset(self):
        non_staff = create_user(self.tenant, email="nonstaff@example.com")
        self.client.force_authenticate(non_staff)

        payload = {
            "name": "New Pump",
            "asset_type": str(self.asset_type.id),
            "supervisor": str(non_staff.id),
            "location": "Building B",
            "installation_date": "2021-06-01",
            "recommended_maintenance_interval_days": 60,
            "metadata": {"spec_version": 1},
        }

        res = self.client.post(
            ASSET_LIST_URL,
            payload,
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 403)

    def test_non_staff_can_list_assets(self):
        non_staff = create_user(self.tenant, email="nonstaff@example.com")
        self.client.force_authenticate(non_staff)

        res = self.client.get(
            ASSET_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)


class AssetDetailTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant, is_staff=True)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_asset_success(self):
        res = self.client.get(
            asset_detail_url(self.asset.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["name"], self.asset.name)

    def test_retrieve_other_tenant_asset_fails(self):
        other_tenant = create_tenant(name="Other Tenant")
        other_asset_type = create_asset_type(other_tenant, name="Motor")
        other_asset = create_asset(
            other_tenant, other_asset_type, name="Motor X"
        )

        res = self.client.get(
            asset_detail_url(other_asset.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 404)

    def test_update_asset_success(self):
        res = self.client.patch(
            asset_detail_url(self.asset.id),
            {"name": "Updated Pump"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.name, "Updated Pump")

    def test_delete_asset_soft_deletes(self):
        res = self.client.delete(
            asset_detail_url(self.asset.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 204)
        self.asset.refresh_from_db()
        self.assertTrue(self.asset.is_deleted)

    def test_delete_without_tenant_header_fails(self):
        res = self.client.delete(asset_detail_url(self.asset.id))

        self.assertEqual(res.status_code, 403)


class AssetRestoreTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant, is_staff=True)
        self.asset_type = create_asset_type(self.tenant)
        self.asset = create_asset(self.tenant, self.asset_type)
        self.asset.soft_delete()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_restore_deleted_asset_success(self):
        res = self.client.post(
            asset_restore_url(self.asset.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.asset.refresh_from_db()
        self.assertFalse(self.asset.is_deleted)

    def test_restore_non_deleted_asset_fails(self):
        self.asset.restore()

        res = self.client.post(
            asset_restore_url(self.asset.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 400)

    def test_restore_other_tenant_asset_fails(self):
        other_tenant = create_tenant(name="Other Tenant")
        other_asset_type = create_asset_type(other_tenant, name="Motor")
        other_asset = create_asset(
            other_tenant, other_asset_type, name="Motor X"
        )
        other_asset.soft_delete()

        res = self.client.post(
            asset_restore_url(other_asset.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 404)

    def test_restore_without_tenant_header_fails(self):
        res = self.client.post(asset_restore_url(self.asset.id))

        self.assertEqual(res.status_code, 403)

    def test_non_staff_cannot_restore(self):
        non_staff = create_user(self.tenant, email="nonstaff@example.com")
        self.client.force_authenticate(non_staff)

        res = self.client.post(
            asset_restore_url(self.asset.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 403)


class AssetSupervisorPermissionTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.asset_type = create_asset_type(self.tenant)
        self.supervisor = create_user(
            self.tenant, email="supervisor@example.com"
        )
        self.other_user = create_user(self.tenant, email="other@example.com")
        self.asset = create_asset(
            self.tenant, self.asset_type, supervisor=self.supervisor
        )
        self.client = APIClient()

    def test_supervisor_can_update_their_asset(self):
        self.client.force_authenticate(self.supervisor)

        res = self.client.patch(
            asset_detail_url(self.asset.id),
            {"name": "Updated by supervisor"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.name, "Updated by supervisor")

    def test_non_supervisor_cannot_update_asset(self):
        self.client.force_authenticate(self.other_user)

        res = self.client.patch(
            asset_detail_url(self.asset.id),
            {"name": "Unauthorized update"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 403)

    def test_non_staff_cannot_delete_asset(self):
        self.client.force_authenticate(self.supervisor)

        res = self.client.delete(
            asset_detail_url(self.asset.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 403)

    def test_supervisor_can_send_sensor_alert(self):
        self.client.force_authenticate(self.supervisor)

        res = self.client.post(
            asset_sensor_alert_url(self.asset.id),
            {"severity": "warning", "message": "Pressure high"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 202)

    def test_non_supervisor_cannot_send_sensor_alert(self):
        self.client.force_authenticate(self.other_user)

        res = self.client.post(
            asset_sensor_alert_url(self.asset.id),
            {"severity": "warning", "message": "Pressure high"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 403)
