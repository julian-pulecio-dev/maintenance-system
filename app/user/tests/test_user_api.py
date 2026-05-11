from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from tenant.models import Tenant

CREATE_USER_URL = reverse("user:create")
ME_USER_URL = reverse("user:me")
LIST_USERS_URL = reverse("user:list")


def promote_url(user_id):
    return reverse("user:promote", args=[user_id])


def create_tenant(name="Test Tenant"):
    return Tenant.objects.create(name=name)


def create_user(**params):
    return get_user_model().objects.create_user(**params)


def create_superuser(**params):
    return get_user_model().objects.create_superuser(**params)


class UnAuthenticatedUserApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = create_tenant()

    def test_create_user_success(self):
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test User",
        }
        res = self.client.post(
            CREATE_USER_URL, payload, HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(res.status_code, 201)
        user = get_user_model().objects.get(email=payload["email"])
        self.assertTrue(user.check_password(payload["password"]))
        self.assertEqual(user.name, payload["name"])
        self.assertEqual(user.tenant, self.tenant)
        self.assertNotIn("password", res.data)

    def test_create_user_without_tenant_header_fails(self):
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test User",
        }
        res = self.client.post(CREATE_USER_URL, payload)
        self.assertEqual(res.status_code, 403)

    def test_user_with_email_exists_error(self):
        create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test User",
        }
        res = self.client.post(
            CREATE_USER_URL, payload, HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.data)

    def test_password_too_short_error(self):
        payload = {
            "email": "test@example.com",
            "password": "pw",
            "name": "Test User",
        }
        res = self.client.post(
            CREATE_USER_URL, payload, HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(res.status_code, 400)
        user_exists = (
            get_user_model().objects.filter(email=payload["email"]).exists()
        )
        self.assertFalse(user_exists)
        self.assertIn("password", res.data)


class AuthenticatedUserApiTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.user = create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User",
            tenant=self.tenant,
        )
        self.other_user = create_user(
            email="other@example.com",
            password="otherpass123",
            name="Other User",
            tenant=self.tenant,
        )
        self.superuser = create_superuser(
            email="superuser@example.com",
            password="superpass123",
            name="Super User",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_retrieve_user_authenticated(self):
        res = self.client.get(ME_USER_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["email"], self.user.email)

    def test_retrieve_user_unauthenticated(self):
        self.client.force_authenticate(user=None)
        res = self.client.get(ME_USER_URL)
        self.assertEqual(res.status_code, 401)

    def test_list_users_success(self):
        res = self.client.get(
            LIST_USERS_URL, HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        self.assertEqual(res.status_code, 200)

    def test_list_users_unauthenticated(self):
        self.client.force_authenticate(user=None)
        res = self.client.get(LIST_USERS_URL)
        self.assertEqual(res.status_code, 401)

    def test_list_users_unauthorized(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get(LIST_USERS_URL)
        self.assertEqual(res.status_code, 403)

    def test_update_user_success(self):
        payload = {"name": "Updated Name"}
        res = self.client.patch(ME_USER_URL, payload)
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, payload["name"])

    def test_update_user_unauthenticated(self):
        self.client.force_authenticate(user=None)
        res = self.client.patch(ME_USER_URL, {"name": "Updated Name"})
        self.assertEqual(res.status_code, 401)

    def test_delete_user_success(self):
        res = self.client.delete(ME_USER_URL)
        self.assertEqual(res.status_code, 204)
        user_exists = get_user_model().objects.filter(id=self.user.id).exists()
        self.assertFalse(user_exists)

    def test_delete_user_unauthenticated(self):
        self.client.force_authenticate(user=None)
        res = self.client.delete(ME_USER_URL)
        self.assertEqual(res.status_code, 401)


class PromoteUserApiTests(TestCase):
    def setUp(self):
        self.tenant = create_tenant()
        self.staff_user = create_user(
            email="staff@example.com",
            password="staffpass123",
            name="Staff User",
            tenant=self.tenant,
            is_staff=True,
        )
        self.regular_user = create_user(
            email="regular@example.com",
            password="regularpass123",
            name="Regular User",
            tenant=self.tenant,
        )
        self.superuser = create_superuser(
            email="superuser@example.com",
            password="superpass123",
            name="Super User",
        )
        self.client = APIClient()

    def test_staff_can_promote_user(self):
        self.client.force_authenticate(user=self.staff_user)
        url = promote_url(self.regular_user.id)
        res = self.client.post(url, HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(res.status_code, 200)
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_staff)
        self.assertTrue(res.data["is_staff"])

    def test_superuser_can_promote_user(self):
        self.client.force_authenticate(user=self.superuser)
        url = promote_url(self.regular_user.id)
        res = self.client.post(url, HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(res.status_code, 200)
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_staff)

    def test_regular_user_cannot_promote(self):
        self.client.force_authenticate(user=self.regular_user)
        url = promote_url(self.regular_user.id)
        res = self.client.post(url, HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(res.status_code, 403)

    def test_unauthenticated_cannot_promote(self):
        url = promote_url(self.regular_user.id)
        res = self.client.post(url, HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(res.status_code, 401)

    def test_promote_missing_tenant_header_fails(self):
        self.client.force_authenticate(user=self.staff_user)
        url = promote_url(self.regular_user.id)
        res = self.client.post(url)
        self.assertEqual(res.status_code, 403)

    def test_promote_user_not_in_tenant_returns_404(self):
        other_tenant = create_tenant(name="Other Tenant")
        other_user = create_user(
            email="other@example.com",
            password="otherpass123",
            name="Other User",
            tenant=other_tenant,
        )
        self.client.force_authenticate(user=self.staff_user)
        url = promote_url(other_user.id)
        res = self.client.post(url, HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(res.status_code, 404)

    def test_promote_already_staff_returns_409(self):
        already_staff = create_user(
            email="already@example.com",
            password="alreadypass123",
            name="Already Staff",
            tenant=self.tenant,
            is_staff=True,
        )
        self.client.force_authenticate(user=self.staff_user)
        url = promote_url(already_staff.id)
        res = self.client.post(url, HTTP_X_TENANT_ID=str(self.tenant.id))
        self.assertEqual(res.status_code, 409)
