from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from user.models import PasswordResetToken

User = get_user_model()

FORGOT_PASSWORD_URL = reverse("user:forgot-password")


def create_user(**kwargs):
    defaults = {"email": "user@example.com", "password": "testpass123"}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


class ForgotPasswordViewTestCase(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()

    def test_returns_200_for_existing_email(self):
        response = self.client.post(
            FORGOT_PASSWORD_URL, {"email": self.user.email}
        )

        self.assertEqual(response.status_code, 200)

    def test_returns_200_for_nonexistent_email(self):
        response = self.client.post(
            FORGOT_PASSWORD_URL, {"email": "nobody@example.com"}
        )

        self.assertEqual(response.status_code, 200)

    def test_creates_reset_token_for_existing_user(self):
        self.client.post(FORGOT_PASSWORD_URL, {"email": self.user.email})

        self.assertTrue(
            PasswordResetToken.objects.filter(user=self.user).exists()
        )

    def test_does_not_create_token_for_nonexistent_email(self):
        self.client.post(FORGOT_PASSWORD_URL, {"email": "nobody@example.com"})

        self.assertEqual(PasswordResetToken.objects.count(), 0)

    def test_sends_email_to_user(self):
        self.client.post(FORGOT_PASSWORD_URL, {"email": self.user.email})

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_email_contains_token(self):
        self.client.post(FORGOT_PASSWORD_URL, {"email": self.user.email})

        token = PasswordResetToken.objects.get(user=self.user)
        self.assertIn(str(token.token), mail.outbox[0].body)

    def test_does_not_send_email_for_nonexistent_user(self):
        self.client.post(FORGOT_PASSWORD_URL, {"email": "nobody@example.com"})

        self.assertEqual(len(mail.outbox), 0)

    def test_returns_400_for_invalid_email_format(self):
        response = self.client.post(
            FORGOT_PASSWORD_URL, {"email": "not-an-email"}
        )

        self.assertEqual(response.status_code, 400)

    def test_returns_400_when_email_missing(self):
        response = self.client.post(FORGOT_PASSWORD_URL, {})

        self.assertEqual(response.status_code, 400)
