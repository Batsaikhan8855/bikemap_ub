from django.db import models
from django.conf import settings


class Segment(models.Model):
    """
    Road segment with safety condition — E2 US-010 US-011 US-012 US-013
    Route is NOT stored in DB (browser session only) — E1 US-002
    """
    CONDITION_CHOICES = [
        ("green",  "Green — Bike lane present"),
        ("yellow", "Yellow — Passable, no dedicated lane"),
        ("red",    "Red — Impassable / dangerous"),
    ]
    INFRA_LEVEL_CHOICES = [(i, str(i)) for i in range(1, 7)]

    # Geometry
    start_lat   = models.DecimalField(max_digits=9, decimal_places=6)
    start_lng   = models.DecimalField(max_digits=9, decimal_places=6)
    end_lat     = models.DecimalField(max_digits=9, decimal_places=6)
    end_lng     = models.DecimalField(max_digits=9, decimal_places=6)

    condition   = models.CharField(max_length=10, choices=CONDITION_CHOICES)
    infra_level = models.IntegerField(choices=INFRA_LEVEL_CHOICES, default=4,
                                      help_text="1=separated track … 6=shared road")

    # Road-snapped geometry from OSRM /match — list of {lat, lng} dicts.
    # Null for old segments imported before snap-to-road was added.
    geometry    = models.JSONField(null=True, blank=True)

    # US-013: is_created=True means manually drawn (not from a GPS route)
    is_created  = models.BooleanField(default=False,
                                      help_text="TRUE = created via Create Segment, not from GPS route")

    user        = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True,
                                    related_name="segments")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Segment [{self.condition}] ({self.start_lat},{self.start_lng})"