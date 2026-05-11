/**
 * Smart Route — E5 US-040 US-041 US-042
 */
const SmartRoute = {
  routeLayer: null,
  startMarker: null, endMarker: null,
  pickingStart: false, pickingEnd: false,
  selectedMode: 'safe',

  init(map) {
    this.map = map;
    this.routeLayer = L.layerGroup().addTo(map);

    document.querySelectorAll('.bm-mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.bm-mode-btn').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        this.selectedMode = btn.dataset.mode;
      });
    });
  },

  handleMapClick(latlng) {
    if (this.pickingStart) {
      this.pickingStart = false;
      this.startMarker?.remove();
      this.startMarker = L.marker(latlng, {
        icon: L.divIcon({html:'<div style="background:#22c55e;width:14px;height:14px;border-radius:50%;border:2px solid white"></div>',className:'',iconSize:[14,14]})
      }).addTo(this.map);
      document.getElementById('routeStart').value = `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`;
      document.getElementById('routeStart').dataset.lat = latlng.lat;
      document.getElementById('routeStart').dataset.lng = latlng.lng;
      this.map.getContainer().style.cursor = '';
      showToast('info','Одоо төгсгөлийн цэг тавина уу');
      this.pickingEnd = true;
      this.map.getContainer().style.cursor = 'crosshair';
      return true;
    }
    if (this.pickingEnd) {
      this.pickingEnd = false;
      this.endMarker?.remove();
      this.endMarker = L.marker(latlng, {
        icon: L.divIcon({html:'<div style="background:#ef4444;width:14px;height:14px;border-radius:50%;border:2px solid white"></div>',className:'',iconSize:[14,14]})
      }).addTo(this.map);
      document.getElementById('routeEnd').value = `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`;
      document.getElementById('routeEnd').dataset.lat = latlng.lat;
      document.getElementById('routeEnd').dataset.lng = latlng.lng;
      this.map.getContainer().style.cursor = '';
      return true;
    }
    return false;
  },

  async calculate() {
    const startEl = document.getElementById('routeStart');
    const endEl   = document.getElementById('routeEnd');
    const sLat = parseFloat(startEl.dataset.lat);
    const sLng = parseFloat(startEl.dataset.lng);
    const eLat = parseFloat(endEl.dataset.lat);
    const eLng = parseFloat(endEl.dataset.lng);
    if (isNaN(sLat)||isNaN(eLat)) {
      showToast('warning','Газрын зурагт эхлэл болон төгсгөл тавина уу');
      this.pickingStart = true;
      this.map.getContainer().style.cursor = 'crosshair';
      showToast('info','Эхлэлийн цэг тавина уу');
      return;
    }
    try {
      showToast('info','Маршрут тооцоолж байна...');
      const data = await API.smartRoute({
        start:{lat:sLat,lng:sLng},
        end:  {lat:eLat,lng:eLng},
        mode: this.selectedMode,
      });
      this._renderRoute(data);
      const km = (data.distance_m/1000).toFixed(2);
      const min = Math.round(data.duration_s/60);
      showToast('success',`Маршрут: ${km} км · ${min} мин`);
    } catch(e) { showToast('danger','Маршрут тооцооллын алдаа: '+e.message); }
  },

  // ── Visual style constants ─────────────────────────────────────────
  // Two stacked polylines (casing + line) keep the route readable
  // even when it overlaps the colored segments below it.
  ROUTE_STYLE: {
    osrm: {
      casing: { color: '#0b1220', weight: 9, opacity: 0.55, lineCap: 'round', lineJoin: 'round' },
      line:   { color: '#3b82f6', weight: 5, opacity: 1.00, lineCap: 'round', lineJoin: 'round' },
    },
    // Fallback = OSRM unavailable → just a straight line. Make it
    // obviously different so users know it's not a real road route.
    fallback: {
      casing: { color: '#3a2a00', weight: 8, opacity: 0.40, lineCap: 'round', lineJoin: 'round' },
      line:   { color: '#f59e0b', weight: 4, opacity: 0.95, dashArray: '10 8',
                lineCap: 'round', lineJoin: 'round' },
    },
  },

  // 6 түвшний дэд бүтцийн зэрэглэлийн өнгө (NFR06)
  //   1 = тусгаарлагдсан bike lane (хамгийн аюулгүй)
  //   6 = дундаа ашиглах зам    (хамгийн эрсдэлтэй)
  LEVEL_COLORS: {
    1: '#15803d',  // dark green
    2: '#22c55e',  // green
    3: '#84cc16',  // lime
    4: '#f59e0b',  // amber
    5: '#f97316',  // orange
    6: '#ef4444',  // red
  },
  // Crowd dominant 3 өнгө (CrowdAggregation)
  CROWD_COLORS: {
    green:  '#22c55e',
    yellow: '#f59e0b',
    red:    '#ef4444',
  },

  _renderRoute(data) {
    this.routeLayer.clearLayers();

    // Build a single polyline path. Prefer `coordinates` (continuous line),
    // fall back to stitching `segments` end-to-end.
    let latlngs = null;
    if (data.coordinates?.length) {
      latlngs = data.coordinates.map(c => [c[1], c[0]]);
    } else if (data.segments?.length) {
      latlngs = [];
      data.segments.forEach((seg, i) => {
        if (i === 0) latlngs.push([seg.from[1], seg.from[0]]);
        latlngs.push([seg.to[1], seg.to[0]]);
      });
    }

    if (latlngs && latlngs.length > 1) {
      const isFallback = data.routing_status === 'fallback' || latlngs.length === 2;
      const S = isFallback ? SmartRoute.ROUTE_STYLE.fallback : SmartRoute.ROUTE_STYLE.osrm;

      // Layer 1: dark casing (renders below)
      L.polyline(latlngs, { pane: 'bm-route-casing', ...S.casing })
        .addTo(this.routeLayer);

      // Layer 2: маршрут дээр crowd colour + 6-түвшний infra_level
      // тус бүрийн сегментийг тус тусын өнгөөр зурна. Хэрэв
      // segments массив хоосон бол анхдагч хөх line-аар зурна.
      const segs = data.segments || [];
      if (!isFallback && segs.length) {
        segs.forEach(seg => {
          const a = [seg.from[1], seg.from[0]];
          const b = [seg.to[1],   seg.to[0]];
          // Өнгийг infra_level (1..6) > crowd colour > default дарааллаар
          let color;
          if (seg.infra_level && SmartRoute.LEVEL_COLORS[seg.infra_level]) {
            color = SmartRoute.LEVEL_COLORS[seg.infra_level];
          } else if (seg.colour && SmartRoute.CROWD_COLORS[seg.colour]) {
            color = SmartRoute.CROWD_COLORS[seg.colour];
          } else {
            color = '#3b82f6';  // unknown — neutral blue
          }
          L.polyline([a, b], {
            pane: 'bm-route-line',
            color, weight: 6, opacity: 0.95,
            lineCap: 'round', lineJoin: 'round',
          }).addTo(this.routeLayer);
        });
      } else {
        // OSRM-аас сегмент хариу өгөөгүй / fallback бол энгийн line
        L.polyline(latlngs, { pane: 'bm-route-line', ...S.line })
          .addTo(this.routeLayer);
      }

      // Tell the map we're in "route mode" so the segments pane fades.
      this.map.getContainer().classList.add('bm-route-active');
      this.map.getContainer().classList.toggle('bm-route-fallback', isFallback);

      if (isFallback) {
        showToast('warning',
          'OSRM сервер хариу өгсөнгүй — энэ зөвхөн шулуун чиглэл. Замын алхам гэж бүү тоо.');
      }
    }

    // Hazard markers — default markerPane is already above all our custom panes.
    (data.hazards || []).forEach(h => {
      L.circleMarker([h.lat, h.lng], {
        radius: 8, color: '#ef4444', fillColor: '#ef4444',
        fillOpacity: 0.7, weight: 2,
      })
      .bindTooltip(`⚠ ${h.poi_type}`)
      .addTo(this.routeLayer);
    });

    // ── Render legend / infra-level breakdown panel ──────────────
    SmartRoute._renderLegend(data);
  },

  /**
   * Маршрутын дэргэд дугаар + 6-түвшний задаргааг харуулах легенд.
   * Жнь: 12% Level 1, 30% Level 2, 25% Level 4 гэх мэт. Хэрэглэгчид
   * замын аюулгүй байдал-ыг харахад тусална.
   */
  _renderLegend(data) {
    const segs = data.segments || [];
    const total = segs.length;
    const matched = segs.filter(s => s.matched).length;

    // ─ Level distribution
    const levelCount = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, unknown:0};
    segs.forEach(s => {
      if (s.infra_level && levelCount[s.infra_level] !== undefined) {
        levelCount[s.infra_level]++;
      } else {
        levelCount.unknown++;
      }
    });

    const km  = (data.distance_m / 1000).toFixed(1);
    const min = Math.round(data.duration_s / 60);
    const modeLabel = data.mode === 'safe' ? 'Аюулгүй' : 'Хурдан';

    const LEVEL_LABELS = {
      1: 'Тусгаарлагдсан', 2: 'Холимог', 3: 'Хамгаалалттай',
      4: 'Тэмдэглэгээт',   5: 'Явган',    6: 'Машинтай',
    };

    const rows = [1,2,3,4,5,6].map(lvl => {
      const n = levelCount[lvl];
      if (!n) return '';
      const pct = total ? (n * 100 / total).toFixed(0) : 0;
      const color = SmartRoute.LEVEL_COLORS[lvl];
      return `
        <div class="d-flex align-items-center gap-2 mb-1" style="font-size:.72rem">
          <span style="display:inline-block;width:14px;height:6px;
                       background:${color};border-radius:3px"></span>
          <span class="flex-fill">${lvl} — ${LEVEL_LABELS[lvl]}</span>
          <span class="text-secondary">${pct}%</span>
        </div>`;
    }).join('');

    const unknownRow = levelCount.unknown ? `
      <div class="d-flex align-items-center gap-2 mb-1" style="font-size:.72rem">
        <span style="display:inline-block;width:14px;height:6px;
                     background:#3b82f6;border-radius:3px;opacity:.5"></span>
        <span class="flex-fill text-secondary">— Мэдээлэлгүй (OSRM-ийн зам)</span>
        <span class="text-secondary">${(levelCount.unknown*100/total).toFixed(0)}%</span>
      </div>` : '';

    // Find or create legend element
    let legend = document.getElementById('routeLegend');
    if (!legend) {
      legend = document.createElement('div');
      legend.id = 'routeLegend';
      legend.className = 'bm-route-legend card border-secondary shadow';
      document.querySelector('.bm-map-pane')?.appendChild(legend);
    }
    legend.innerHTML = `
      <div class="card-body p-2">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <strong style="font-size:.78rem">
            <i class="bi bi-signpost-2 me-1 text-success"></i>${modeLabel} маршрут
          </strong>
          <button class="btn-close btn-close-white btn-sm"
                  onclick="SmartRoute.clear()" title="Хаах"
                  style="font-size:.65rem"></button>
        </div>
        <div class="d-flex gap-2 mb-2" style="font-size:.72rem">
          <span><i class="bi bi-rulers text-success me-1"></i>${km} км</span>
          <span><i class="bi bi-clock text-info me-1"></i>${min} мин</span>
          <span class="text-secondary ms-auto">${matched}/${total} тэмдэглэгээтэй</span>
        </div>
        <hr class="my-1" style="border-color: var(--bm-border)">
        ${rows || '<p class="small text-secondary mb-0">Замд тэмдэглэсэн сегмент байхгүй.</p>'}
        ${unknownRow}
      </div>`;
    legend.style.display = 'block';
  },

  clear() {
    this.routeLayer?.clearLayers();
    this.startMarker?.remove(); this.endMarker?.remove();
    this.startMarker=null; this.endMarker=null;
    document.getElementById('routeStart').value='';
    document.getElementById('routeEnd').value='';
    delete document.getElementById('routeStart').dataset.lat;
    delete document.getElementById('routeStart').dataset.lng;
    delete document.getElementById('routeEnd').dataset.lat;
    delete document.getElementById('routeEnd').dataset.lng;

    // Restore segments to full opacity.
    this.map?.getContainer().classList.remove('bm-route-active');
    this.map?.getContainer().classList.remove('bm-route-fallback');

    // Hide legend panel
    const legend = document.getElementById('routeLegend');
    if (legend) legend.style.display = 'none';
  },
};