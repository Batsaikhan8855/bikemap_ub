"""
Audit log — админы үйлдлүүдийг бүртгэдэг (POI approve/reject, user ban,
segment delete гэх мэт)  — NFR05
"""
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("login",           "Login"),
        ("logout",          "Logout"),
        ("poi_approve",     "POI approved"),
        ("poi_reject",      "POI rejected"),
        ("poi_delete",      "POI deleted"),
        ("segment_delete",  "Segment deleted"),
        ("user_ban",        "User banned"),
        ("user_unban",      "User unbanned"),
        ("user_role_change","User role changed"),
        ("password_reset",  "Password reset requested"),
    ]

    actor       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="audit_actions",
    )
    action      = models.CharField(max_length=32, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=32, blank=True,
                                   help_text="e.g. 'POI', 'User', 'Segment'")
    target_id   = models.IntegerField(null=True, blank=True)
    detail      = models.TextField(blank=True,
                                   help_text="Reason / extra context, e.g. ban reason")
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.actor or 'system'} → {self.action}"

    @classmethod
    def log(cls, *, actor, action, target_type="", target_id=None,
            detail="", request=None):
        """Convenience helper used throughout views."""
        ip = None
        if request is not None:
            ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                  or request.META.get("REMOTE_ADDR"))
        return cls.objects.create(
            actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
            action=action, target_type=target_type, target_id=target_id,
            detail=detail, ip_address=ip,
        )
