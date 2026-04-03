from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user — E8 US-070 US-071
    Roles: guest (unauthenticated), cyclist, moderator, admin
    """
    ROLE_CHOICES = [
        ("cyclist",   "Cyclist"),
        ("moderator", "Moderator"),
        ("admin",     "Admin"),
    ]
    email              = models.EmailField(unique=True)
    role               = models.CharField(max_length=20, choices=ROLE_CHOICES, default="cyclist")
    avatar             = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio                = models.TextField(blank=True)
    # Profile stats — E7 US-060
    total_distance_km  = models.FloatField(default=0.0)
    total_pois         = models.PositiveIntegerField(default=0)
    total_segments     = models.PositiveIntegerField(default=0)
    is_banned          = models.BooleanField(default=False)
    created_at         = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} [{self.role}]"

    @property
    def is_admin_or_mod(self):
        return self.role in ("admin", "moderator") or self.is_staff