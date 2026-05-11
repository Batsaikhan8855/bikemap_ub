"""
Routes app — E1 GPS tracking + GPX export/import + E5 Smart Route
NOTE: Routes are NOT stored in DB per US-002.
      Only the GPX export (US-003), GPX import, and smart route (US-040 US-041)
      endpoints live here.
"""
import io, datetime, math
import xml.etree.ElementTree as ET
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.http import HttpResponse
from django.conf import settings
from django.db.models import Q
try:
    import requests as req_lib
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
import gpxpy
from apps.accounts.permissions import IsCyclistOrAbove
from apps.pois.models import POI
from apps.aggregation.models import CrowdAggregation
from apps.segments.models import Segment
from apps.aggregation.tasks import update_aggregation


def _haversine_m(lat1, lng1, lat2, lng2):
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def _segment_match_points(seg):
    """Сегментийг route-той тулгахад ашиглах sample цэгүүдийн жагсаалт.

    OSM-аас орсон сегмент бүрд `geometry` field-д бүх node хадгалагдсан
    (заримдаа 50+ цэг). Эхэн ба төгсгөлийн цэгийг хайх нь хангалтгүй —
    route нь сегментийн ДУНДУУР яваад байж болно. Үүнийг засахын тулд
    geometry-ийн хэд хэдэн цэг (~8 хэсгээр sample) буцаана.

    Гар хийсэн (geometry-гүй) сегмент бол start + end л буцаана.
    """
    pts = []
    geom = getattr(seg, "geometry", None)
    if geom and isinstance(geom, list) and len(geom) >= 2:
        # Long OSM way — sample every Nth node
        step = max(1, len(geom) // 8)
        for p in geom[::step]:
            try:
                pts.append((float(p["lat"]), float(p["lng"])))
            except (KeyError, TypeError, ValueError):
                continue
        # Эцсийн цэгийг үргэлж нэмнэ
        try:
            last = geom[-1]
            pts.append((float(last["lat"]), float(last["lng"])))
        except (KeyError, TypeError, ValueError):
            pass
    if not pts:
        # Manual segment (geometry-гүй) — start + end
        try:
            pts = [(float(seg.start_lat), float(seg.start_lng)),
                   (float(seg.end_lat),   float(seg.end_lng))]
        except Exception:
            return []
    return pts


def _simplify_points(raw, target=120):
    """Distance-based simplification: keep a point only if it is >= min_dist
    metres from the previous kept point.  Adaptive min_dist = total / target."""
    if len(raw) <= target:
        return raw
    # Estimate total distance
    total = sum(_haversine_m(raw[i][0], raw[i][1], raw[i+1][0], raw[i+1][1])
                for i in range(len(raw) - 1))
    min_dist = max(15.0, total / target)
    result = [raw[0]]
    for pt in raw[1:]:
        prev = result[-1]
        if _haversine_m(prev[0], prev[1], pt[0], pt[1]) >= min_dist:
            result.append(pt)
    if result[-1] != raw[-1]:
        result.append(raw[-1])
    return result


class GPXImportView(APIView):
    """
    POST /api/routes/gpx-import/
    Accepts a .gpx file upload, parses it with gpxpy, simplifies the track,
    and returns the simplified point list for the frontend to preview and save.
    """
    permission_classes = [IsCyclistOrAbove]

    def post(self, request):
        gpx_file = request.FILES.get("gpx_file")
        if not gpx_file:
            return Response({"error": "gpx_file required"}, status=400)
        if not gpx_file.name.lower().endswith(".gpx"):
            return Response({"error": "Only .gpx files are accepted"}, status=400)
        if gpx_file.size > 10 * 1024 * 1024:
            return Response({"error": "File too large (max 10 MB)"}, status=400)

        try:
            gpx = gpxpy.parse(gpx_file)
        except Exception as e:
            return Response({"error": f"Invalid GPX file: {e}"}, status=400)

        raw = []
        for track in gpx.tracks:
            for seg in track.segments:
                for pt in seg.points:
                    raw.append((round(float(pt.latitude), 6),
                                round(float(pt.longitude), 6)))
        if not raw:
            for rte in gpx.routes:
                for pt in rte.points:
                    raw.append((round(float(pt.latitude), 6),
                                round(float(pt.longitude), 6)))

        if len(raw) < 2:
            return Response({"error": "GPX must contain at least 2 track points"}, status=400)

        simplified = _simplify_points(raw, target=120)
        return Response({
            "points":           [{"lat": p[0], "lng": p[1]} for p in simplified],
            "total_original":   len(raw),
            "total_simplified": len(simplified),
            "segment_count":    len(simplified) - 1,
        })


class GPXImportSaveView(APIView):
    """
    POST /api/routes/gpx-import/save/

    GPX-аас preview хийсэн point-уудыг **хэсэг хэсгээр** condition / infra_level
    тэмдэглэж олон Segment-ээр bulk хадгална.

    Body:
    {
      "splits": [
        {
          "points":      [{"lat": 47.918, "lng": 106.917}, ...],
          "condition":   "green",     # green | yellow | red
          "infra_level": 1            # 1..6
        },
        {
          "points":      [{"lat": 47.920, "lng": 106.920}, ...],
          "condition":   "yellow",
          "infra_level": 4
        },
        ...
      ]
    }

    Хариу:  { "created_count": N, "segment_ids": [...] }
    """
    permission_classes = [IsCyclistOrAbove]

    def post(self, request):
        splits = request.data.get("splits") or []
        if not isinstance(splits, list) or not splits:
            return Response({"error": "splits[] required"}, status=400)

        valid_cond  = {"green", "yellow", "red"}
        valid_level = {1, 2, 3, 4, 5, 6}
        created_segments = []

        for i, split in enumerate(splits):
            pts   = split.get("points") or []
            cond  = split.get("condition")
            level = int(split.get("infra_level") or 0)

            if cond not in valid_cond:
                return Response({"error":
                    f"split[{i}].condition must be one of {sorted(valid_cond)}"},
                    status=400)
            if level not in valid_level:
                return Response({"error":
                    f"split[{i}].infra_level must be 1..6"}, status=400)
            if len(pts) < 2:
                return Response({"error":
                    f"split[{i}] must have ≥2 points"}, status=400)

            # Цэг бүрийн дараалал бүрд нэг Segment үүсгэнэ
            for j in range(len(pts) - 1):
                p1, p2 = pts[j], pts[j + 1]
                seg = Segment.objects.create(
                    start_lat=round(float(p1["lat"]), 6),
                    start_lng=round(float(p1["lng"]), 6),
                    end_lat=round(float(p2["lat"]),   6),
                    end_lng=round(float(p2["lng"]),   6),
                    condition=cond,
                    infra_level=level,
                    user=request.user,
                    is_created=False,  # GPX import-аас үүссэн
                )
                created_segments.append(seg)

        # Crowd aggregation бүгдэд нь нэг удаа дуудлага хийнэ
        for seg in created_segments:
            try:
                update_aggregation(seg)
            except Exception:
                pass

        # User stat
        user = request.user
        user.total_segments += len(created_segments)
        user.save(update_fields=["total_segments"])

        return Response({
            "created_count": len(created_segments),
            "segment_ids":   [s.id for s in created_segments],
        }, status=201)


class GPXExportView(APIView):
    """
    POST /api/routes/gpx-export/
    Body: { "coordinates": [{lat, lng, timestamp}, ...], "distance_km": float }
    Returns a .gpx file download — US-003
    """
    permission_classes = [IsCyclistOrAbove]

    def post(self, request):
        coords = request.data.get("coordinates", [])
        if not coords:
            return Response({"error": "No coordinates provided"}, status=400)

        # Build GPX XML
        gpx = ET.Element("gpx", {
            "version": "1.1",
            "creator": "BikeMap UB",
            "xmlns": "http://www.topografix.com/GPX/1/1",
        })
        metadata = ET.SubElement(gpx, "metadata")
        ET.SubElement(metadata, "name").text = f"BikeMap UB Route {datetime.date.today()}"
        ET.SubElement(metadata, "time").text = datetime.datetime.utcnow().isoformat() + "Z"

        trk  = ET.SubElement(gpx, "trk")
        ET.SubElement(trk, "name").text = "Bicycle Route"
        trkseg = ET.SubElement(trk, "trkseg")

        for pt in coords:
            trkpt = ET.SubElement(trkseg, "trkpt", {
                "lat": str(pt.get("lat", 0)),
                "lon": str(pt.get("lng", 0)),
            })
            if pt.get("timestamp"):
                ET.SubElement(trkpt, "time").text = pt["timestamp"]

        tree = ET.ElementTree(gpx)
        buf  = io.BytesIO()
        tree.write(buf, encoding="utf-8", xml_declaration=True)

        response = HttpResponse(buf.getvalue(), content_type="application/gpx+xml")
        response["Content-Disposition"] = (
            f"attachment; filename=bikemap_route_{datetime.date.today()}.gpx"
        )
        return response


class SmartRouteView(APIView):
    """
    POST /api/routes/smart/
    Body: {
      "start": {"lat": float, "lng": float},
      "end":   {"lat": float, "lng": float},
      "mode":  "safe" | "fast"   (US-041)
    }

    "fast" mode  → OSRM-ийн хамгийн богино зам шууд буцаана.
    "safe" mode  → OSRM-аас 3 хүртэл alternative зам авч, хэрэглэгчдийн
                   оруулсан Segment (infra_level + condition) болон
                   аюулын POI-той давхцалаар нь score тооцон, аюулгүй
                   зэрэглэлтэй хамгийн их оноотойг буцаана.

    Score = sum(safety_per_overlapping_segment) - hazard_penalty
        - infra_level 1 (тусгаарлагдсан) =  +6
        - infra_level 2                  =  +5
        - infra_level 3                  =  +4
        - infra_level 4                  =  +2
        - infra_level 5                  =  +0
        - infra_level 6 (нийтийн машинт.) =  -1
        - condition green                =  +2
        - condition yellow               =   0
        - condition red                  =  -4
        - hazard POI ойролцоо            =  -5
    """
    permission_classes = [permissions.AllowAny]

    # ── Scoring weights ────────────────────────────────────────────
    # 6 түвшний дэд бүтцийн зэрэглэлийг бүгдийг харгалзана.
    # User-н оруулсан Segment-д нийцэх маршрутыг илүү давамгайлуулна.
    LEVEL_W   = {1: 8, 2: 6, 3: 4, 4: 2, 5: 0, 6: -2}   # 1=хамгийн аюулгүй
    COND_W    = {"green": 4, "yellow": 0, "red": -6}    # green урамшуулна
    HAZARD_W  = -5
    USER_GREEN_BONUS = 2  # user-н green Segment-д нэмэлт onoo

    def post(self, request):
        start = request.data.get("start")
        end   = request.data.get("end")
        mode  = request.data.get("mode", "safe")

        if not start or not end:
            return Response({"error": "start and end required"}, status=400)

        # ── 1. Fetch route(s) from OSRM ────────────────────────────
        # safe mode-д alternatives асаана. fast mode-д шортхэн нэг л.
        alt_flag = "true" if mode == "safe" else "false"
        osrm_url = (
            f"{settings.OSRM_BASE_URL}/route/v1/cycling/"
            f"{start['lng']},{start['lat']};{end['lng']},{end['lat']}"
            f"?overview=full&geometries=geojson&steps=true"
            f"&alternatives={alt_flag}"
        )
        osrm_data = None
        if REQUESTS_AVAILABLE:
            try:
                r = req_lib.get(osrm_url, timeout=5)
                if r.status_code == 200:
                    osrm_data = r.json()
            except Exception:
                pass

        # ── 2. Fallback (OSRM unavailable) ─────────────────────────
        if not osrm_data or not osrm_data.get("routes"):
            route_coords = [
                [start["lng"], start["lat"]],
                [end["lng"],   end["lat"]],
            ]
            distance_m = _haversine_m(start["lat"], start["lng"],
                                       end["lat"], end["lng"])
            duration_s = int((distance_m / 1000) / 15 * 3600) if distance_m else 0
            return Response({
                "mode":           mode,
                "routing_status": "fallback",
                "distance_m":     distance_m,
                "duration_s":     duration_s,
                "coordinates":    route_coords,
                "segments":       [],
                "hazards":        [],
                "score":          None,
                "alternatives_count": 0,
            })

        # ── 3. Score each candidate (only for safe mode) ───────────
        candidates = osrm_data["routes"]
        if mode == "safe" and len(candidates) > 1:
            scored = [(self._score_route(r["geometry"]["coordinates"]), r)
                      for r in candidates]
            scored.sort(key=lambda x: x[0], reverse=True)
            best_score, best = scored[0]
        else:
            best = candidates[0]
            best_score = (self._score_route(best["geometry"]["coordinates"])
                          if mode == "safe" else None)

        route_coords = best["geometry"]["coordinates"]
        distance_m   = best["distance"]
        duration_s   = best["duration"]

        # ── 4. Annotate route edge-бүрийг хамгийн ойрын хэрэглэгчийн
        # Segment-ийн infra_level + condition-аар тэмдэглэх ──────────
        # OSM-ийн урт way-ыг (бүтэн geometry-той) таних учир: сегмент
        # бүрийн geometry-аас sample point-уудыг гаргаж memory-д хайна.
        # Filter: сегментийн START эсвэл END цэгийн аль нэг нь route-ийн
        # bbox дотор байвал хамтад нь авна.
        lats = [c[1] for c in route_coords]
        lngs = [c[0] for c in route_coords]
        lat_lo, lat_hi = min(lats) - 0.005, max(lats) + 0.005
        lng_lo, lng_hi = min(lngs) - 0.005, max(lngs) + 0.005

        nearby_segs_qs = Segment.objects.filter(
            Q(start_lat__range=(lat_lo, lat_hi),
              start_lng__range=(lng_lo, lng_hi)) |
            Q(end_lat__range=(lat_lo, lat_hi),
              end_lng__range=(lng_lo, lng_hi))
        ).only("start_lat", "start_lng", "end_lat", "end_lng",
               "geometry", "infra_level", "condition")[:5000]

        # Сегмент → sample point жагсаалт (нэг сегмент олон цэгтэй)
        # Зөвхөн (lat, lng, infra_level, condition) tuple-аар хадгална.
        seg_points = []
        for s in nearby_segs_qs:
            for plat, plng in _segment_match_points(s):
                seg_points.append((plat, plng, s.infra_level, s.condition))

        # Crowd aggregation-уудыг бас bbox-оор татаад memory-д лookup
        nearby_aggs = list(CrowdAggregation.objects.filter(
            start_lat__range=(min(lats) - 0.002, max(lats) + 0.002),
            start_lng__range=(min(lngs) - 0.002, max(lngs) + 0.002),
        ).only("start_lat", "start_lng", "dominant"))
        agg_index = [(float(a.start_lat), float(a.start_lng), a.dominant)
                     for a in nearby_aggs]

        segments_colour = []
        for i in range(len(route_coords) - 1):
            lng1, lat1 = route_coords[i]
            lng2, lat2 = route_coords[i + 1]
            mid_lat = (lat1 + lat2) / 2
            mid_lng = (lng1 + lng2) / 2

            # Хамгийн ойрын user segment-ийн sample point (~80 м radius)
            best, best_d = None, 0.0008
            for plat, plng, lvl, cnd in seg_points:
                d = abs(plat - mid_lat) + abs(plng - mid_lng)
                if d < best_d:
                    best_d = d
                    best = (lvl, cnd)

            # Crowd aggregation dominant colour (нэмэлт)
            agg_best, agg_d = "unknown", 0.002
            for al, an, dom in agg_index:
                d = abs(al - mid_lat) + abs(an - mid_lng)
                if d < agg_d:
                    agg_d = d
                    agg_best = dom

            if best:
                lvl, cnd = best
                segments_colour.append({
                    "from":        [lng1, lat1],
                    "to":          [lng2, lat2],
                    "infra_level": lvl,
                    "condition":   cnd,
                    "colour":      agg_best,
                    "matched":     True,
                })
            else:
                segments_colour.append({
                    "from":        [lng1, lat1],
                    "to":          [lng2, lat2],
                    "infra_level": None,
                    "condition":   "unknown",
                    "colour":      agg_best,
                    "matched":     False,
                })

        # ── 5. Nearby POI hazards on chosen route ──────────────────
        danger_types = ["danger", "road_damage", "no_bike_lane"]
        hazards, seen = [], set()
        for lng, lat in route_coords:
            nearby = POI.objects.filter(
                status="approved",
                poi_type__in=danger_types,
                latitude__range=(lat - 0.0005, lat + 0.0005),
                longitude__range=(lng - 0.0005, lng + 0.0005),
            )
            for p in nearby:
                if p.id in seen:
                    continue
                seen.add(p.id)
                hazards.append({
                    "id": p.id, "poi_type": p.poi_type,
                    "lat": float(p.latitude), "lng": float(p.longitude),
                })

        return Response({
            "mode":               mode,
            "routing_status":     "osrm",
            "distance_m":         distance_m,
            "duration_s":         duration_s,
            "coordinates":        route_coords,
            "segments":           segments_colour,
            "hazards":            hazards,
            "score":              best_score,
            "alternatives_count": len(candidates),
        })

    # ── Safety scoring ────────────────────────────────────────────────
    def _score_route(self, route_coords):
        """Score a candidate route based on overlap with crowd-sourced
        Segments and proximity to hazard POIs.

        Higher score = safer. Segments are detected via spatial bbox query
        for performance. Each segment counts at most once per route.
        """
        if not route_coords or len(route_coords) < 2:
            return 0

        lats = [c[1] for c in route_coords]
        lngs = [c[0] for c in route_coords]
        # +-0.001 deg ≈ 100m padding
        lat_lo, lat_hi = min(lats) - 0.005, max(lats) + 0.005
        lng_lo, lng_hi = min(lngs) - 0.005, max(lngs) + 0.005

        # ─ Pull all candidate segments — segment-ийн START эсвэл END
        # цэгийн аль нэг нь route-ийн bbox дотор байвал авна. (OSM-ийн
        # урт way-ыг нэг ч endpoint нь нөгөө талд хол байсан ч авч чадна)
        segs = list(Segment.objects.filter(
            Q(start_lat__range=(lat_lo, lat_hi),
              start_lng__range=(lng_lo, lng_hi)) |
            Q(end_lat__range=(lat_lo, lat_hi),
              end_lng__range=(lng_lo, lng_hi))
        ).only("start_lat", "start_lng", "end_lat", "end_lng",
               "geometry", "infra_level", "condition")[:1000])

        score = 0
        # Sample every 4th route point to keep checks fast
        sampled = route_coords[::4] or route_coords
        for seg in segs:
            # OSM way бол geometry-аас олон цэг ашиглана; гар хийсэн
            # сегмент бол start + end л үзнэ.
            seg_pts = _segment_match_points(seg)
            if not seg_pts:
                continue
            matched = False
            for sp_lat, sp_lng in seg_pts:
                if matched:
                    break
                for lng, lat in sampled:
                    if abs(lat - sp_lat) < 0.0008 and abs(lng - sp_lng) < 0.0008:
                        score += self.LEVEL_W.get(seg.infra_level, 0)
                        score += self.COND_W.get(seg.condition, 0)
                        # Хэрэглэгчдийн оруулсан "green" сегментэд маршрут
                        # таарвал нэмэлт онооноор давамгайлуулна — энэ нь
                        # OSRM-н багц зам биш, харин user crowd-sourced
                        # bike lane-уудыг сонгоход илүү ашиглах зорилготой
                        if seg.condition == "green":
                            score += self.USER_GREEN_BONUS
                        matched = True
                        break

        # ─ Hazard POIs in bbox
        hazards_qs = POI.objects.filter(
            status="approved",
            poi_type__in=["danger", "road_damage", "no_bike_lane"],
            latitude__range=(lat_lo, lat_hi),
            longitude__range=(lng_lo, lng_hi),
        ).only("latitude", "longitude")
        for poi in hazards_qs:
            try:
                pl, pn = float(poi.latitude), float(poi.longitude)
            except Exception:
                continue
            for lng, lat in sampled:
                if abs(lat - pl) < 0.0006 and abs(lng - pn) < 0.0006:
                    score += self.HAZARD_W
                    break

        return score


class SnapToRoadView(APIView):
    """
    POST /api/routes/snap/
    Body: { "points": [{"lat": f, "lng": f}, ...] }
    Returns road-snapped geometry.
    Falls back to the original points if OSRM is unavailable.

    OSRM has two relevant endpoints, used here for different cases:

      • /route (point-to-point pathfinding) — used when only 2 points are
        given (typical "draw start → end segment" case). /route returns a
        clean shortest-path along the road network.
      • /match (GPS trace alignment)        — used when ≥3 points are given,
        e.g. a recorded GPX trace that needs snapping to nearby roads.

    Using /match for 2 distant points is the wrong tool — it tries to fit
    them as if they were sequential GPS samples and produces zigzag paths
    through small alleys.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        points = request.data.get("points", [])
        if len(points) < 2:
            return Response({"error": "At least 2 points required"}, status=400)

        coords = ";".join(f"{p['lng']},{p['lat']}" for p in points)

        if len(points) == 2:
            # Point-to-point: ask OSRM for a proper route, not a match.
            osrm_url = (
                f"{settings.OSRM_BASE_URL}/route/v1/cycling/{coords}"
                f"?overview=full&geometries=geojson"
            )
            extract = lambda d: (d.get("routes") or [None])[0]  # noqa: E731
        else:
            # GPS-trace style: align many points to the road network.
            radiuses = ";".join("50" for _ in points)
            osrm_url = (
                f"{settings.OSRM_BASE_URL}/match/v1/cycling/{coords}"
                f"?overview=full&geometries=geojson&radiuses={radiuses}"
            )
            extract = lambda d: (d.get("matchings") or [None])[0]  # noqa: E731

        if REQUESTS_AVAILABLE:
            try:
                r = req_lib.get(osrm_url, timeout=5)
                if r.status_code == 200:
                    feature = extract(r.json())
                    if feature and feature.get("geometry"):
                        # OSRM returns [lng, lat] — convert to {lat, lng}
                        geom = feature["geometry"]["coordinates"]
                        geometry = [{"lat": c[1], "lng": c[0]} for c in geom]
                        return Response({"geometry": geometry, "source": "osrm"})
            except Exception:
                pass

        # Fallback: return the original points as a straight line.
        geometry = [{"lat": p["lat"], "lng": p["lng"]} for p in points]
        return Response({"geometry": geometry, "source": "fallback"})


class GPXClassifyView(APIView):
    """
    POST /api/routes/gpx-classify/
    Body: { "points": [{lat, lng}, ...] }

    GPX route-ийн consecutive 2 цэг хооронд тус бүр хамгийн ойрын
    хэрэглэгчийн / OSM-ийн Segment-ийг олж infra_level + condition-ийг
    өвлүүлнэ. Дараа нь дараалсан "ижил classification"-той edge-уудыг
    нэг section болгон бүлэглэж жагсаалт буцаана.

    Хариу:
        {
          "sections": [
            { "from_idx": 0, "to_idx": 12,
              "infra_level": 1, "condition": "green",
              "matched": true, "distance_m": 482 },
            ...
          ],
          "matched_count": 23,
          "unmatched_count": 7
        }
    Хэрэглэгч "Зөв" дарвал section-уудыг шууд хадгална. "Засах" дарж
    хүссэн хэсгийг өөрчлөх боломжтой.
    """
    permission_classes = [IsCyclistOrAbove]

    def post(self, request):
        points = request.data.get("points", [])
        if len(points) < 2:
            return Response({"error": "At least 2 points required"}, status=400)

        # ─ bbox + nearby segments
        try:
            lats = [float(p["lat"]) for p in points]
            lngs = [float(p["lng"]) for p in points]
        except (KeyError, TypeError, ValueError):
            return Response({"error": "Invalid point format"}, status=400)

        nearby_segs = list(Segment.objects.filter(
            Q(start_lat__range=(min(lats) - 0.005, max(lats) + 0.005),
              start_lng__range=(min(lngs) - 0.005, max(lngs) + 0.005)) |
            Q(end_lat__range=(min(lats) - 0.005, max(lats) + 0.005),
              end_lng__range=(min(lngs) - 0.005, max(lngs) + 0.005))
        ).only("start_lat", "start_lng", "end_lat", "end_lng",
               "geometry", "infra_level", "condition")[:5000])

        seg_points = []
        for s in nearby_segs:
            for plat, plng in _segment_match_points(s):
                seg_points.append((plat, plng, s.infra_level, s.condition))

        # ─ Classify each edge
        classifications = []   # [(infra_level, condition) | None for edge i]
        for i in range(len(points) - 1):
            mid_lat = (lats[i] + lats[i + 1]) / 2
            mid_lng = (lngs[i] + lngs[i + 1]) / 2
            best, best_d = None, 0.0008
            for plat, plng, lvl, cnd in seg_points:
                d = abs(plat - mid_lat) + abs(plng - mid_lng)
                if d < best_d:
                    best_d = d
                    best = (lvl, cnd)
            classifications.append(best)

        # ─ Group consecutive edges with same (level, condition) into sections
        sections = []
        if classifications:
            cur_start = 0
            cur_class = classifications[0]
            for i in range(1, len(classifications)):
                if classifications[i] != cur_class:
                    sections.append(self._make_section(
                        points, cur_start, i, cur_class))
                    cur_start = i
                    cur_class = classifications[i]
            sections.append(self._make_section(
                points, cur_start, len(classifications), cur_class))

        matched_count   = sum(1 for c in classifications if c is not None)
        unmatched_count = len(classifications) - matched_count

        return Response({
            "sections":        sections,
            "matched_count":   matched_count,
            "unmatched_count": unmatched_count,
            "edges_total":     len(classifications),
        })

    def _make_section(self, points, from_idx, to_idx, klass):
        """Helper — section dict with distance computed."""
        # to_idx is exclusive index into 'classifications', i.e. node index
        # of the END of the section. Distance: sum of edges in [from_idx, to_idx)
        d = 0
        for j in range(from_idx, to_idx):
            if j < len(points) - 1:
                d += _haversine_m(
                    float(points[j]["lat"]),     float(points[j]["lng"]),
                    float(points[j + 1]["lat"]), float(points[j + 1]["lng"]),
                )
        if klass:
            lvl, cnd = klass
            return {
                "from_idx":    from_idx,
                "to_idx":      to_idx,
                "infra_level": lvl,
                "condition":   cnd,
                "matched":     True,
                "distance_m":  round(d, 1),
            }
        else:
            return {
                "from_idx":    from_idx,
                "to_idx":      to_idx,
                "infra_level": 4,        # default
                "condition":   "yellow",  # default
                "matched":     False,
                "distance_m":  round(d, 1),
            }


class UpdateProfileDistanceView(APIView):
    """
    POST /api/routes/record-distance/
    Body: { "distance_km": float }
    Called client-side when Stop Route is pressed — US-002, E7 US-060
    Route is NOT saved to DB; only the user's total distance is incremented.
    """
    permission_classes = [IsCyclistOrAbove]

    def post(self, request):
        km = float(request.data.get("distance_km", 0))
        if km <= 0:
            return Response({"error": "distance_km must be positive"}, status=400)
        user = request.user
        user.total_distance_km += km
        user.save(update_fields=["total_distance_km"])
        return Response({"total_distance_km": user.total_distance_km})