"""
Django management command — Import bike infrastructure for Ulaanbaatar
from OpenStreetMap (Overpass API) and bulk-create Segment rows.

Usage:
    python manage.py import_osm_bikepaths
    python manage.py import_osm_bikepaths --bbox 47.85,106.75,48.00,107.10
    python manage.py import_osm_bikepaths --dry-run
    python manage.py import_osm_bikepaths --clear   # эхлээд хуучин OSM-segment-үүдийг устгана

Тэмдэглэл:
* Strava нь олон нийтийн route-ыг GPX-ээр өгдөггүй (ToS) тул бид OSM ашиглана.
* Overpass API нь хэрэглээний хязгаартай — олон удаа дуудахаас зайлсхий.
* Tag-аас condition + infra_level-ийг classify() функц нь автоматаар дүгнэнэ.
"""
import time
import requests
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.segments.models import Segment


# Overpass нь олон нийтийн mirror-той — нэг нь хариу өгөхгүй бол дараагийнхыг
# туршина. Эхэнд илүү найдвартай mirror-ыг тавив.
OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
HTTP_HEADERS = {
    # Олон Overpass mirror нь User-Agent байхгүй request-ийг 403/406-аар
    # буцаадаг. Эх сурвалжаа тодорхойлсон header дамжуулна.
    "User-Agent": "BikeMap-UB-Importer/1.0 (educational; +https://bikemap.local)",
    "Accept": "application/json",
}

# Ulaanbaatar бараг бүтэн хотыг бүрхэх bounding box: (south, west, north, east)
DEFAULT_BBOX = (47.80, 106.65, 48.05, 107.30)

# Bike-related ways: highway=cycleway, anything tagged cycleway=*,
# bicycle=designated/yes, plus pedestrian/footway with bicycle access.
OVERPASS_QUERY = """
[out:json][timeout:90];
(
  way["highway"="cycleway"]({s},{w},{n},{e});
  way["cycleway"]({s},{w},{n},{e});
  way["cycleway:left"]({s},{w},{n},{e});
  way["cycleway:right"]({s},{w},{n},{e});
  way["cycleway:both"]({s},{w},{n},{e});
  way["bicycle"="designated"]({s},{w},{n},{e});
  way["highway"="path"]["bicycle"="yes"]({s},{w},{n},{e});
);
(._;>;);
out body;
"""


def classify(tags):
    """Return (condition, infra_level) for an OSM way's tag dict.

    OSM convention reminder:
      - highway=cycleway = a way **dedicated to cyclists** (no cars)
      - cycleway=track on a road = bike track separated by a barrier
      - cycleway=lane on a road = painted lane only
      - bicycle=designated = path designed for bikes
      - bicycle=yes = bikes allowed but not the primary use

    Project mapping:
        highway=cycleway (segregated=no / foot=yes/designated)
                                          → 2 (mixed)              green
        highway=cycleway (default)        → 1 (isolated cycleway)  green
        highway=path  + bicycle=designated→ 2 (mixed)              green
        cycleway[:*]=track                → 3 (protected lane)     green
        cycleway[:*]=lane (and variants)  → 4 (painted lane)       yellow
        highway=path/footway + bicycle=yes→ 5 (sidewalk-ish)       yellow
        bicycle=yes (any other)           → 6 (shared with cars)   yellow
    """
    h    = tags.get("highway", "")
    cw   = tags.get("cycleway", "")
    cwl  = tags.get("cycleway:left", "")
    cwr  = tags.get("cycleway:right", "")
    cwb  = tags.get("cycleway:both", "")
    seg  = tags.get("segregated", "")
    foot = tags.get("foot", "")
    cw_any = cw or cwb or cwl or cwr
    bic  = tags.get("bicycle", "")

    # Pure cycleway = dedicated bike infrastructure
    if h == "cycleway":
        # Mixed with pedestrians?
        if seg == "no" or foot in ("yes", "designated"):
            return ("green", 2)
        # Default: treat as isolated bike path (most accurate per OSM)
        return ("green", 1)

    # Multi-use path designed for bikes
    if h == "path" and bic == "designated":
        return ("green", 2)
    if h == "path" and bic == "yes":
        return ("yellow", 5)

    # Bike track on a road — physically separated
    if cw_any == "track":
        return ("green", 3)

    # Painted lanes (any direction or shared with bus)
    if cw_any in ("lane", "opposite_lane", "shared_lane",
                  "share_busway", "opposite_share_busway"):
        return ("yellow", 4)

    # Shared with pedestrians (sidewalk path)
    if h in ("footway", "pedestrian") and bic in ("yes", "permissive", "designated"):
        return ("yellow", 5)

    # Designated bike facility without other context
    if bic == "designated":
        return ("green", 2)

    # Bikes allowed on a regular road
    if bic in ("yes", "permissive"):
        return ("yellow", 6)

    # Fallback (shouldn't really occur given the query filters)
    return ("yellow", 4)


def haversine_m(lat1, lng1, lat2, lng2):
    from math import radians, sin, cos, asin, sqrt
    R = 6_371_000
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * R * asin(sqrt(a))


