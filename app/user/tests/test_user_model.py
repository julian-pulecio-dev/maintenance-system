from django.test import TestCase
from django.contrib.auth import get_user_model


class UserModelTest(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        return

    def test_create_user_successfully(self):
        user = self.user_model.objects.create_user(
            email="test_user@email.com", password="user_password123*"
        )
        self.assertEqual(1, self.user_model.objects.count())
        self.assertEqual(user.email, "test_user@email.com")
        self.assertTrue(user.check_password("user_password123*"))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser_successfully(self):
        superuser = self.user_model.objects.create_superuser(
            email="test_superuser@email.com", password="superuser_password123*"
        )
        self.assertEqual(1, self.user_model.objects.count())
        self.assertEqual(superuser.email, "test_superuser@email.com")
        self.assertTrue(superuser.check_password("superuser_password123*"))
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

    def test_create_superuser_without_email_raises_value_error(self):
        with self.assertRaisesMessage(ValueError, "Email is required"):
            self.user_model.objects.create_superuser(
                email="", password="superuser_password123*"
            )

    def test_create_user_without_password_raises_value_error(self):
        with self.assertRaisesMessage(ValueError, "Password is required"):
            self.user_model.objects.create_user(
                email="test_user@email.com", password=""
            )
