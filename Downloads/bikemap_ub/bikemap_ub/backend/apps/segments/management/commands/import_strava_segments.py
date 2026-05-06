"""
Strava Segments API-ээс УБ-ын popular cycling segment-уудыг импортлох.

⚠️  Strava-ийн official API-г ашигладаг тул access token шаардлагатай.
   1) https://www.strava.com/settings/api руу ороорой
   2) "Create App" дарж жижиг application үүсгэнэ (нэр: "BikeMap UB", website: localhost)
   3) "Your Access Token" гэсэн талбараас token хуулна
   4) Тэр token-оо командад дамжуулна:
        export STRAVA_ACCESS_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxx
        python manage.py import_strava_segments

Strava /segments/explore нэг дуудалтад **дээд тал нь 10 segment** буцаадаг.
Бид УБ-ын bbox-ыг grid-ээр хуваагаад, нүд тус бүрд дуудалт хийнэ. Жишээ нь
4×4 grid = 16 дуудалт = ~160 segment татна.

API rate limit:
   - Token бүрд 200 хүсэлт / 15 мин, 2000 / өдөр.
   - Бид 16 дуудалт хийдэг тул хангалттай.

Usage:
    python manage.py import_strava_segments
    python manage.py import_strava_segments --grid 6
    python manage.py import_strava_segments --bbox 47.85,106.75,48.00,107.10
    python manage.py import_strava_segments --dry-run
    python manage.py import_strava_segments --clear
"""
import os
import time
import requests
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.segments.models import Segment


STRAVA_EXPLORE_URL = "https://www.strava.com/api/v3/segments/explore"
DEFAULT_BBOX = (47.80, 106.65, 48.05, 107.30)  # (sw_lat, sw_lng, ne_lat, ne_lng)


