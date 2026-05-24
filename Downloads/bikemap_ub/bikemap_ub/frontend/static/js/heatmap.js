/**
 * heatmap.js — Strava-style heatmap (full-screen, gradient density)
 * Үндсэн идэвхтэй өгөгдөл:
 *   • Segment-ийн coordinates (start + end + geometry midpoints) → heat point
 *   • POI-ийн coordinates (approved) → heat point
 * Leaflet.heat plugin-аар нягтшилыг градиентээр харуулна.
 */
const HeatmapPage = (() => {
  let map, heatLayer = null;
  let segments = [], pois = [];
  let activeFilter = '';
  let intensity = 8;   // Strava Global Heatmap — нарийн гэрэлтсэн шугам

  // ── Strava Global Heatmap gradient ──────────────────────────────
  // Хамгийн их явсан газар цагаан-шар (hot)
  // Бага явсан газар хөх-ягаан (cold)
  // Их contrast — диплом дээр convincing харагдана
  // ── Strava Global Heatmap-ын яг тэр gradient ────────────────────────
  // Бага явсан газар: тунгалаг хөх → ягаан
  // Их явсан газар:   шар → улбар шар → цагаан (hottest)
  const GRADIENT = {
    0.00: 'rgba(0, 0, 80, 0)',         // тунгалаг
    0.10: 'rgba(20, 0, 100, .50)',     // dark indigo
    0.25: 'rgba(80, 30, 200, .72)',    // purple-blue (Strava cold)
    0.40: 'rgba(0, 140, 220, .82)',    // bright blue
    0.55: 'rgba(0, 200, 200, .88)',    // cyan
    0.70: 'rgba(60, 220, 100, .92)',   // bright green
    0.82: 'rgba(255, 230, 0, .96)',    // gold
    0.92: 'rgba(255, 150, 0, .98)',    // orange
    1.00: 'rgba(255, 255, 255, 1)',    // hottest white core
  };

  async function init() {
    map = L.map('heatmap', {
      zoomControl: true,
      attributionControl: false,
    }).setView([47.9167, 106.9167], 12);

    // Dark tile (Strava-той ойролцоо стиль)
    L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      { maxZoom: 19, subdomains: 'abcd' }
    ).addTo(map);

    await loadData();
    render();
  }

  async function loadData() {
    try {
      const [segRes, poiRes] = await Promise.all([
        fetch('/api/segments/', { credentials: 'same-origin' })
          .then(r => r.ok ? r.json() : []).catch(() => []),
        fetch('/api/pois/?status=approved&page_size=500', { credentials: 'same-origin' })
          .then(r => r.ok ? r.json() : { results: [] }).catch(() => ({ results: [] })),
      ]);
      // /segments/ нь pagination_class=None — массив шууд буцаана
      segments = Array.isArray(segRes) ? segRes : (segRes.results || []);
      // /pois/ нь paginated — results-аас гаргах
      pois     = Array.isArray(poiRes) ? poiRes : (poiRes.results || []);

      console.log('[Heatmap] loaded', segments.length, 'segments,',
                  pois.length, 'POIs');

      document.getElementById('heatStatSegs').textContent = segments.length;
      document.getElementById('heatStatPois').textContent = pois.length;
      const totalKm = (segments.length * 0.2).toFixed(1);
      document.getElementById('heatStatKm').textContent   = totalKm;
      document.getElementById('heatCount').textContent    =
        segments.length + pois.length;

      if (segments.length === 0 && pois.length === 0) {
        if (typeof showToast === 'function') {
          showToast('warning',
            'Өгөгдөл олдсонгүй. Эхлээд сегмент эсвэл POI оруулна уу.');
        }
      }
    } catch (e) {
      console.error('Heatmap load error:', e);
      if (typeof showToast === 'function') {
        showToast('danger', 'Өгөгдөл татахад алдаа: ' + e.message);
      }
    }
  }

  function _weight(cond) {
    if (cond === 'green')  return 0.45;
    if (cond === 'yellow') return 0.72;
    if (cond === 'red')    return 1.0;
    return 0.55;
  }

  function _buildPoints() {
    const pts = [];
    const condFilter = ['green','yellow','red'].includes(activeFilter)
                         ? activeFilter : null;
    const includeSeg = activeFilter !== 'poi';
    const includePoi = activeFilter !== 'seg' && !condFilter;

    if (includeSeg) {
      segments.forEach(s => {
        if (condFilter && s.condition !== condFilter) return;
        const w = _weight(s.condition);
        const sl = parseFloat(s.start_lat), sn = parseFloat(s.start_lng);
        const el = parseFloat(s.end_lat),   en = parseFloat(s.end_lng);
        if (!isFinite(sl) || !isFinite(sn)
            || !isFinite(el) || !isFinite(en)) return;

        // Strava-н "глоу шугам" эффект: сегмент бүрд олон дунд цэг тарааж
        // нэмнэ. Цэг хооронд ойролцоо байх тусам heat шугам мэт гэрэлтэнэ.
        const STEPS = 12;  // 12 дунд цэг → нарийн тасархайгүй шугам
        for (let k = 0; k <= STEPS; k++) {
          const t = k / STEPS;
          const lat = sl + (el - sl) * t;
          const lng = sn + (en - sn) * t;
          pts.push([lat, lng, w]);
        }
      });
    }
    if (includePoi) {
      pois.forEach(p => {
        const heat = ['danger', 'road_damage', 'no_bike_lane']
                       .includes(p.poi_type) ? 1.0 : 0.55;
        const lat = parseFloat(p.latitude), lng = parseFloat(p.longitude);
        if (isFinite(lat) && isFinite(lng)) pts.push([lat, lng, heat]);
      });
    }
    return pts;
  }

  function render() {
    if (heatLayer) map.removeLayer(heatLayer);
    const pts = _buildPoints();
    console.log('[Heatmap] rendering', pts.length, 'heat points');
    if (!pts.length) {
      if (typeof showToast === 'function') showToast('info', 'Шүүлтэд тохирох цэг олдсонгүй');
      return;
    }

    // Хэрэв leaflet.heat plugin ачаалагдаагүй бол circleMarker-аар fallback
    if (typeof L.heatLayer !== 'function') {
      console.warn('[Heatmap] L.heatLayer not available, using circleMarker fallback');
      heatLayer = L.layerGroup();
      pts.forEach(([lat, lng, w]) => {
        const color = w >= 0.85 ? '#fef08a'
                     : w >= 0.65 ? '#ef4444'
                     : w >= 0.45 ? '#f59e0b'
                     : w >= 0.25 ? '#22c55e' : '#1e3a8a';
        L.circleMarker([lat, lng], {
          radius:      Math.max(5, intensity * 0.6),
          color,
          fillColor:   color,
          fillOpacity: 0.45 + w * 0.3,
          weight:      0,
        }).addTo(heatLayer);
      });
      heatLayer.addTo(map);
    } else {
      // Strava-н "thin glowing line" стиль:
      //   radius  бага     → нарийн шугам
      //   blur    маш бага → хурц зах
      //   minOpacity өндөр → бүх зам тод харагдана
      heatLayer = L.heatLayer(pts, {
        radius:      intensity,            // 8 px анхдагч
        blur:        Math.max(4, Math.round(intensity * 0.45)),  // нимгэн blur
        maxZoom:     17,
        minOpacity:  0.55,                 // илүү тод
        gradient:    GRADIENT,
      }).addTo(map);
    }

    if (!window._heatFitted) {
      const lats = pts.map(p => p[0]);
      const lngs = pts.map(p => p[1]);
      const bounds = L.latLngBounds(
        [Math.min(...lats), Math.min(...lngs)],
        [Math.max(...lats), Math.max(...lngs)],
      );
      map.fitBounds(bounds, { padding: [40, 40] });
      window._heatFitted = true;
    }
  }

  function filter(value) {
    activeFilter = value;
    document.querySelectorAll('.heat-filter-pill').forEach(b => {
      b.classList.toggle('active', b.dataset.c === value);
    });
    render();
  }

  function setIntensity(v) {
    intensity = parseInt(v, 10);
    render();
  }

  return { init, filter, setIntensity };
})();

document.addEventListener('DOMContentLoaded', HeatmapPage.init);
