"""
POI CRUD ба санал өгөх тест — US-020, US-022, US-051
"""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from .models import POI

User = get_user_model()


class POICreateTest(APITestCase):
    """POI үүсгэх — US-020"""

    def setUp(self):
        self.user = User.objects.create_user(username="cy1", email="cy@x.mn", password="pw12345!")
        self.client.force_authenticate(self.user)

    def test_create_poi_status_pending(self):
        r = self.client.post("/api/pois/", {
            "latitude": 47.918, "longitude": 106.917,
            "poi_type": "danger", "description": "Big pothole",
        }, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["status"], "pending")
        self.user.refresh_from_db()
        self.assertEqual(self.user.total_pois, 1)


class POIVoteTest(APITestCase):
    """upvote / downvote — US-022"""

    def setUp(self):
        self.owner = User.objects.create_user(username="owner1", email="o@x.mn", password="pw12345!")
        self.voter = User.objects.create_user(username="voter1", email="v@x.mn", password="pw12345!")
        self.poi = POI.objects.create(
            user=self.owner, latitude=47.918, longitude=106.917,
            poi_type="danger", status="approved",
        )

    def test_upvote_increments_count(self):
        self.client.force_authenticate(self.voter)
        r = self.client.post(f"/api/pois/{self.poi.id}/vote/",
                             {"vote_type": "up"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["upvotes"], 1)
        self.assertEqual(r.data["downvotes"], 0)

    def test_double_upvote_toggles_off(self):
        """Хэрэглэгч upvote 2 удаа дарахад устдаг"""
        self.client.force_authenticate(self.voter)
        self.client.post(f"/api/pois/{self.poi.id}/vote/",
                         {"vote_type": "up"}, format="json")
        r = self.client.post(f"/api/pois/{self.poi.id}/vote/",
                             {"vote_type": "up"}, format="json")
        self.assertEqual(r.data["status"], "vote_removed")
        self.poi.refresh_from_db()
        self.assertEqual(self.poi.upvotes, 0)

    def test_switch_from_up_to_down(self):
        self.client.force_authenticate(self.voter)
        self.client.post(f"/api/pois/{self.poi.id}/vote/",
                         {"vote_type": "up"}, format="json")
        r = self.client.post(f"/api/pois/{self.poi.id}/vote/",
                             {"vote_type": "down"}, format="json")
        self.assertEqual(r.data["upvotes"], 0)
        self.assertEqual(r.data["downvotes"], 1)

    def test_unauthenticated_cannot_vote(self):
        r = self.client.post(f"/api/pois/{self.poi.id}/vote/",
                             {"vote_type": "up"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_vote_type_returns_400(self):
        self.client.force_authenticate(self.voter)
        r = self.client.post(f"/api/pois/{self.poi.id}/vote/",
                             {"vote_type": "xxx"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


class POIApprovalTest(APITestCase):
    """Админ батлах / татгалзах — US-051"""

    def setUp(self):
        self.cyclist = User.objects.create_user(username="cy2", email="cy@x.mn", password="pw12345!")
        self.admin   = User.objects.create_user(username="ad1", email="ad@x.mn", password="pw12345!")
        self.admin.role = "admin"
        self.admin.save()
        self.poi = POI.objects.create(
            user=self.cyclist, latitude=47.918, longitude=106.917,
            poi_type="danger", status="pending",
        )

    def test_admin_can_approve(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f"/api/pois/{self.poi.id}/approve/", {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.poi.refresh_from_db()
        self.assertEqual(self.poi.status, "approved")

    def test_cyclist_cannot_approve(self):
        """Жирийн хэрэглэгч POI батлах эрхгүй"""
        self.client.force_authenticate(self.cyclist)
        r = self.client.post(f"/api/pois/{self.poi.id}/approve/", {}, format="json")
        self.assertIn(r.status_code, (401, 403))

    def test_admin_reject_requires_reason(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(f"/api/pois/{self.poi.id}/reject/",
                             {}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

        r = self.client.post(f"/api/pois/{self.poi.id}/reject/",
                             {"reason": "Spam"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.poi.refresh_from_db()
        self.assertEqual(self.poi.status, "rejected")
        self.assertEqual(self.poi.reject_reason, "Spam")