def decode_polyline(encoded):
    """Decode a Google encoded polyline string into [(lat, lng), ...].

    Strava returns segment geometries in this format. The algorithm reads
    variable-length integers (lat/lng deltas) and reconstructs absolute
    coordinates.  Standard, well-known encoding.
    """
    coords, i, lat, lng = [], 0, 0, 0
    while i < len(encoded):
        for which in ("lat", "lng"):
            shift, result = 0, 0
            while True:
                b = ord(encoded[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if (result & 1) else (result >> 1)
            if which == "lat":
                lat += delta
            else:
                lng += delta
        coords.append((lat / 1e5, lng / 1e5))
    return coords


def grid_cells(sw_lat, sw_lng, ne_lat, ne_lng, n):
    """Yield (sw_lat, sw_lng, ne_lat, ne_lng) tuples for an n×n grid."""
    dlat = (ne_lat - sw_lat) / n
    dlng = (ne_lng - sw_lng) / n
    for i in range(n):
        for j in range(n):
            yield (sw_lat + i * dlat,
                   sw_lng + j * dlng,
                   sw_lat + (i + 1) * dlat,
                   sw_lng + (j + 1) * dlng)


def haversine_m(lat1, lng1, lat2, lng2):
    from math import radians, sin, cos, asin, sqrt
    R = 6_371_000
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * R * asin(sqrt(a))


class Command(BaseCommand):
    help = "Import popular Strava cycling segments for Ulaanbaatar via the Strava API."

    def add_arguments(self, parser):
        parser.add_argument("--token",
                            help="Strava access token. Or set STRAVA_ACCESS_TOKEN env var.")
        parser.add_argument("--bbox",
                            help="sw_lat,sw_lng,ne_lat,ne_lng (default: UB-area)")
        parser.add_argument("--grid", type=int, default=4,
                            help="Grid size (n×n) for tiling the bbox. Default 4.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Fetch + show counts, but don't write to DB.")
        parser.add_argument("--clear", action="store_true",
                            help="Delete previous Strava-imported segments first.")
        parser.add_argument("--user", default="strava_import",
                            help="Username to attribute imports to.")
        parser.add_argument("--min-meters", type=int, default=8)
        parser.add_argument("--default-condition", default="green",
                            choices=["green", "yellow", "red"],
                            help="Strava segment-уудыг ямар condition-оор тэмдэглэх (default green).")
        parser.add_argument("--default-level", type=int, default=2,
                            help="Default infra_level for Strava segments (default 2).")

    @transaction.atomic
    def handle(self, *args, **opts):
        token = opts.get("token") or os.environ.get("STRAVA_ACCESS_TOKEN")
        if not token:
            raise CommandError(
                "Strava access token хэрэгтэй. --token=... эсвэл "
                "STRAVA_ACCESS_TOKEN env var тохируулна уу.\n\n"
                "Token авах: https://www.strava.com/settings/api"
            )

        # Parse bbox
        if opts["bbox"]:
            try:
                sw_lat, sw_lng, ne_lat, ne_lng = (float(x) for x in opts["bbox"].split(","))
            except ValueError:
                raise CommandError("--bbox 'sw_lat,sw_lng,ne_lat,ne_lng' format")
        else:
            sw_lat, sw_lng, ne_lat, ne_lng = DEFAULT_BBOX

        n = max(1, opts["grid"])
        cond = opts["default_condition"]
        lvl  = opts["default_level"]

        self.stdout.write(self.style.NOTICE(
            f"BBox: ({sw_lat},{sw_lng}) → ({ne_lat},{ne_lng})  grid={n}×{n}={n*n} cells"))

        # User
        User = get_user_model()
        sys_user, created = User.objects.get_or_create(
            username=opts["user"],
            defaults={"email": f"{opts['user']}@bikemap.local", "is_active": True},
        )
        if created:
            sys_user.set_unusable_password(); sys_user.save()
            self.stdout.write(f"Created import user '{opts['user']}'")

        if opts["clear"] and not opts["dry_run"]:
            n_del, _ = Segment.objects.filter(user=sys_user).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted {n_del} previously-imported Strava segments"))

        # Fetch segments grid by grid
        headers = {"Authorization": f"Bearer {token}",
                   "User-Agent": "BikeMap-UB-Importer/1.0"}
        seen_ids = set()
        all_segments = []

        cells = list(grid_cells(sw_lat, sw_lng, ne_lat, ne_lng, n))
        self.stdout.write("→ Querying Strava /segments/explore for each cell…")
        for idx, (s, w, ne_la, ne_ln) in enumerate(cells, 1):
            params = {
                "bounds":        f"{s},{w},{ne_la},{ne_ln}",
                "activity_type": "riding",
            }
            try:
                r = requests.get(STRAVA_EXPLORE_URL,
                                 params=params, headers=headers, timeout=30)
            except requests.RequestException as ex:
                self.stdout.write(self.style.WARNING(
                    f"  cell {idx}/{len(cells)} ✗ {ex}"))
                continue

            if r.status_code == 401:
                raise CommandError("401 Unauthorized — Strava access token хүчингүй "
                                   "эсвэл хугацаа дууссан. Шинэ token аваарай.")
            if r.status_code == 429:
                self.stdout.write(self.style.WARNING(
                    "  rate-limit hit, sleeping 60s…"))
                time.sleep(60)
                continue
            if r.status_code != 200:
                self.stdout.write(self.style.WARNING(
                    f"  cell {idx}/{len(cells)} ✗ HTTP {r.status_code}: "
                    f"{r.text[:120]}"))
                continue

            segs = r.json().get("segments", [])
            new_count = 0
            for seg in segs:
                sid = seg.get("id")
                if not sid or sid in seen_ids:
                    continue
                seen_ids.add(sid)
                all_segments.append(seg)
                new_count += 1
            self.stdout.write(
                f"  cell {idx}/{len(cells)} ✓ {len(segs)} returned ({new_count} new)")

            time.sleep(0.5)  # polite pacing

        self.stdout.write(f"\nTotal unique Strava segments fetched: {len(all_segments)}")
        if not all_segments:
            self.stderr.write("No segments returned. Check token / bbox.")
            return

        # Build Segment rows from polylines
        to_create = []
        skipped = 0
        for seg in all_segments:
            poly = seg.get("points") or ""
            if not poly:
                skipped += 1
                continue
            try:
                latlngs = decode_polyline(poly)
            except Exception:
                skipped += 1
                continue
            if len(latlngs) < 2:
                skipped += 1
                continue

            for i in range(len(latlngs) - 1):
                a_lat, a_lng = latlngs[i]
                b_lat, b_lng = latlngs[i + 1]
                if haversine_m(a_lat, a_lng, b_lat, b_lng) < opts["min_meters"]:
                    continue
                to_create.append(Segment(
                    start_lat=round(a_lat, 6), start_lng=round(a_lng, 6),
                    end_lat=round(b_lat, 6),   end_lng=round(b_lng, 6),
                    condition=cond, infra_level=lvl,
                    is_created=False, user=sys_user,
                ))

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Summary"))
        self.stdout.write(f"  Strava segments unique:  {len(all_segments)}")
        self.stdout.write(f"  Decoded → Segment rows:  {len(to_create)}")
        self.stdout.write(f"  Skipped (no polyline):   {skipped}")
        self.stdout.write(f"  Default condition/level: {cond} / {lvl}")

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "\nDRY-RUN — no changes written. Run without --dry-run to commit."))
            return

        Segment.objects.bulk_create(to_create, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Imported {len(to_create)} segments as user '{sys_user.username}'."))
