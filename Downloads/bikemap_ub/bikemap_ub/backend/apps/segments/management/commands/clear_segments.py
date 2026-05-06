"""
Сегментүүдийг bulk устгах команд.

Жишээ:
    # osm_import хэрэглэгчийн бүх сегментийг устгах (бүх 1500+)
    python manage.py clear_segments --user osm_import

    # Сүүлд орсон 100 сегментийг устгах
    python manage.py clear_segments --user osm_import --last 100

    # Бүх strava_import segment-уудыг устгах
    python manage.py clear_segments --user strava_import

    # Условий filter (зөвхөн red condition):
    python manage.py clear_segments --user osm_import --condition red

    # Огт хүртэх (preview only)
    python manage.py clear_segments --user osm_import --dry-run
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.segments.models import Segment


class Command(BaseCommand):
    help = "Bulk-delete segments by user / filter (preview-able with --dry-run)."

    def add_arguments(self, parser):
        parser.add_argument("--user", required=True,
                            help="Username (osm_import, strava_import, manual_import гэх мэт)")
        parser.add_argument("--last", type=int, default=None,
                            help="Зөвхөн сүүлд орсон N сегментийг устгах (default: бүгд)")
        parser.add_argument("--condition", choices=["green", "yellow", "red"],
                            help="Зөвхөн энэ condition-той сегментийг устгах")
        parser.add_argument("--infra-level", type=int, choices=range(1, 7),
                            help="Зөвхөн энэ infra_level-той сегментийг устгах")
        parser.add_argument("--dry-run", action="store_true",
                            help="Тоог зөвхөн харах, устгахгүй")
        parser.add_argument("--yes", action="store_true",
                            help="Баталгаажуулалтгүйгээр устгах")

    @transaction.atomic
    def handle(self, *args, **opts):
        User = get_user_model()
        try:
            user = User.objects.get(username=opts["user"])
        except User.DoesNotExist:
            raise CommandError(f"User '{opts['user']}' not found")

        qs = Segment.objects.filter(user=user)

        if opts["condition"]:
            qs = qs.filter(condition=opts["condition"])
        if opts["infra_level"]:
            qs = qs.filter(infra_level=opts["infra_level"])

        # Сүүлд орсон N-ыг ялгах
        if opts["last"]:
            qs = qs.order_by("-created_at")[:opts["last"]]
            # qs is sliced — need to convert back to a deletable form
            ids = list(qs.values_list("id", flat=True))
            qs = Segment.objects.filter(id__in=ids)

        total = qs.count()
        self.stdout.write(self.style.NOTICE(
            f"Matched {total} segments owned by '{user.username}'"))
        if opts["condition"]:
            self.stdout.write(f"  · condition = {opts['condition']}")
        if opts["infra_level"]:
            self.stdout.write(f"  · infra_level = {opts['infra_level']}")
        if opts["last"]:
            self.stdout.write(f"  · last {opts['last']} (sorted by newest)")

        if total == 0:
            self.stdout.write("Nothing to delete.")
            return

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN — no changes. Run without --dry-run to delete."))
            return

        if not opts["yes"]:
            self.stdout.write(self.style.WARNING(
                f"\nAbout to delete {total} segments. This cannot be undone."))
            confirm = input("Type 'yes' to continue: ").strip().lower()
            if confirm != "yes":
                self.stdout.write("Aborted.")
                return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Deleted {deleted} segments."))
