"""
Сегментийн тоо/харьцаа/давхардлыг харах debug команд.

Жишээ:
    python manage.py segment_stats
    python manage.py segment_stats --duplicates       # дараагийн алхам — давхардал тоолох
    python manage.py segment_stats --remove-duplicates  # давхардлыг устгах
"""
from collections import Counter
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db import transaction

from apps.segments.models import Segment


class Command(BaseCommand):
    help = "Show segment count breakdown and detect duplicates."

    def add_arguments(self, parser):
        parser.add_argument("--duplicates", action="store_true",
                            help="Давхардсан (адилхан координат) сегмент олох")
        parser.add_argument("--remove-duplicates", action="store_true",
                            help="Давхардсан сегментүүдийг устгах (хамгийн эртийг үлдээнэ)")

    def handle(self, *args, **opts):
        total = Segment.objects.count()
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== Total segments in DB: {total} ==="))

        # ── By user ──
        self.stdout.write(self.style.NOTICE("\nBy user:"))
        for row in (Segment.objects
                    .values("user__username")
                    .annotate(n=Count("id"))
                    .order_by("-n")):
            uname = row["user__username"] or "(no-user)"
            self.stdout.write(f"  {uname:25s} {row['n']:>6}")

        # ── By condition ──
        self.stdout.write(self.style.NOTICE("\nBy condition:"))
        for row in (Segment.objects
                    .values("condition")
                    .annotate(n=Count("id"))
                    .order_by("-n")):
            self.stdout.write(f"  {row['condition'] or '(empty)':10s} {row['n']:>6}")

        # ── By infra_level ──
        self.stdout.write(self.style.NOTICE("\nBy infra_level:"))
        for row in (Segment.objects
                    .values("infra_level")
                    .annotate(n=Count("id"))
                    .order_by("infra_level")):
            self.stdout.write(f"  level {row['infra_level']:<2}    {row['n']:>6}")

        # ── By is_created (manual vs imported) ──
        self.stdout.write(self.style.NOTICE("\nBy is_created (manual=True):"))
        for row in (Segment.objects
                    .values("is_created")
                    .annotate(n=Count("id"))
                    .order_by("-n")):
            label = "manual" if row["is_created"] else "imported"
            self.stdout.write(f"  {label:10s} {row['n']:>6}")

        # ── Duplicate detection ──
        if opts["duplicates"] or opts["remove_duplicates"]:
            self.stdout.write(self.style.NOTICE("\nLooking for duplicates "
                              "(same start_lat, start_lng, end_lat, end_lng)…"))
            # Group by coords and count
            dups = (Segment.objects
                    .values("start_lat", "start_lng", "end_lat", "end_lng")
                    .annotate(n=Count("id"))
                    .filter(n__gt=1)
                    .order_by("-n"))
            dup_groups = list(dups)
            extra_total = sum(g["n"] - 1 for g in dup_groups)
            self.stdout.write(
                f"  Дугтуй groups:    {len(dup_groups)}")
            self.stdout.write(
                f"  Илүү (устгавал устах) сегмент: {extra_total}")

            if opts["remove_duplicates"] and extra_total:
                self.stdout.write(self.style.WARNING(
                    f"\n→ Removing {extra_total} duplicate segments "
                    "(keeping the earliest of each group)…"))
                self._remove_duplicates(dup_groups)

    @transaction.atomic
    def _remove_duplicates(self, groups):
        n_removed = 0
        for g in groups:
            qs = (Segment.objects
                  .filter(start_lat=g["start_lat"],
                          start_lng=g["start_lng"],
                          end_lat=g["end_lat"],
                          end_lng=g["end_lng"])
                  .order_by("created_at"))
            keep_id = qs.first().id
            removed, _ = qs.exclude(id=keep_id).delete()
            n_removed += removed
        self.stdout.write(self.style.SUCCESS(
            f"✓ Removed {n_removed} duplicate segments."))
