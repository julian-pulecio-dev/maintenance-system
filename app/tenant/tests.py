from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from tenant.models import Tenant

TENANT_LIST_URL = reverse("tenant:list-create")


def tenant_detail_url(tenant_id):
    return reverse("tenant:detail", args=[tenant_id])


def create_tenant(name="Test Tenant"):
    return Tenant.objects.create(name=name)


def create_user(**kwargs):
    defaults = {"email": "user@example.com", "password": "testpass123"}
    defaults.update(kwargs)
    return get_user_model().objects.create_user(**defaults)


def create_admin(**kwargs):
    defaults = {"email": "admin@example.com", "password": "adminpass123"}
    defaults.update(kwargs)
    return get_user_model().objects.create_superuser(**defaults)


class TenantListCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_admin()
        self.user = create_user(email="regular@example.com")

    def test_list_tenants_as_admin(self):
        create_tenant("Tenant A")
        create_tenant("Tenant B")
        self.client.force_authenticate(self.admin)

        res = self.client.get(TENANT_LIST_URL)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_list_tenants_unauthenticated(self):
        res = self.client.get(TENANT_LIST_URL)

        self.assertEqual(res.status_code, 401)

    def test_list_tenants_non_admin(self):
        self.client.force_authenticate(self.user)

        res = self.client.get(TENANT_LIST_URL)

        self.assertEqual(res.status_code, 403)

    def test_create_tenant_as_admin(self):
        self.client.force_authenticate(self.admin)

        res = self.client.post(TENANT_LIST_URL, {"name": "New Tenant"})

        self.assertEqual(res.status_code, 201)
        self.assertTrue(Tenant.objects.filter(name="New Tenant").exists())

    def test_create_tenant_unauthenticated(self):
        res = self.client.post(TENANT_LIST_URL, {"name": "New Tenant"})

        self.assertEqual(res.status_code, 401)

    def test_create_tenant_non_admin(self):
        self.client.force_authenticate(self.user)

        res = self.client.post(TENANT_LIST_URL, {"name": "New Tenant"})

        self.assertEqual(res.status_code, 403)

    def test_create_tenant_missing_name(self):
        self.client.force_authenticate(self.admin)

        res = self.client.post(TENANT_LIST_URL, {})

        self.assertEqual(res.status_code, 400)
        self.assertIn("name", res.data)

    def test_response_contains_expected_fields(self):
        self.client.force_authenticate(self.admin)

        res = self.client.post(TENANT_LIST_URL, {"name": "New Tenant"})

        self.assertIn("id", res.data)
        self.assertIn("name", res.data)
        self.assertIn("created_at", res.data)
        self.assertIn("updated_at", res.data)


class TenantDetailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = create_admin()
        self.user = create_user(email="regular@example.com")
        self.tenant = create_tenant()

    def test_retrieve_tenant_as_admin(self):
        self.client.force_authenticate(self.admin)

        res = self.client.get(tenant_detail_url(self.tenant.id))

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["name"], self.tenant.name)

    def test_retrieve_tenant_unauthenticated(self):
        res = self.client.get(tenant_detail_url(self.tenant.id))

        self.assertEqual(res.status_code, 401)

    def test_retrieve_tenant_non_admin(self):
        self.client.force_authenticate(self.user)

        res = self.client.get(tenant_detail_url(self.tenant.id))

        self.assertEqual(res.status_code, 403)

    def test_retrieve_tenant_not_found(self):
        self.client.force_authenticate(self.admin)
        url = tenant_detail_url("00000000-0000-0000-0000-000000000000")

        res = self.client.get(url)

        self.assertEqual(res.status_code, 404)

    def test_update_tenant_as_admin(self):
        self.client.force_authenticate(self.admin)

        res = self.client.patch(
            tenant_detail_url(self.tenant.id), {"name": "Updated Name"}
        )

        self.assertEqual(res.status_code, 200)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.name, "Updated Name")

    def test_update_tenant_non_admin(self):
        self.client.force_authenticate(self.user)

        res = self.client.patch(
            tenant_detail_url(self.tenant.id), {"name": "Updated Name"}
        )

        self.assertEqual(res.status_code, 403)

    def test_delete_tenant_as_admin(self):
        self.client.force_authenticate(self.admin)

        res = self.client.delete(tenant_detail_url(self.tenant.id))

        self.assertEqual(res.status_code, 204)
        self.assertFalse(Tenant.objects.filter(id=self.tenant.id).exists())

    def test_delete_tenant_non_admin(self):
        self.client.force_authenticate(self.user)

        res = self.client.delete(tenant_detail_url(self.tenant.id))

        self.assertEqual(res.status_code, 403)

    def test_delete_tenant_with_users_is_protected(self):
        create_user(email="member@example.com", tenant=self.tenant)
        self.client.force_authenticate(self.admin)

        res = self.client.delete(tenant_detail_url(self.tenant.id))

        self.assertEqual(res.status_code, 409)
        self.assertTrue(Tenant.objects.filter(id=self.tenant.id).exists())
