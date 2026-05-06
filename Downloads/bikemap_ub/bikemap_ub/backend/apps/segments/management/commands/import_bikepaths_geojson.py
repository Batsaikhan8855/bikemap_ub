"""
Хэрэглэгчийн зурсан / гар хийсэн дугуйн замыг GeoJSON-оос импортлох.

Workflow:
    1. https://geojson.io  ороод УБ дээр зам зурна
    2. Бүх line дээр properties нэмнэ:
           "name":        "Энхтайваны өргөн чөлөө",
           "condition":   "green" | "yellow" | "red",
           "infra_level": 1..6
    3. Save as GeoJSON → жнь  data/ub_bikepaths.geojson
    4. Дараах командыг ажиллуулна:

       python manage.py import_bikepaths_geojson data/ub_bikepaths.geojson
       python manage.py import_bikepaths_geojson data/ub_bikepaths.geojson --clear
       python manage.py import_bikepaths_geojson data/ub_bikepaths.geojson --dry-run

GeoJSON format жишээ:
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[106.910, 47.918], [106.920, 47.920], ...]
      },
      "properties": {
        "name": "Энхтайваны өргөн чөлөө дугуйн зам",
        "condition": "yellow",
        "infra_level": 4
      }
    }
  ]
}

Тэмдэглэл: GeoJSON координат нь [lng, lat] эрэмбэтэй (lat биш!).
"""
import json
from pathlib import Path
from math import radians, sin, cos, asin, sqrt

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.segments.models import Segment


def haversine_m(lat1, lng1, lat2, lng2):
    R = 6_371_000
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * R * asin(sqrt(a))


VALID_CONDITIONS = {"green", "yellow", "red"}
VALID_LEVELS = set(range(1, 7))


class Command(BaseCommand):
    help = "Import hand-drawn bike paths from a GeoJSON file as Segment rows."

    def add_arguments(self, parser):
        parser.add_argument("path",
                            help="Path to a GeoJSON file (FeatureCollection of LineStrings)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show counts but don't write to DB")
        parser.add_argument("--clear", action="store_true",
                            help="Delete previous segments owned by --user before importing")
        parser.add_argument("--user", default="manual_import",
                            help="Username to attribute imports to (created if missing)")
        parser.add_argument("--min-meters", type=int, default=8,
                            help="Skip segments shorter than this (default 8 m)")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["path"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as ex:
            raise CommandError(f"Invalid JSON: {ex}")

        if data.get("type") != "FeatureCollection":
            raise CommandError("Top-level type must be FeatureCollection")
        features = data.get("features", [])
        if not features:
            raise CommandError("No features found in file")

        # ── User ──────────────────────────────────────────────────────
        User = get_user_model()
        sys_user, created = User.objects.get_or_create(
            username=opts["user"],
            defaults={
                "email": f"{opts['user']}@bikemap.local",
                "is_active": True,
            },
        )
        if created:
            sys_user.set_unusable_password()
            sys_user.save()
            self.stdout.write(f"Created import user '{opts['user']}'")

        # ── Optional clean-up ─────────────────────────────────────────
        if opts["clear"] and not opts["dry_run"]:
            n_del, _ = Segment.objects.filter(user=sys_user).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted {n_del} previously-imported segments owned by {sys_user.username}"))

        # ── Validate + collect ────────────────────────────────────────
        to_create = []
        per_level = {i: 0 for i in range(1, 7)}
        per_cond  = {"green": 0, "yellow": 0, "red": 0}
        skipped_short, skipped_invalid = 0, 0

        for idx, feat in enumerate(features, 1):
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}

            if geom.get("type") != "LineString":
                self.stdout.write(self.style.WARNING(
                    f"  feature #{idx} ignored — geometry must be LineString"))
                skipped_invalid += 1
                continue

            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                skipped_invalid += 1
                continue

            cond = props.get("condition", "yellow")
            try:
                lvl = int(props.get("infra_level", 4))
            except (TypeError, ValueError):
                lvl = 4

            if cond not in VALID_CONDITIONS:
                self.stdout.write(self.style.WARNING(
                    f"  feature #{idx}: condition='{cond}' invalid, defaulting to 'yellow'"))
                cond = "yellow"
            if lvl not in VALID_LEVELS:
                self.stdout.write(self.style.WARNING(
                    f"  feature #{idx}: infra_level={lvl} invalid, defaulting to 4"))
                lvl = 4

            # Walk the line and create per-pair segments
            for i in range(len(coords) - 1):
                a_lng, a_lat = coords[i][:2]
                b_lng, b_lat = coords[i + 1][:2]
                if haversine_m(a_lat, a_lng, b_lat, b_lng) < opts["min_meters"]:
                    skipped_short += 1
                    continue
                to_create.append(Segment(
                    start_lat=round(a_lat, 6), start_lng=round(a_lng, 6),
                    end_lat=round(b_lat, 6),   end_lng=round(b_lng, 6),
                    condition=cond, infra_level=lvl,
                    is_created=True, user=sys_user,
                ))
                per_level[lvl] += 1
                per_cond[cond] += 1

        # ── Report ────────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Summary"))
        self.stdout.write(f"  Features in file:      {len(features)}")
        self.stdout.write(f"  Skipped (invalid):     {skipped_invalid}")
        self.stdout.write(f"  Skipped (too short):   {skipped_short}")
        self.stdout.write(f"  Segments to import:    {len(to_create)}")
        self.stdout.write(f"  Per condition:         {per_cond}")
        self.stdout.write(f"  Per infra level:       {per_level}")

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN — no changes written. Run without --dry-run to commit."))
            return

        Segment.objects.bulk_create(to_create, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Imported {len(to_create)} segments as user '{sys_user.username}'."))
