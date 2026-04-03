from django.db import models
from django.conf import settings


class POI(models.Model):
    """
    Point of Interest — E3 US-020 US-021 US-022 US-023
    Types: danger, no_bike_lane, road_damage, parking_problem, bike_repair, bike_parking
    """
    POI_TYPE_CHOICES = [
        ("danger",          "Danger"),
        ("no_bike_lane",    "No Bike Lane"),
        ("road_damage",     "Road Damage"),
        ("parking_problem", "Parking Problem"),
        ("bike_repair",     "Bike Repair"),
        ("bike_parking",    "Bike Parking"),
    ]
    STATUS_CHOICES = [
        ("pending",  "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True,
                                    related_name="pois")
    latitude    = models.DecimalField(max_digits=9, decimal_places=6)
    longitude   = models.DecimalField(max_digits=9, decimal_places=6)
    poi_type    = models.CharField(max_length=30, choices=POI_TYPE_CHOICES)
    description = models.TextField(blank=True)
    image       = models.ImageField(upload_to="pois/", blank=True, null=True)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    upvotes     = models.PositiveIntegerField(default=0)
    downvotes   = models.PositiveIntegerField(default=0)
    reject_reason = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"POI [{self.poi_type}] @ ({self.latitude},{self.longitude}) — {self.status}"


class POIVote(models.Model):
    """One vote per user per POI — E3 US-022"""
    VOTE_CHOICES = [("up", "Upvote"), ("down", "Downvote")]
    poi       = models.ForeignKey(POI, on_delete=models.CASCADE, related_name="votes")
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vote_type = models.CharField(max_length=4, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("poi", "user")