"""
Authentication & RBAC unit tests — US-070, US-071, NFR01
"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class RegisterLoginTest(APITestCase):
    """Бүртгэл, нэвтрэлтийн тест"""

    def test_register_creates_user_and_returns_jwt(self):
        url = "/api/auth/register/"
        payload = {
            "username":  "newuser",
            "email":     "newuser@example.com",
            "password":  "SecurePass123!",
            "password2": "SecurePass123!",
        }
        r = self.client.post(url, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", r.data)
        self.assertIn("refresh", r.data)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_login_with_valid_credentials(self):
        User.objects.create_user(username="u1", email="u@x.mn", password="pw12345!")
        r = self.client.post("/api/auth/login/",
                             {"email": "u@x.mn", "password": "pw12345!"},
                             format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn("access", r.data)

    def test_login_with_invalid_credentials_returns_401(self):
        User.objects.create_user(username="u2", email="u2@x.mn", password="pw12345!")
        r = self.client.post("/api/auth/login/",
                             {"email": "u2@x.mn", "password": "wrong"},
                             format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_banned_user_cannot_login(self):
        u = User.objects.create_user(username="banned1", email="banned@x.mn", password="pw12345!")
        u.is_banned = True
        u.save()
        r = self.client.post("/api/auth/login/",
                             {"email": "banned@x.mn", "password": "pw12345!"},
                             format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class RBACTest(APITestCase):
    """Role-Based Access Control — US-071"""

    def test_guest_cannot_create_segment(self):
        """Зочин (auth-гүй) → 401"""
        r = self.client.post("/api/segments/",
                             {"start_lat": 47.918, "start_lng": 106.917,
                              "end_lat": 47.920,   "end_lng": 106.920,
                              "condition": "green", "infra_level": 4},
                             format="json")
        self.assertIn(r.status_code, (401, 403))

    def test_authenticated_user_can_create_segment(self):
        u = User.objects.create_user(username="cy1", email="cy@x.mn", password="pw12345!")
        self.client.force_authenticate(u)
        r = self.client.post("/api/segments/",
                             {"start_lat": 47.918, "start_lng": 106.917,
                              "end_lat": 47.920,   "end_lng": 106.920,
                              "condition": "green", "infra_level": 4},
                             format="json")
        self.assertIn(r.status_code, (200, 201))
