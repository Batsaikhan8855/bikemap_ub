from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('action', models.CharField(choices=[
                    ('login', 'Login'), ('logout', 'Logout'),
                    ('poi_approve', 'POI approved'), ('poi_reject', 'POI rejected'),
                    ('poi_delete', 'POI deleted'), ('segment_delete', 'Segment deleted'),
                    ('user_ban', 'User banned'), ('user_unban', 'User unbanned'),
                    ('user_role_change', 'User role changed'),
                    ('password_reset', 'Password reset requested'),
                ], max_length=32)),
                ('target_type', models.CharField(blank=True, max_length=32)),
                ('target_id', models.IntegerField(blank=True, null=True)),
                ('detail', models.TextField(blank=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('actor', models.ForeignKey(blank=True, null=True,
                                            on_delete=django.db.models.deletion.SET_NULL,
                                            related_name='audit_actions',
                                            to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
