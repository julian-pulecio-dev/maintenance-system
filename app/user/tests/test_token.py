from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from tenant.models import Tenant

TOKEN_URL = reverse("token_obtain_pair")

User = get_user_model()


def create_tenant(name="Test Tenant"):
    return Tenant.objects.create(name=name)


class TokenObtainTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = create_tenant()
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        self.superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass123",
        )

    def test_login_regular_user_with_tenant_header(self):
        res = self.client.post(
            TOKEN_URL,
            {"email": "user@example.com", "password": "testpass123"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_login_superuser_without_tenant_header(self):
        res = self.client.post(
            TOKEN_URL,
            {"email": "admin@example.com", "password": "adminpass123"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)

    def test_login_wrong_password(self):
        res = self.client.post(
            TOKEN_URL,
            {"email": "user@example.com", "password": "wrongpass"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(res.status_code, 401)

    def test_login_wrong_tenant(self):
        other_tenant = create_tenant(name="Other Tenant")
        res = self.client.post(
            TOKEN_URL,
            {"email": "user@example.com", "password": "testpass123"},
            HTTP_X_TENANT_ID=str(other_tenant.id),
        )
        self.assertEqual(res.status_code, 401)

    def test_login_invalid_tenant_id(self):
        res = self.client.post(
            TOKEN_URL,
            {"email": "user@example.com", "password": "testpass123"},
            HTTP_X_TENANT_ID="not-a-uuid",
        )
        self.assertEqual(res.status_code, 400)

    def test_login_regular_user_without_tenant_header_fails(self):
        res = self.client.post(
            TOKEN_URL,
            {"email": "user@example.com", "password": "testpass123"},
        )
        self.assertEqual(res.status_code, 401)
