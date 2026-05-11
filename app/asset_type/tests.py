from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from asset_type.models import AssetType
from tenant.models import Tenant

ASSET_TYPE_LIST_URL = reverse("asset_type:list-create")


def asset_type_detail_url(asset_type_id):
    return reverse("asset_type:detail", args=[asset_type_id])


def create_tenant(name="Test Tenant"):
    return Tenant.objects.create(name=name)


def create_user(tenant, **kwargs):
    defaults = {"email": "user@example.com", "password": "testpass123"}
    defaults.update(kwargs)
    return get_user_model().objects.create_user(tenant=tenant, **defaults)


def create_asset_type(tenant, **kwargs):
    defaults = {"name": "Pump"}
    defaults.update(kwargs)
    return AssetType.objects.create(tenant=tenant, **defaults)


class AssetTypeListCreateTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant, is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_asset_types_success(self):
        create_asset_type(self.tenant, name="Pump")
        create_asset_type(self.tenant, name="Motor")

        res = self.client.get(
            ASSET_TYPE_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_list_only_returns_own_tenant_types(self):
        other_tenant = create_tenant(name="Other Tenant")
        create_asset_type(self.tenant, name="Pump")
        create_asset_type(other_tenant, name="Motor")

        res = self.client.get(
            ASSET_TYPE_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_list_without_tenant_header_fails(self):
        res = self.client.get(ASSET_TYPE_LIST_URL)

        self.assertEqual(res.status_code, 403)

    def test_list_unauthenticated_fails(self):
        self.client.force_authenticate(user=None)

        res = self.client.get(
            ASSET_TYPE_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 401)

    def test_create_asset_type_success(self):
        payload = {"name": "Pump", "description": "Water pump"}

        res = self.client.post(
            ASSET_TYPE_LIST_URL,
            payload,
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 201)
        self.assertTrue(
            AssetType.objects.filter(tenant=self.tenant, name="Pump").exists()
        )

    def test_create_asset_type_without_tenant_header_fails(self):
        res = self.client.post(ASSET_TYPE_LIST_URL, {"name": "Pump"})

        self.assertEqual(res.status_code, 403)

    def test_non_staff_user_is_forbidden(self):
        non_staff = create_user(self.tenant, email="nonstaff@example.com")
        self.client.force_authenticate(non_staff)

        res = self.client.get(
            ASSET_TYPE_LIST_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        self.assertEqual(res.status_code, 403)


class AssetTypeDetailTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(self.tenant, is_staff=True)
        self.asset_type = create_asset_type(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_asset_type_success(self):
        res = self.client.get(
            asset_type_detail_url(self.asset_type.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["name"], self.asset_type.name)

    def test_retrieve_other_tenant_asset_type_fails(self):
        other_tenant = create_tenant(name="Other Tenant")
        other_asset_type = create_asset_type(other_tenant, name="Motor")

        res = self.client.get(
            asset_type_detail_url(other_asset_type.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 404)

    def test_update_asset_type_success(self):
        res = self.client.patch(
            asset_type_detail_url(self.asset_type.id),
            {"name": "Updated Pump"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 200)
        self.asset_type.refresh_from_db()
        self.assertEqual(self.asset_type.name, "Updated Pump")

    def test_delete_asset_type_success(self):
        res = self.client.delete(
            asset_type_detail_url(self.asset_type.id),
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(res.status_code, 204)
        self.assertFalse(
            AssetType.objects.filter(id=self.asset_type.id).exists()
        )

    def test_delete_asset_type_without_tenant_header_fails(self):
        res = self.client.delete(asset_type_detail_url(self.asset_type.id))

        self.assertEqual(res.status_code, 403)
