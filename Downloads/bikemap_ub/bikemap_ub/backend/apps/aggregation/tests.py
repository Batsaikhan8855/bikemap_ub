"""
Crowd Aggregation алгоритмын unit test
NFR06 — green=10, yellow=3, red=6 → green (давамгай нөхцлийн тест)
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import CrowdAggregation
from .tasks import update_aggregation
from apps.segments.models import Segment

User = get_user_model()


class CrowdAggregationModelTest(TestCase):
    """CrowdAggregation -ийн compute_dominant() методийн тест"""

    def test_dominant_when_green_majority(self):
        """green=10, yellow=3, red=6 → green"""
        agg = CrowdAggregation(green_votes=10, yellow_votes=3, red_votes=6)
        self.assertEqual(agg.compute_dominant(), "green")

    def test_dominant_when_yellow_majority(self):
        agg = CrowdAggregation(green_votes=2, yellow_votes=8, red_votes=3)
        self.assertEqual(agg.compute_dominant(), "yellow")

    def test_dominant_when_red_majority(self):
        agg = CrowdAggregation(green_votes=1, yellow_votes=1, red_votes=10)
        self.assertEqual(agg.compute_dominant(), "red")

    def test_dominant_when_zero_votes(self):
        """Нийт санал 0 → 'none'"""
        agg = CrowdAggregation(green_votes=0, yellow_votes=0, red_votes=0)
        self.assertEqual(agg.compute_dominant(), "none")

    def test_make_hash_consistency(self):
        """Ижил координат ижил hash өгнө үү"""
        h1 = CrowdAggregation.make_hash(47.918, 106.917, 47.920, 106.920)
        h2 = CrowdAggregation.make_hash(47.918, 106.917, 47.920, 106.920)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_make_hash_rounding(self):
        """3 оронтой бөөрөнхийлөлтөөс шалтгаалан ойролцоо координат ижил hash"""
        h1 = CrowdAggregation.make_hash(47.9181, 106.9171, 47.9201, 106.9201)
        h2 = CrowdAggregation.make_hash(47.9183, 106.9173, 47.9203, 106.9203)
        self.assertEqual(h1, h2)


class UpdateAggregationTest(TestCase):
    """update_aggregation() функцийн integration тест"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def _make_segment(self, condition):
        return Segment.objects.create(
            start_lat=47.918, start_lng=106.917,
            end_lat=47.920,   end_lng=106.920,
            condition=condition, infra_level=4, user=self.user,
        )

    def test_aggregation_runs_on_segment_create(self):
        """Сегмент үүсгэхэд aggregation шинэчлэгдэнэ"""
        seg = self._make_segment("green")
        agg = update_aggregation(seg)
        self.assertEqual(agg.green_votes, 1)
        self.assertEqual(agg.dominant, "green")

    def test_aggregation_majority_vote(self):
        """green=2, yellow=1, red=0 → green davamgai"""
        self._make_segment("green")
        self._make_segment("green")
        s3 = self._make_segment("yellow")
        agg = update_aggregation(s3)
        self.assertEqual(agg.green_votes, 2)
        self.assertEqual(agg.yellow_votes, 1)
        self.assertEqual(agg.dominant, "green")
