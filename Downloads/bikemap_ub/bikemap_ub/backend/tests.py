"""
BikeMap UB — Comprehensive Test Suite
Багшийн шаардлага: coverage ≥ 30%, 20-30+ test case
Runs with: python manage.py test tests --verbosity=2
"""
from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.models import User
from apps.pois.models import POI, POIVote
from apps.segments.models import Segment
from apps.aggregation.models import CrowdAggregation
import io


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_user(email="u@test.com", username="testuser", role="cyclist", password="Pass1234!"):
    return User.objects.create_user(
        email=email, username=username, password=password, role=role
    )

def auth_client(user):
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return client

def make_poi(user, status="approved", poi_type="danger",
             lat="47.916700", lng="106.916700"):
    return POI.objects.create(
        user=user, latitude=lat, longitude=lng,
        poi_type=poi_type, status=status,
    )

def make_segment(user, condition="green"):
    return Segment.objects.create(
        user=user,
        start_lat="47.916700", start_lng="106.916700",
        end_lat="47.920000",   end_lng="106.920000",
        condition=condition, infra_level=4,
    )

def make_gpx_file(n_points=5):
    pts = "\n".join(
        f'    <trkpt lat="{47.9 + i*0.001}" lon="{106.9 + i*0.001}"></trkpt>'
        for i in range(n_points)
    )
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <trk><name>T</name><trkseg>
{pts}
  </trkseg></trk>
