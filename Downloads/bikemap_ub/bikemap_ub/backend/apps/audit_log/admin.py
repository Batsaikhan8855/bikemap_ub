from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ("created_at", "actor", "action", "target_type",
                     "target_id", "ip_address")
    list_filter   = ("action", "target_type")
    search_fields = ("actor__email", "detail", "ip_address")
    readonly_fields = ("actor", "action", "target_type", "target_id",
                       "detail", "ip_address", "created_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):       # Audit log зөвхөн систем бүртгэдэг
        return False

    def has_change_permission(self, request, obj=None):
        return False
