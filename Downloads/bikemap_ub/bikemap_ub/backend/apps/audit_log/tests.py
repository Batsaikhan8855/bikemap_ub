from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from .models import AuditLog
from apps.pois.models import POI

User = get_user_model()


class AuditLogTest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin1", email="ad@x.mn", password="pw12345!")
        self.admin.role = "admin"
        self.admin.save()
        self.cy = User.objects.create_user(username="cy1", email="cy@x.mn", password="pw12345!")
        self.poi = POI.objects.create(
            user=self.cy, latitude=47.918,
            longitude=106.917, poi_type="danger",
            status="pending",
        )

    def test_approve_creates_audit_log(self):
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/pois/{self.poi.id}/approve/", {}, format="json")
        log = AuditLog.objects.filter(action="poi_approve").last()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.admin)
        self.assertEqual(log.target_id, self.poi.id)

    def test_reject_logs_reason_in_detail(self):
        self.client.force_authenticate(self.admin)
        self.client.post(f"/api/pois/{self.poi.id}/reject/",
                         {"reason": "Spam"}, format="json")
        log = AuditLog.objects.filter(action="poi_reject").last()
        self.assertEqual(log.detail, "Spam")
