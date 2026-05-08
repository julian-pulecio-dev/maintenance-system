from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from tenant.models import Tenant
from user.models import PasswordResetToken

User = get_user_model()

FORGOT_PASSWORD_URL = reverse("user:forgot-password")


def create_tenant(name="Test Tenant"):
    return Tenant.objects.create(name=name)


def create_user(**kwargs):
    defaults = {"email": "user@example.com", "password": "testpass123"}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class ForgotPasswordViewTestCase(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.tenant = create_tenant()
        self.user = create_user(tenant=self.tenant)

    def test_returns_200_for_existing_email(self):
        response = self.client.post(
            FORGOT_PASSWORD_URL,
            {"email": self.user.email},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(response.status_code, 200)

    def test_returns_200_for_nonexistent_email(self):
        response = self.client.post(
            FORGOT_PASSWORD_URL,
            {"email": "nobody@example.com"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(response.status_code, 200)

    def test_creates_reset_token_for_existing_user(self):
        self.client.post(
            FORGOT_PASSWORD_URL,
            {"email": self.user.email},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertTrue(
            PasswordResetToken.objects.filter(user=self.user).exists()
        )

    def test_does_not_create_token_for_nonexistent_email(self):
        self.client.post(
            FORGOT_PASSWORD_URL,
            {"email": "nobody@example.com"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(PasswordResetToken.objects.count(), 0)

    def test_sends_email_to_user(self):
        self.client.post(
            FORGOT_PASSWORD_URL,
            {"email": self.user.email},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_email_contains_token(self):
        self.client.post(
            FORGOT_PASSWORD_URL,
            {"email": self.user.email},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        token = PasswordResetToken.objects.get(user=self.user)
        self.assertIn(str(token.token), mail.outbox[0].body)

    def test_does_not_send_email_for_nonexistent_user(self):
        self.client.post(
            FORGOT_PASSWORD_URL,
            {"email": "nobody@example.com"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_returns_400_for_invalid_email_format(self):
        response = self.client.post(
            FORGOT_PASSWORD_URL,
            {"email": "not-an-email"},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(response.status_code, 400)

    def test_returns_400_when_email_missing(self):
        response = self.client.post(
            FORGOT_PASSWORD_URL,
            {},
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(response.status_code, 400)


RESET_PASSWORD_URL = reverse("user:reset-password")


class ResetPasswordViewTestCase(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.tenant = create_tenant()
        self.user = create_user(tenant=self.tenant)
        self.reset_token = PasswordResetToken.objects.create(user=self.user)

    def test_returns_200_with_valid_token(self):
        response = self.client.post(
            RESET_PASSWORD_URL,
            {"token": str(self.reset_token.token), "password": "newpass123"},
        )
        self.assertEqual(response.status_code, 200)

    def test_password_is_updated(self):
        new_password = "newpass123"
        self.client.post(
            RESET_PASSWORD_URL,
            {"token": str(self.reset_token.token), "password": new_password},
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_token_is_marked_as_used(self):
        self.client.post(
            RESET_PASSWORD_URL,
            {"token": str(self.reset_token.token), "password": "newpass123"},
        )
        self.reset_token.refresh_from_db()
        self.assertTrue(self.reset_token.is_used)

    def test_returns_400_for_already_used_token(self):
        self.reset_token.mark_as_used()
        response = self.client.post(
            RESET_PASSWORD_URL,
            {"token": str(self.reset_token.token), "password": "newpass123"},
        )
        self.assertEqual(response.status_code, 400)

    def test_returns_400_for_invalid_token(self):
        response = self.client.post(
            RESET_PASSWORD_URL,
            {
                "token": "00000000-0000-0000-0000-000000000000",
                "password": "newpass123",
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_returns_400_when_password_too_short(self):
        response = self.client.post(
            RESET_PASSWORD_URL,
            {"token": str(self.reset_token.token), "password": "abc"},
        )
        self.assertEqual(response.status_code, 400)

    def test_returns_400_when_token_missing(self):
        response = self.client.post(
            RESET_PASSWORD_URL, {"password": "newpass123"}
        )
        self.assertEqual(response.status_code, 400)
