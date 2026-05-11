import hashlib
from django.db import models


class CrowdAggregation(models.Model):
    """
    Aggregated crowd vote per map cell — E4 US-030 US-031
    segment_hash = hash(round(start_lat,3), round(start_lng,3),
                        round(end_lat,3),   round(end_lng,3))
    """
    DOMINANT_CHOICES = [
        ("green",  "Green"),
        ("yellow", "Yellow"),
        ("red",    "Red"),
        ("none",   "No data"),
    ]
    segment_hash  = models.CharField(max_length=64, unique=True, db_index=True)
    # Raw vote counts
    green_votes   = models.PositiveIntegerField(default=0)
    yellow_votes  = models.PositiveIntegerField(default=0)
    red_votes     = models.PositiveIntegerField(default=0)
    # Computed dominant
    dominant      = models.CharField(max_length=10, choices=DOMINANT_CHOICES, default="none")
    # Bounding box (for map queries)
    start_lat     = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    start_lng     = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    end_lat       = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    end_lng       = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Agg [{self.segment_hash[:8]}] → {self.dominant}"

    @staticmethod
    def make_hash(start_lat, start_lng, end_lat, end_lng):
        key = (
            f"{round(float(start_lat),3)},{round(float(start_lng),3)},"
            f"{round(float(end_lat),3)},{round(float(end_lng),3)}"
        )
        return hashlib.sha256(key.encode()).hexdigest()[:64]

    def compute_dominant(self):
        """
        US-031 algorithm: most votes wins.
        Tie-breaker: safety-first — red > yellow > green.
        Example: green=10, yellow=3, red=6 → green
        Example: green=5,  yellow=5, red=0  → yellow (safer than green tie)
        """
        votes = {
            "green":  self.green_votes,
            "yellow": self.yellow_votes,
            "red":    self.red_votes,
        }
        total = sum(votes.values())
        if total == 0:
            self.dominant = "none"
        else:
            max_votes = max(votes.values())
            # Safety-first tie-break: among tied conditions pick the most cautious
            for condition in ("red", "yellow", "green"):
                if votes[condition] == max_votes:
                    self.dominant = condition
                    break
        return self.dominant