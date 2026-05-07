from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

CREATE_USER_URL = reverse("user:create")
ME_USER_URL = reverse("user:me")
LIST_USERS_URL = reverse("user:list")


def create_user(**params):
    return get_user_model().objects.create_user(**params)


def create_superuser(**params):
    return get_user_model().objects.create_superuser(**params)


class UnAuthenticatedUserApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_create_user_success(self):
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test User",
        }
        res = self.client.post(CREATE_USER_URL, payload)
        self.assertEqual(res.status_code, 201)
        user = get_user_model().objects.get(email=payload["email"])
        self.assertTrue(user.check_password(payload["password"]))
        self.assertEqual(user.name, payload["name"])
        self.assertNotIn("password", res.data)

    def test_user_with_email_exists_error(self):
        payload = {
            "email": "test@example.com",
            "password": "testpass123",
            "name": "Test User",
        }
        create_user(**payload)
        res = self.client.post(CREATE_USER_URL, payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("email", res.data)

    def test_password_too_short_error(self):
        payload = {
            "email": "test@example.com",
            "password": "pw",
            "name": "Test User",
        }
        res = self.client.post(CREATE_USER_URL, payload)
        self.assertEqual(res.status_code, 400)
        user_exists = (
            get_user_model().objects.filter(email=payload["email"]).exists()
        )
        self.assertFalse(user_exists)
        self.assertIn("password", res.data)


class AuthenticatedUserApiTests(TestCase):
    def setUp(self):
        self.user = create_user(
            email="test@example.com",
            password="testpass123",
            name="Test User",
        )
        self.other_user = create_user(
            email="other@example.com",
            password="otherpass123",
            name="Other User",
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
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(LIST_USERS_URL)
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
        payload = {
            "name": "Updated Name",
        }
        res = self.client.patch(ME_USER_URL, payload)
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, payload["name"])

    def test_update_user_unauthenticated(self):
        self.client.force_authenticate(user=None)
        payload = {
            "name": "Updated Name",
        }
        res = self.client.patch(ME_USER_URL, payload)
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