</gpx>"""
    f = io.BytesIO(content.encode())
    f.name = "route.gpx"
    return f


# ══════════════════════════════════════════════════════════════════════════════
# 1. USER MODEL TESTS
# ══════════════════════════════════════════════════════════════════════════════

class UserModelTest(TestCase):

    def test_create_user_defaults(self):
        u = make_user()
        self.assertEqual(u.role, "cyclist")
        self.assertFalse(u.is_banned)
        self.assertEqual(u.total_pois, 0)
        self.assertEqual(u.total_segments, 0)
        self.assertEqual(u.total_distance_km, 0.0)

    def test_is_admin_or_mod_for_admin(self):
        u = make_user(email="a@test.com", username="admin_u", role="admin")
        self.assertTrue(u.is_admin_or_mod)

    def test_is_admin_or_mod_for_moderator(self):
        u = make_user(email="m@test.com", username="mod_u", role="moderator")
        self.assertTrue(u.is_admin_or_mod)

    def test_is_admin_or_mod_false_for_cyclist(self):
        u = make_user()
        self.assertFalse(u.is_admin_or_mod)

    def test_str_representation(self):
        u = make_user()
        self.assertIn("u@test.com", str(u))
        self.assertIn("cyclist", str(u))


# ══════════════════════════════════════════════════════════════════════════════
# 2. AUTHENTICATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class AuthTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = make_user(email="auth@test.com", username="authuser")

    def test_login_success(self):
        res = self.client.post("/api/auth/login/",
                               {"email": "auth@test.com", "password": "Pass1234!"},
                               content_type="application/json")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("access", data)
        self.assertIn("user", data)
        self.assertEqual(data["user"]["username"], "authuser")

    def test_login_wrong_password(self):
        res = self.client.post("/api/auth/login/",
                               {"email": "auth@test.com", "password": "wrong"},
                               content_type="application/json")
        self.assertEqual(res.status_code, 401)

    def test_login_sets_httponly_cookie(self):
        res = self.client.post("/api/auth/login/",
                               {"email": "auth@test.com", "password": "Pass1234!"},
                               content_type="application/json")
        self.assertIn("bm_access", res.cookies)
        self.assertTrue(res.cookies["bm_access"]["httponly"])

    def test_register_creates_user(self):
        res = self.client.post("/api/auth/register/",
                               {"email": "new@test.com", "username": "newbie",
                                "password": "Secure123!", "password2": "Secure123!"},
                               content_type="application/json")
        self.assertEqual(res.status_code, 201)
        self.assertTrue(User.objects.filter(email="new@test.com").exists())

    def test_register_duplicate_email_fails(self):
        res = self.client.post("/api/auth/register/",
                               {"email": "auth@test.com", "username": "dup",
                                "password": "Secure123!", "password2": "Secure123!"},
                               content_type="application/json")
        self.assertNotEqual(res.status_code, 201)

    def test_banned_user_cannot_login(self):
        self.user.is_banned = True
        self.user.save()
        res = self.client.post("/api/auth/login/",
                               {"email": "auth@test.com", "password": "Pass1234!"},
                               content_type="application/json")
        self.assertEqual(res.status_code, 403)

    def test_profile_requires_auth(self):
        res = self.client.get("/api/auth/profile/")
        self.assertEqual(res.status_code, 401)

    def test_profile_returns_user_data(self):
        c = auth_client(self.user)
        res = c.get("/api/auth/profile/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["username"], "authuser")


# ══════════════════════════════════════════════════════════════════════════════
# 3. SEGMENT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class SegmentTest(TestCase):

    def setUp(self):
        self.user = make_user(email="seg@test.com", username="seguser")
        self.client = auth_client(self.user)

    def test_list_segments_public(self):
        make_segment(self.user)
        res = APIClient().get("/api/segments/")
        self.assertEqual(res.status_code, 200)

    def test_create_segment_authenticated(self):
        res = self.client.post("/api/segments/", {
            "start_lat": "47.916700", "start_lng": "106.916700",
            "end_lat":   "47.920000", "end_lng":   "106.920000",
            "condition": "green", "infra_level": 4,
        }, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Segment.objects.count(), 1)

    def test_create_segment_unauthenticated_denied(self):
        res = APIClient().post("/api/segments/", {
            "start_lat": "47.916700", "start_lng": "106.916700",
            "end_lat":   "47.920000", "end_lng":   "106.920000",
            "condition": "green", "infra_level": 4,
        }, format="json")
        self.assertEqual(res.status_code, 401)

    def test_segment_condition_choices(self):
        res = self.client.post("/api/segments/", {
            "start_lat": "47.916700", "start_lng": "106.916700",
            "end_lat":   "47.920000", "end_lng":   "106.920000",
            "condition": "invalid_cond", "infra_level": 4,
        }, format="json")
        self.assertEqual(res.status_code, 400)

    def test_bulk_import_segments(self):
        segs = [
            {"start_lat": "47.916700", "start_lng": "106.916700",
             "end_lat": "47.917000", "end_lng": "106.917000",
             "condition": "yellow", "infra_level": 3, "is_created": False},
            {"start_lat": "47.917000", "start_lng": "106.917000",
             "end_lat": "47.918000", "end_lng": "106.918000",
             "condition": "red", "infra_level": 5, "is_created": False},
        ]
        res = self.client.post("/api/segments/bulk-import/",
                               {"segments": segs}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["created"], 2)
        self.assertEqual(Segment.objects.count(), 2)

    def test_bulk_import_exceeds_limit(self):
        segs = [{"start_lat": "47.9", "start_lng": "106.9",
                 "end_lat": "47.901", "end_lng": "106.901",
                 "condition": "green", "infra_level": 4}] * 501
        res = self.client.post("/api/segments/bulk-import/",
                               {"segments": segs}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_delete_own_segment(self):
        seg = make_segment(self.user)
        res = self.client.delete(f"/api/segments/{seg.id}/")
        self.assertEqual(res.status_code, 204)

    def test_delete_other_segment_denied(self):
        other = make_user(email="other@test.com", username="other")
        seg = make_segment(other)
        res = self.client.delete(f"/api/segments/{seg.id}/")
        self.assertEqual(res.status_code, 403)


# ══════════════════════════════════════════════════════════════════════════════
# 4. POI TESTS
# ══════════════════════════════════════════════════════════════════════════════

class POITest(TestCase):

    def setUp(self):
        self.cyclist = make_user(email="c@test.com", username="cyclist1")
        self.mod = make_user(email="mod@test.com", username="mod1", role="moderator")
        self.cyclist_client = auth_client(self.cyclist)
        self.mod_client     = auth_client(self.mod)

    def test_list_pois_shows_only_approved_for_anon(self):
        make_poi(self.cyclist, status="approved")
        make_poi(self.cyclist, status="pending")
        res = APIClient().get("/api/pois/")
        data = res.json()
        items = data.get("results", data)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["status"], "approved")

    def test_create_poi_requires_auth(self):
        res = APIClient().post("/api/pois/", {
            "latitude": "47.9167", "longitude": "106.9167",
            "poi_type": "danger",
        }, format="json")
        self.assertIn(res.status_code, [401, 403])

    def test_create_poi_sets_pending(self):
        res = self.cyclist_client.post("/api/pois/", {
            "latitude": "47.916700", "longitude": "106.916700",
            "poi_type": "danger",
        }, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["status"], "pending")

    def test_moderator_can_approve_poi(self):
        poi = make_poi(self.cyclist, status="pending")
        res = self.mod_client.post(f"/api/pois/{poi.id}/approve/")
        self.assertEqual(res.status_code, 200)
        poi.refresh_from_db()
        self.assertEqual(poi.status, "approved")

    def test_cyclist_cannot_approve_poi(self):
        poi = make_poi(self.cyclist, status="pending")
        res = self.cyclist_client.post(f"/api/pois/{poi.id}/approve/")
        self.assertEqual(res.status_code, 403)

    def test_moderator_can_reject_with_reason(self):
        poi = make_poi(self.cyclist, status="pending")
        res = self.mod_client.post(f"/api/pois/{poi.id}/reject/",
                                   {"reason": "Дутуу мэдээлэл"}, format="json")
        self.assertEqual(res.status_code, 200)
        poi.refresh_from_db()
        self.assertEqual(poi.status, "rejected")
        self.assertEqual(poi.reject_reason, "Дутуу мэдээлэл")

    def test_reject_without_reason_fails(self):
        poi = make_poi(self.cyclist, status="pending")
        res = self.mod_client.post(f"/api/pois/{poi.id}/reject/",
                                   {"reason": ""}, format="json")
        self.assertEqual(res.status_code, 400)


# ══════════════════════════════════════════════════════════════════════════════
# 5. VOTE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class VoteTest(TestCase):

    def setUp(self):
        self.owner  = make_user(email="owner@test.com", username="owner")
        self.voter  = make_user(email="voter@test.com", username="voter")
        self.poi    = make_poi(self.owner, status="approved")
        self.client = auth_client(self.voter)

    def test_upvote_increments(self):
        res = self.client.post(f"/api/pois/{self.poi.id}/vote/",
                               {"vote_type": "up"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.poi.refresh_from_db()
        self.assertEqual(self.poi.upvotes, 1)

    def test_double_upvote_toggles_off(self):
        self.client.post(f"/api/pois/{self.poi.id}/vote/",
                         {"vote_type": "up"}, format="json")
        self.client.post(f"/api/pois/{self.poi.id}/vote/",
                         {"vote_type": "up"}, format="json")
        self.poi.refresh_from_db()
        self.assertEqual(self.poi.upvotes, 0)

    def test_switch_upvote_to_downvote(self):
        self.client.post(f"/api/pois/{self.poi.id}/vote/",
                         {"vote_type": "up"}, format="json")
        self.client.post(f"/api/pois/{self.poi.id}/vote/",
                         {"vote_type": "down"}, format="json")
        self.poi.refresh_from_db()
        self.assertEqual(self.poi.upvotes, 0)
        self.assertEqual(self.poi.downvotes, 1)

    def test_invalid_vote_type_rejected(self):
        res = self.client.post(f"/api/pois/{self.poi.id}/vote/",
                               {"vote_type": "invalid"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_unauthenticated_vote_denied(self):
        res = APIClient().post(f"/api/pois/{self.poi.id}/vote/",
                               {"vote_type": "up"}, format="json")
        self.assertIn(res.status_code, [401, 403])

    def test_voter_can_vote_on_others_poi(self):
        """Cyclist must be able to vote on any approved POI — regression test."""
        res = self.client.post(f"/api/pois/{self.poi.id}/vote/",
                               {"vote_type": "up"}, format="json")
        self.assertEqual(res.status_code, 200)


# ══════════════════════════════════════════════════════════════════════════════
# 6. GPX IMPORT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class GPXImportTest(TestCase):

    def setUp(self):
        self.user   = make_user(email="gpx@test.com", username="gpxuser")
        self.client = auth_client(self.user)

    def test_gpx_import_returns_points(self):
        f = make_gpx_file(10)
        res = self.client.post("/api/routes/gpx-import/",
                               {"gpx_file": f}, format="multipart")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("points", data)
        self.assertGreaterEqual(len(data["points"]), 2)

    def test_gpx_import_unauthenticated_denied(self):
        f = make_gpx_file(5)
        res = APIClient().post("/api/routes/gpx-import/",
                               {"gpx_file": f}, format="multipart")
        self.assertIn(res.status_code, [401, 403])

    def test_gpx_import_no_file_fails(self):
        res = self.client.post("/api/routes/gpx-import/", {}, format="multipart")
        self.assertEqual(res.status_code, 400)

    def test_gpx_import_wrong_extension_fails(self):
        f = io.BytesIO(b"not gpx content")
        f.name = "route.txt"
        res = self.client.post("/api/routes/gpx-import/",
                               {"gpx_file": f}, format="multipart")
        self.assertEqual(res.status_code, 400)


# ══════════════════════════════════════════════════════════════════════════════
# 7. AGGREGATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class AggregationTest(TestCase):

    def setUp(self):
        self.user = make_user(email="agg@test.com", username="agguser")

    def test_aggregation_created_on_segment_save(self):
        seg = make_segment(self.user, condition="green")
        from apps.aggregation.tasks import update_aggregation
        update_aggregation(seg)
        self.assertTrue(CrowdAggregation.objects.exists())

    def test_aggregation_dominant_majority(self):
        """3 green + 1 red → dominant = green"""
        u2 = make_user(email="u2@t.com", username="u2")
        u3 = make_user(email="u3@t.com", username="u3")
        u4 = make_user(email="u4@t.com", username="u4")
        from apps.aggregation.tasks import update_aggregation
        for u, cond in [(self.user, "green"), (u2, "green"), (u3, "green"), (u4, "red")]:
            seg = make_segment(u, condition=cond)
            update_aggregation(seg)
        agg = CrowdAggregation.objects.first()
        self.assertEqual(agg.dominant, "green")
