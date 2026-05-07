from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from user.models import PasswordResetToken

User = get_user_model()

FORGOT_PASSWORD_URL = reverse("user:forgot-password")
RESET_PASSWORD_URL = reverse("user:reset-password")


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


class ResetPasswordViewTestCase(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.reset_token = PasswordResetToken.objects.create(user=self.user)

    def test_resets_password_with_valid_token(self):
        response = self.client.post(
            RESET_PASSWORD_URL,
            {
                "token": str(self.reset_token.token),
                "new_password": "newpass456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass456"))

    def test_marks_token_as_used(self):
        self.client.post(
            RESET_PASSWORD_URL,
            {
                "token": str(self.reset_token.token),
                "new_password": "newpass456",
            },
        )

        self.reset_token.refresh_from_db()
        self.assertTrue(self.reset_token.is_used)

    def test_returns_400_for_already_used_token(self):
        self.reset_token.is_used = True
        self.reset_token.save()

        response = self.client.post(
            RESET_PASSWORD_URL,
            {
                "token": str(self.reset_token.token),
                "new_password": "newpass456",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_returns_400_for_expired_token(self):
        self.reset_token.created_at = timezone.now() - timezone.timedelta(
            hours=2
        )
        self.reset_token.save()

        response = self.client.post(
            RESET_PASSWORD_URL,
            {
                "token": str(self.reset_token.token),
                "new_password": "newpass456",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_returns_400_for_nonexistent_token(self):
        import uuid

        response = self.client.post(
            RESET_PASSWORD_URL,
            {"token": str(uuid.uuid4()), "new_password": "newpass456"},
        )

        self.assertEqual(response.status_code, 400)

    def test_returns_400_for_password_too_short(self):
        response = self.client.post(
            RESET_PASSWORD_URL,
            {"token": str(self.reset_token.token), "new_password": "pw"},
        )

        self.assertEqual(response.status_code, 400)

    def test_returns_400_when_token_missing(self):
        response = self.client.post(
            RESET_PASSWORD_URL,
            {"new_password": "newpass456"},
        )

        self.assertEqual(response.status_code, 400)

    def test_returns_400_when_password_missing(self):
        response = self.client.post(
            RESET_PASSWORD_URL,
            {"token": str(self.reset_token.token)},
        )

        self.assertEqual(response.status_code, 400)

    def test_used_token_cannot_reset_password_again(self):
        self.client.post(
            RESET_PASSWORD_URL,
            {
                "token": str(self.reset_token.token),
                "new_password": "newpass456",
            },
        )

        response = self.client.post(
            RESET_PASSWORD_URL,
            {
                "token": str(self.reset_token.token),
                "new_password": "anotherpass",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.check_password("anotherpass"))
