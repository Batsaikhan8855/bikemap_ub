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
try:
    import requests as req_lib
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
import gpxpy
from apps.accounts.permissions import IsCyclistOrAbove
from apps.pois.models import POI
from apps.aggregation.models import CrowdAggregation


def _haversine_m(lat1, lng1, lat2, lng2):
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


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
    Returns OSRM route annotated with segment colours + POI hazards — US-040
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        start = request.data.get("start")
        end   = request.data.get("end")
        mode  = request.data.get("mode", "safe")

        if not start or not end:
            return Response({"error": "start and end required"}, status=400)

        # 1. Fetch base route from OSRM
        osrm_url = (
            f"{settings.OSRM_BASE_URL}/route/v1/cycling/"
            f"{start['lng']},{start['lat']};{end['lng']},{end['lat']}"
            f"?overview=full&geometries=geojson&steps=true"
        )
        osrm_data = None
        if REQUESTS_AVAILABLE:
            try:
                r = req_lib.get(osrm_url, timeout=5)
                if r.status_code == 200:
                    osrm_data = r.json()
            except Exception:
                pass

        # 2. If OSRM unavailable, return straight-line fallback
        if not osrm_data or not osrm_data.get("routes"):
            route_coords = [
                [start["lng"], start["lat"]],
                [end["lng"],   end["lat"]],
            ]
            distance_m = 1000
            duration_s = 300
        else:
            route      = osrm_data["routes"][0]
            route_coords = route["geometry"]["coordinates"]
            distance_m = route["distance"]
            duration_s = route["duration"]

        # 3. Annotate with aggregation colours
        segments_colour = []
        for i in range(len(route_coords) - 1):
            lng1, lat1 = route_coords[i]
            lng2, lat2 = route_coords[i + 1]
            agg = CrowdAggregation.objects.filter(
                start_lat__range=(lat1 - 0.002, lat1 + 0.002),
                start_lng__range=(lng1 - 0.002, lng1 + 0.002),
            ).first()
            colour = agg.dominant if agg else "unknown"
            segments_colour.append({"from": [lng1, lat1], "to": [lng2, lat2],
                                     "colour": colour})

        # 4. Nearby POI hazards (within ~50 m) — US-040
        danger_types = ["danger", "road_damage", "no_bike_lane"]
        seen_hazard_ids = set()
        hazards = []
        for coord in route_coords:
            lng, lat = coord
            nearby = POI.objects.filter(
                status="approved",
                poi_type__in=danger_types,
                latitude__range=(lat - 0.0005, lat + 0.0005),
                longitude__range=(lng - 0.0005, lng + 0.0005),
            )
            for p in nearby:
                if p.id not in seen_hazard_ids:
                    seen_hazard_ids.add(p.id)
                    hazards.append({
                        "id": p.id, "poi_type": p.poi_type,
                        "lat": float(p.latitude), "lng": float(p.longitude),
                    })

        return Response({
            "mode":       mode,
            "distance_m": distance_m,
            "duration_s": duration_s,
            "coordinates": route_coords,
            "segments":   segments_colour,
            "hazards":    hazards,
        })


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