class Command(BaseCommand):
    help = "Import OpenStreetMap bicycle infrastructure for Ulaanbaatar as Segments."

    def add_arguments(self, parser):
        parser.add_argument("--bbox",
                            help="south,west,north,east (default: UB-area)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Show counts but don't write to DB")
        parser.add_argument("--clear", action="store_true",
                            help="Delete previous OSM-imported segments first")
        parser.add_argument("--min-meters", type=int, default=8,
                            help="Skip segment if shorter than this (default 8)")
        parser.add_argument("--user", default="osm_import",
                            help="Username to attribute imports to (created if missing)")

    @transaction.atomic
    def handle(self, *args, **opts):
        # ── Parse bbox ────────────────────────────────────────────────
        if opts["bbox"]:
            try:
                s, w, n, e = (float(x) for x in opts["bbox"].split(","))
            except ValueError:
                self.stderr.write("--bbox must be 'south,west,north,east'")
                return
        else:
            s, w, n, e = DEFAULT_BBOX

        self.stdout.write(self.style.NOTICE(
            f"BBox: south={s} west={w} north={n} east={e}"))

        # ── User to attribute imports to ──────────────────────────────
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
            # Try to mark as admin if such role/flag exists
            for attr in ("role", "is_staff"):
                if hasattr(sys_user, attr):
                    setattr(sys_user, attr,
                            "admin" if attr == "role" else True)
            sys_user.save()
            self.stdout.write(f"Created import user '{opts['user']}'")

        # ── Optional clean-up ─────────────────────────────────────────
        if opts["clear"] and not opts["dry_run"]:
            n_del, _ = Segment.objects.filter(user=sys_user).delete()
            self.stdout.write(self.style.WARNING(
                f"Deleted {n_del} previously-imported OSM segments"))

        # ── Query Overpass (try mirrors until one works) ───────────────
        query = OVERPASS_QUERY.format(s=s, w=w, n=n, e=e)
        self.stdout.write("→ Querying Overpass API (~10–30s)…")

        data, last_err = None, None
        for url in OVERPASS_MIRRORS:
            t0 = time.time()
            try:
                r = requests.post(
                    url,
                    data={"data": query},
                    headers=HTTP_HEADERS,
                    timeout=120,
                )
                r.raise_for_status()
                data = r.json()
                self.stdout.write(
                    f"  ✓ {url}  ({time.time()-t0:.1f}s, "
                    f"{len(data.get('elements', []))} elements)"
                )
                break
            except requests.RequestException as ex:
                last_err = ex
                self.stdout.write(self.style.WARNING(
                    f"  ✗ {url}  ({type(ex).__name__}: {ex})"))
                continue

        if data is None:
            self.stderr.write(self.style.ERROR(
                f"All Overpass mirrors failed. Last error: {last_err}"))
            return

        # ── Build node lookup + collect ways ──────────────────────────
        nodes, ways = {}, []
        for el in data.get("elements", []):
            if el["type"] == "node":
                nodes[el["id"]] = (el["lat"], el["lon"])
            elif el["type"] == "way":
                ways.append(el)

        if not ways:
            self.stderr.write("No bike-related ways found in this bbox.")
            return

        self.stdout.write(f"  Bike-related ways: {len(ways)}")

        # ── Build segment objects ─────────────────────────────────────
        # Шинэ хувилбар: OSM way бүрд НЭГ Segment row үүсгэнэ. Way-ийн бүх
        # цэгийг `geometry` JSON field дотор хадгалж frontend-д smooth
        # полилайн (зам мэт хэлбэрээр) зурагдах боломжтой болгоно.
        # Хуучин 11 жижиг 2-цэгт сегмент → 1 бүтэн зам. Үр дүнд visual
        # тал нь огт өөр болж жинхэнэ дугуйн зам шиг харагдана.
        to_create = []
        skipped_short = 0
        skipped_invalid = 0
        per_level = {i: 0 for i in range(1, 7)}
        per_cond  = {"green": 0, "yellow": 0, "red": 0}

        for way in ways:
            tags = way.get("tags", {})
            cond, lvl = classify(tags)
            way_nodes = way.get("nodes", [])

            # Way-ийн бүх node-ыг (lat, lng)-ээр цуглуулна
            geom = []
            for nid in way_nodes:
                pt = nodes.get(nid)
                if pt:
                    geom.append({"lat": round(pt[0], 6), "lng": round(pt[1], 6)})

            if len(geom) < 2:
                skipped_invalid += 1
                continue

            # Way-ийн нийт уртыг тооцох (хэт богино way-ыг алгасах)
            total_m = sum(
                haversine_m(geom[i]["lat"], geom[i]["lng"],
                            geom[i + 1]["lat"], geom[i + 1]["lng"])
                for i in range(len(geom) - 1)
            )
            if total_m < opts["min_meters"]:
                skipped_short += 1
                continue

            to_create.append(Segment(
                start_lat=geom[0]["lat"],  start_lng=geom[0]["lng"],
                end_lat=geom[-1]["lat"],   end_lng=geom[-1]["lng"],
                geometry=geom,                        # бүх цэг JSON-оор
                condition=cond, infra_level=lvl,
                is_created=False, user=sys_user,
            ))
            per_level[lvl] += 1
            per_cond[cond]  += 1

        # ── Report ────────────────────────────────────────────────────
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Summary"))
        self.stdout.write(f"  Segments to import:   {len(to_create)}")
        self.stdout.write(f"  Skipped (invalid):    {skipped_invalid}")
        self.stdout.write(f"  Skipped (too short):  {skipped_short}")
        self.stdout.write(f"  Per condition:        {per_cond}")
        self.stdout.write(f"  Per infra level:      {per_level}")

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN — no changes written. Run without --dry-run to commit."))
            return

        # ── Bulk create ───────────────────────────────────────────────
        Segment.objects.bulk_create(to_create, batch_size=2000)
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ Imported {len(to_create)} segments as user '{sys_user.username}'."))
