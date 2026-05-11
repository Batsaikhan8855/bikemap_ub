/**
 * gpx_import_page.js — Тусдаа GPX import хуудас (Ride with GPS стиль)
 *  • Зөвхөн орсон GPX route-г харуулна (OSM сегмент дэвсгэр БАЙХГҮЙ)
 *  • Доор Chart.js elevation profile
 *  • Chart дээр hover хийхэд map дээр тухайн цэг highlight
 *  • Хэсэгчилж condition + infra_level (1..6) тэмдэглэн bulk-save
 */
const GPXImportPage = (() => {
  // ── 6-түвшний өнгө ────────────────────────────────────────────────
  const LEVEL_COLORS = {
    1: '#15803d', 2: '#22c55e', 3: '#84cc16',
    4: '#f59e0b', 5: '#f97316', 6: '#ef4444',
  };
  const COND_COLORS = {
    green: '#22c55e', yellow: '#f59e0b', red: '#ef4444',
  };
  const LEVEL_LABEL = {
    1: 'Тусгаарлагдсан', 2: 'Холимог',  3: 'Хамгаалалттай',
    4: 'Тэмдэглэгээт',  5: 'Явган',     6: 'Дундаа',
  };

  let map, splitLayers = [], hoverMarker = null, parsedPoints = [];
  let elevations = [], distances = [];
  let splits = [];
  let chart = null;
  let isSaving = false;
  let selectedIdx = 0;          // одоо сонгогдсон хэсгийн index
  let splitMarkers = [];        // map дээр харагдах "тоонтой" marker-ууд
  let editMode = false;         // false = Summary view, true = Edit toolbar
  let editCondition = 'green';  // toolbar-ийн одоогийн condition
  let editLevel     = 4;        // toolbar-ийн одоогийн infra_level
  // ─── 2-цэгт click flow state machine ───────────────────────────
  // 'idle'           — edit mode-аас гарсан
  // 'awaiting_start' — эхлэх цэг сонгох
  // 'awaiting_end'   — төгсгөл цэг сонгох
  // 'selected'       — 2 цэг сонгогдсон, condition/level сонгох гэж байна
  let editState        = 'idle';
  let editStartIdx     = null;   // parsedPoints дэх индекс
  let editEndIdx       = null;
  let editStartMarker  = null;
  let editEndMarker    = null;
  let editHighlight    = null;   // сонгогдсон хэсгийн цагаан outline
  let editHoverMarker  = null;   // mousemove дээр харагдах guide
  let editHistory      = [];     // undo stack (splits-ийн өмнөх snapshot)

  // ── INIT ──────────────────────────────────────────────────────────
  function init() {
    map = L.map('gpxMap', {
      zoomControl: true,
      attributionControl: true,
    }).setView([47.9167, 106.9167], 12);

    L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
      { maxZoom: 19, subdomains: 'abcd',
        attribution: '© OpenStreetMap, CARTO' }
    ).addTo(map);

    // ── Edit-mode click + hover handler ────────────────────────────
    // Map дээрх click нь editState-ээс хамаарна:
    //   awaiting_start → эхлэх цэг тэмдэглэнэ
    //   awaiting_end   → төгсгөл цэг тэмдэглэж section-ыг сонгоно
    map.on('click', (e) => {
      if (!editMode || editState === 'idle' || editState === 'selected') return;
      _handleEditClick(e.latlng);
    });
    map.on('mousemove', (e) => {
      if (!editMode || (editState !== 'awaiting_start' && editState !== 'awaiting_end')) {
        _clearHoverMarker();
        return;
      }
      _showHoverMarker(e.latlng);
    });
    map.on('mouseout', () => _clearHoverMarker());

    // Drag-and-drop upload
    const zone = document.getElementById('gpxUploadZone');
    ['dragover', 'dragenter'].forEach(ev =>
      zone.addEventListener(ev, e => { e.preventDefault();
        zone.classList.add('has-file'); }));
    ['dragleave', 'drop'].forEach(ev =>
      zone.addEventListener(ev, () => zone.classList.remove('has-file')));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      const f = e.dataTransfer.files[0];
      if (f && f.name.toLowerCase().endsWith('.gpx')) {
        const inp = document.getElementById('gpxFile');
        const dt = new DataTransfer(); dt.items.add(f); inp.files = dt.files;
        load(inp);
      }
    });
  }

  // ── LOAD GPX ──────────────────────────────────────────────────────
  async function load(input) {
    const file = input.files[0];
    if (!file) return;
    input.value = '';

    _setLabel('<span class="spinner-border spinner-border-sm me-1"></span>Уншиж байна...');

    const form = new FormData();
    form.append('gpx_file', file);

    try {
      const data = await API.postForm('/routes/gpx-import/', form);
      parsedPoints = data.points;

      // Read elevations directly from GPX file (parse client-side too)
      const text = await file.text();
      _parseElevations(text);
      _computeStats();

      window._gpxBoundsFit = false;
      selectedIdx = 0;
      editMode = false;

      // ── Auto-classify: route хэсэг бүрд condition + infra_level ──
      // оноох — backend нь user/OSM segment-тэй тулгаж дүгнэнэ.
      _setLabel('<span class="spinner-border spinner-border-sm me-1"></span>Авто-таних...');
      let cls;
      try {
        cls = await API.post('/routes/gpx-classify/', { points: parsedPoints });
      } catch (cErr) {
        // Хэрэв classify бүтэлгүйтвэл бүх route-г нэг section болгож үлдээнэ
        showToast('warning', 'Авто-таних бүтэлгүйтлээ — гараар тэмдэглэнэ үү');
        cls = { sections: [{
          from_idx:    0,
          to_idx:      parsedPoints.length - 1,
          condition:   'yellow',
          infra_level: 4,
          matched:     false,
          distance_m:  0,
        }], matched_count: 0, unmatched_count: 0 };
      }

      // Section жагсаалтыг splits-руу оноох. (`splits` гэдэг хэвээр
      // үлдсэн ч хэлбэр нь backend-ийн section-тай нийцнэ.)
      splits = (cls.sections || []).map(sec => ({
        from_idx:    sec.from_idx,
        to_idx:      sec.to_idx,
        condition:   sec.condition,
        infra_level: sec.infra_level,
        matched:     !!sec.matched,
        distance_m:  sec.distance_m || 0,
      }));
      // Хэрэв section байхгүй бол default нэг section
      if (!splits.length) {
        splits = [{
          from_idx: 0, to_idx: parsedPoints.length - 1,
          condition: 'yellow', infra_level: 4, matched: false, distance_m: 0,
        }];
      }

      _renderRoute();
      _renderChart();
      _renderSummary();
      _renderEditToolbar();

      document.getElementById('gpxStatsPanel').classList.remove('d-none');
      document.getElementById('gpxSummaryPanel').classList.remove('d-none');
      document.getElementById('gpxEditToolbar').classList.add('d-none');
      _setLabel('<i class="bi bi-check-lg text-success me-1"></i>' + file.name);
      document.getElementById('gpxUploadZone').classList.add('has-file');
    } catch (e) {
      showToast('danger', 'GPX алдаа: ' + e.message);
      _setLabel('.gpx файл сонгох');
    }
  }

  // ── Parse elevation/timestamp from raw GPX text ───────────────────
  function _parseElevations(gpxText) {
    elevations = [];
    distances  = [];
    const parser = new DOMParser();
    const doc = parser.parseFromString(gpxText, 'application/xml');
    const trkpts = doc.getElementsByTagName('trkpt');
    let prevLat = null, prevLng = null, totalDist = 0;
    const allEle = [];
    for (let i = 0; i < trkpts.length; i++) {
      const lat = parseFloat(trkpts[i].getAttribute('lat'));
      const lng = parseFloat(trkpts[i].getAttribute('lon'));
      const ele = trkpts[i].getElementsByTagName('ele')[0]?.textContent;
      const e = ele ? parseFloat(ele) : null;
      if (prevLat !== null) {
        totalDist += _haversine(prevLat, prevLng, lat, lng);
      }
      allEle.push({ ele: e, dist_km: totalDist / 1000 });
      prevLat = lat; prevLng = lng;
    }
    // Resample to match parsed (simplified) points — by distance proximity
    elevations = parsedPoints.map((p, i) => {
      // map-аас зайны хувийг авна
      const ratio = parsedPoints.length > 1 ? i / (parsedPoints.length - 1) : 0;
      const idx = Math.floor(ratio * (allEle.length - 1));
      return allEle[idx]?.ele ?? null;
    });
    // Distance for each parsed point
    distances = [0];
    for (let i = 1; i < parsedPoints.length; i++) {
      const d = _haversine(parsedPoints[i-1].lat, parsedPoints[i-1].lng,
                           parsedPoints[i].lat,   parsedPoints[i].lng) / 1000;
      distances.push(distances[i-1] + d);
    }
  }

  function _haversine(lat1, lng1, lat2, lng2) {
    const R = 6371000;
    const toRad = x => x * Math.PI / 180;
    const dLat = toRad(lat2 - lat1), dLng = toRad(lng2 - lng1);
    const a = Math.sin(dLat/2)**2
            + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLng/2)**2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  // ── Stats panel ──────────────────────────────────────────────────
  function _computeStats() {
    const totalKm = distances[distances.length-1] || 0;
    let gain = 0, loss = 0;
    for (let i = 1; i < elevations.length; i++) {
      if (elevations[i] == null || elevations[i-1] == null) continue;
      const d = elevations[i] - elevations[i-1];
      if (d > 0) gain += d; else loss -= d;
    }
    document.getElementById('gpxStatDist').textContent   = totalKm.toFixed(1) + ' км';
    document.getElementById('gpxStatPoints').textContent = parsedPoints.length;
    document.getElementById('gpxStatGain').textContent   = '+' + Math.round(gain) + ' м';
    document.getElementById('gpxStatLoss').textContent   = '−' + Math.round(loss) + ' м';
  }

  // ── Render route on map ──────────────────────────────────────────
  function _renderRoute() {
    splitLayers.forEach(l => map.removeLayer(l));
    splitLayers = [];
    splitMarkers.forEach(m => map.removeLayer(m));
    splitMarkers = [];

    splits.forEach((s, idx) => {
      const slice = parsedPoints.slice(s.from_idx, s.to_idx + 1);
      const latlngs = slice.map(p => [p.lat, p.lng]);
      const isSelected = idx === selectedIdx;

      // Selection halo — сонгогдсон хэсгийн доор цагаан outline
      if (isSelected) {
        const halo = L.polyline(latlngs, {
          color: '#ffffff', weight: 12, opacity: 0.55,
          lineCap: 'round', lineJoin: 'round',
        }).addTo(map);
        splitLayers.push(halo);
      }

      // Casing
      const casing = L.polyline(latlngs, {
        color: '#0b1220', weight: isSelected ? 10 : 8,
        opacity: isSelected ? 0.7 : 0.5,
        lineCap: 'round', lineJoin: 'round',
      }).addTo(map);

      // Top line — color = infra_level color
      const top = L.polyline(latlngs, {
        color: LEVEL_COLORS[s.infra_level],
        weight: isSelected ? 6 : 5,
        opacity: isSelected ? 1 : 0.85,
        lineCap: 'round', lineJoin: 'round',
      }).addTo(map);

      // Summary view-д section-ыг дарвал тухайн хэсгийг highlight хийнэ.
      // Edit mode-д бол map-ийн ерөнхий click handler нь 2-цэгт flow-ыг
      // хариуцдаг тул polyline дээр нэмэлт click handler хэрэггүй.
      if (!editMode) {
        top.on('click', () => selectSplit(idx));
      }

      splitLayers.push(casing, top);
    });

    // Numbered split marker-уудыг АРИЛГАСАН. Зөвхөн хэрэглэгчийн өөрөө
    // дарж үүсгэсэн start/end marker л edit mode-д харагдана.

    // Fit bounds (only when first rendering / after upload — not on every redraw)
    if (parsedPoints.length && !window._gpxBoundsFit) {
      const bounds = L.latLngBounds(parsedPoints.map(p => [p.lat, p.lng]));
      map.fitBounds(bounds, { padding: [40, 40] });
      window._gpxBoundsFit = true;
    }

    // Endpoints (start green, end red)
    const sp = parsedPoints[0];
    const ep = parsedPoints[parsedPoints.length - 1];
    splitLayers.push(L.circleMarker([sp.lat, sp.lng], {
      radius: 8, color: '#fff', fillColor: '#22c55e',
      fillOpacity: 1, weight: 2,
    }).addTo(map).bindTooltip('Эхлэл'));
    splitLayers.push(L.circleMarker([ep.lat, ep.lng], {
      radius: 8, color: '#fff', fillColor: '#ef4444',
      fillOpacity: 1, weight: 2,
    }).addTo(map).bindTooltip('Төгсгөл'));
  }

  // Хэрэглэгч сонгосон хэсэг
  function selectSplit(idx) {
    if (idx < 0 || idx >= splits.length) return;
    selectedIdx = idx;
    _renderRoute();
    _renderSplits();
  }

  // ── Render Chart.js elevation profile ────────────────────────────
  function _renderChart() {
    if (chart) chart.destroy();
    const ctx = document.getElementById('gpxElevChart').getContext('2d');
    const data = elevations.map((e, i) => ({ x: distances[i], y: e ?? 0 }));

    chart = new Chart(ctx, {
      type: 'line',
      data: {
        datasets: [{
          label: 'Elevation',
          data,
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34,197,94,.15)',
          fill: true,
          tension: 0.25,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: '#fff',
          pointHoverBorderColor: '#22c55e',
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 0 },
        interaction: { mode: 'nearest', intersect: false, axis: 'x' },
        scales: {
          x: { type: 'linear', title: { display: true, text: 'Зай (км)',
               color: '#6b7280', font: { size: 10 } },
               grid: { color: 'rgba(255,255,255,.05)' },
               ticks: { color: '#6b7280', font: { size: 10 } } },
          y: { title: { display: true, text: 'Өндөр (м)',
               color: '#6b7280', font: { size: 10 } },
               grid: { color: 'rgba(255,255,255,.05)' },
               ticks: { color: '#6b7280', font: { size: 10 } } },
        },
        plugins: {
          legend: { display: false },
          tooltip: { enabled: false },
        },
        onHover: (e, items) => {
          if (items.length) {
            const idx = items[0].index;
            _highlightPoint(idx);
          } else {
            _hideHighlight();
          }
        },
      },
    });

    // Mouse leave
    document.getElementById('gpxElevChart').addEventListener('mouseleave',
      () => _hideHighlight());
  }

  function _highlightPoint(idx) {
    const p = parsedPoints[idx];
    if (!p) return;
    if (!hoverMarker) {
      hoverMarker = L.circleMarker([p.lat, p.lng], {
        radius: 8, color: '#fff', fillColor: '#22c55e',
        fillOpacity: 1, weight: 3,
      }).addTo(map);
    } else {
      hoverMarker.setLatLng([p.lat, p.lng]);
    }
    document.getElementById('gpxHoverInfo').textContent =
      `${distances[idx].toFixed(2)} км · ${Math.round(elevations[idx] || 0)} м`;
  }
  function _hideHighlight() {
    if (hoverMarker) { map.removeLayer(hoverMarker); hoverMarker = null; }
    document.getElementById('gpxHoverInfo').textContent = '';
  }

  // ── Summary panel (auto-detect view) ────────────────────────────
  function _renderSummary() {
    const km = { green: 0, yellow: 0, red: 0, unknown: 0 };
    splits.forEach(s => {
      const dist = (s.distance_m || _sectionDistance(s)) / 1000;
      if (!s.matched) km.unknown += dist;
      else if (s.condition === 'green')  km.green  += dist;
      else if (s.condition === 'yellow') km.yellow += dist;
      else if (s.condition === 'red')    km.red    += dist;
    });
    document.getElementById('kmGreen').textContent  = km.green.toFixed(1)  + ' км';
    document.getElementById('kmYellow').textContent = km.yellow.toFixed(1) + ' км';
    document.getElementById('kmRed').textContent    = km.red.toFixed(1)    + ' км';
    document.getElementById('kmUnknown').textContent =
      `Тэмдэглэгдээгүй хэсэг: ${km.unknown.toFixed(1)} км · Нийт ${splits.length} section`;
  }

  function _sectionDistance(s) {
    let d = 0;
    for (let i = s.from_idx; i < s.to_idx; i++) {
      if (i < parsedPoints.length - 1) {
        d += _haversine(parsedPoints[i].lat,   parsedPoints[i].lng,
                        parsedPoints[i+1].lat, parsedPoints[i+1].lng);
      }
    }
    return d;
  }

  // ── Edit-mode toolbar (sidebar) ─────────────────────────────────
  function _renderEditToolbar() {
    // Condition pills
    const row = document.getElementById('gpxEditCondRow');
    if (!row) return;
    row.innerHTML = ['green', 'yellow', 'red'].map(co => {
      const active = co === editCondition;
      const label  = co === 'green' ? 'Зам' : co === 'yellow' ? 'Боломжтой' : 'Боломжгүй';
      const emoji  = co === 'green' ? '🟢' : co === 'yellow' ? '🟡' : '🔴';
      return `
        <button class="gpx-cond-pill ${active ? 'active' : ''}"
                style="--cond-color:${COND_COLORS[co]}"
                onclick="GPXImportPage.setEditCondition('${co}')">
          ${emoji} ${label}
        </button>`;
    }).join('');

    // Level select
    const sel = document.getElementById('gpxEditLevel');
    if (sel) {
      sel.value = editLevel;
      sel.onchange = (ev) => { editLevel = parseInt(ev.target.value, 10); };
    }
  }

  function setEditCondition(co) {
    editCondition = co;
    _renderEditToolbar();
  }

  function toggleEditMode() {
    editMode = !editMode;
    document.getElementById('gpxSummaryPanel').classList.toggle('d-none', editMode);
    document.getElementById('gpxEditToolbar').classList.toggle('d-none', !editMode);
    if (editMode) {
      editState = 'awaiting_start';
      _resetEditMarkers();
      _updateEditPrompt('Эхлэх цэгээ дарна уу');
      map.getContainer().style.cursor = 'crosshair';
      _refreshApplyBtn();
    } else {
      editState = 'idle';
      _resetEditMarkers();
      _updateEditPrompt('');
      map.getContainer().style.cursor = '';
    }
    _renderRoute();
  }

  // ── 2-цэгт state machine: click handler ──────────────────────────
  function _handleEditClick(latlng) {
    const idx = _findNearestRoutePoint(latlng);
    if (idx == null) return;
    const p = parsedPoints[idx];

    if (editState === 'awaiting_start') {
      editStartIdx = idx;
      if (editStartMarker) map.removeLayer(editStartMarker);
      editStartMarker = L.marker([p.lat, p.lng], {
        icon: L.divIcon({
          className: 'gpx-edit-marker',
          html: '<div class="gpx-edit-pin start">A</div>',
          iconSize: [26, 26], iconAnchor: [13, 13],
        }),
        zIndexOffset: 600,
      }).addTo(map);
      editState = 'awaiting_end';
      _updateEditPrompt('Төгсгөлийн цэгээ дарна уу');
      _refreshApplyBtn();
      return;
    }

    if (editState === 'awaiting_end') {
      if (idx === editStartIdx) {
        showToast('warning', 'Өөр цэг сонгоно уу');
        return;
      }
      editEndIdx = idx;
      // Ensure start < end for slicing
      if (editStartIdx > editEndIdx) {
        [editStartIdx, editEndIdx] = [editEndIdx, editStartIdx];
        // Swap visual markers
        const sp = parsedPoints[editStartIdx];
        const ep = parsedPoints[editEndIdx];
        if (editStartMarker) editStartMarker.setLatLng([sp.lat, sp.lng]);
      }
      const ep = parsedPoints[editEndIdx];
      if (editEndMarker) map.removeLayer(editEndMarker);
      editEndMarker = L.marker([ep.lat, ep.lng], {
        icon: L.divIcon({
          className: 'gpx-edit-marker',
          html: '<div class="gpx-edit-pin end">B</div>',
          iconSize: [26, 26], iconAnchor: [13, 13],
        }),
        zIndexOffset: 600,
      }).addTo(map);

      // Highlight selected slice with thick white outline
      const slice = parsedPoints.slice(editStartIdx, editEndIdx + 1)
                                .map(pt => [pt.lat, pt.lng]);
      if (editHighlight) map.removeLayer(editHighlight);
      editHighlight = L.polyline(slice, {
        color: '#ffffff', weight: 14, opacity: 0.65,
        lineCap: 'round', lineJoin: 'round',
      }).addTo(map);

      editState = 'selected';
      _updateEditPrompt('Нөхцөл + зэрэглэлээ сонгож «Хадгалах» дарна уу');
      _refreshApplyBtn();
    }
  }

  function _findNearestRoutePoint(latlng) {
    let bestIdx = null, bestD = Infinity;
    for (let i = 0; i < parsedPoints.length; i++) {
      const dx = parsedPoints[i].lat - latlng.lat;
      const dy = parsedPoints[i].lng - latlng.lng;
      const d  = dx * dx + dy * dy;
      if (d < bestD) { bestD = d; bestIdx = i; }
    }
    return bestIdx;
  }

  function _showHoverMarker(latlng) {
    const idx = _findNearestRoutePoint(latlng);
    if (idx == null) return;
    const p = parsedPoints[idx];
    if (!editHoverMarker) {
      editHoverMarker = L.circleMarker([p.lat, p.lng], {
        radius: 7, color: '#fff', fillColor: '#22c55e',
        fillOpacity: 1, weight: 2,
      }).addTo(map);
    } else {
      editHoverMarker.setLatLng([p.lat, p.lng]);
    }
  }
  function _clearHoverMarker() {
    if (editHoverMarker) { map.removeLayer(editHoverMarker); editHoverMarker = null; }
  }

  function _resetEditMarkers() {
    if (editStartMarker) { map.removeLayer(editStartMarker); editStartMarker = null; }
    if (editEndMarker)   { map.removeLayer(editEndMarker);   editEndMarker = null; }
    if (editHighlight)   { map.removeLayer(editHighlight);   editHighlight = null; }
    _clearHoverMarker();
    editStartIdx = null;
    editEndIdx   = null;
  }

  function _updateEditPrompt(text) {
    let el = document.getElementById('gpxEditPrompt');
    if (!el) {
      el = document.createElement('div');
      el.id = 'gpxEditPrompt';
      el.className = 'gpx-edit-prompt';
      document.querySelector('.gpx-map-area')?.appendChild(el);
    }
    if (!text) { el.style.display = 'none'; return; }
    el.innerHTML = `<i class="bi bi-cursor-fill me-2 text-success"></i>${text}`;
    el.style.display = 'block';
  }

  function _refreshApplyBtn() {
    const btn = document.getElementById('btnApplyEdit');
    if (btn) btn.disabled = (editState !== 'selected');
  }

  // ── Хадгалах: 2 цэгийн хооронд шинэ section үүсгэх ──────────────
  function applyEdit() {
    if (editState !== 'selected' || editStartIdx == null || editEndIdx == null) return;

    // Undo snapshot
    editHistory.push(JSON.parse(JSON.stringify(splits)));

    // Хуучин splits-ийг шинэ диапазонтой огтлолцсон тал тус бүрт нь
    // 3 хэсэг болгож хуваана: [хуучин эхлэлээс editStartIdx] +
    // [editStartIdx..editEndIdx — шинэ] + [editEndIdx-аас хуучин төгсгөл]
    const newSplits = [];
    splits.forEach(s => {
      if (s.to_idx <= editStartIdx || s.from_idx >= editEndIdx) {
        newSplits.push(s); return;
      }
      if (s.from_idx < editStartIdx) {
        newSplits.push({ ...s, to_idx: editStartIdx });
      }
      if (s.to_idx > editEndIdx) {
        newSplits.push({ ...s, from_idx: editEndIdx });
      }
      // Дунд хэсгийг (overlap with edit range) орхино — доор шинээр нэмнэ.
    });
    // Шинэ хэсэг
    let d = 0;
    for (let i = editStartIdx; i < editEndIdx; i++) {
      d += _haversine(parsedPoints[i].lat,   parsedPoints[i].lng,
                      parsedPoints[i+1].lat, parsedPoints[i+1].lng);
    }
    newSplits.push({
      from_idx:    editStartIdx,
      to_idx:      editEndIdx,
      condition:   editCondition,
      infra_level: editLevel,
      matched:     true,
      distance_m:  d,
    });
    newSplits.sort((a, b) => a.from_idx - b.from_idx);
    splits = newSplits;

    showToast('success', 'Хэсэг шинэчлэгдлээ');

    // Дараагийн засварт бэлдэх
    _resetEditMarkers();
    editState = 'awaiting_start';
    _updateEditPrompt('Эхлэх цэгээ дарна уу');
    _refreshApplyBtn();
    _renderRoute();
    _renderSummary();
  }

  function cancelEdit() {
    if (editState === 'idle') return;
    _resetEditMarkers();
    editState = 'awaiting_start';
    _updateEditPrompt('Эхлэх цэгээ дарна уу');
    _refreshApplyBtn();
  }

  function undoEdit() {
    if (!editHistory.length) {
      showToast('info', 'Буцаах өөрчлөлт алга');
      return;
    }
    splits = editHistory.pop();
    cancelEdit();
    _renderRoute();
    _renderSummary();
    showToast('info', 'Өмнөх засвар сэргэлээ');
  }

  // ── Splits sidebar UI (deprecated — manual section edit) ─────────
  function _renderSplits() {
    const c = document.getElementById('gpxSplitsContainer');
    c.innerHTML = '';

    splits.forEach((s, idx) => {
      const km1 = distances[s.from_idx]?.toFixed(1) || '0';
      const km2 = distances[s.to_idx]?.toFixed(1)   || '0';
      const lenKm = (parseFloat(km2) - parseFloat(km1)).toFixed(1);
      const isSelected = idx === selectedIdx;

      const div = document.createElement('div');
      div.className = 'gpx-split-card' + (isSelected ? ' active' : '');
      // Бүхэл картыг дарвал тухайн хэсэг сонгогдоно (товч/control дотор биш)
      div.onclick = (ev) => {
        if (ev.target.closest('button, select, input')) return;
        selectSplit(idx);
      };

      // Pills (том, тод харагдах condition сонголт)
      const condPills = ['green','yellow','red'].map(co => {
        const active = s.condition === co;
        const emoji  = co === 'green' ? '🟢' : co === 'yellow' ? '🟡' : '🔴';
        const label  = co === 'green' ? 'Зам' : co === 'yellow' ? 'Боломжтой' : 'Боломжгүй';
        return `
          <button class="gpx-cond-pill ${active ? 'active' : ''}"
                  style="--cond-color:${COND_COLORS[co]}"
                  onclick="GPXImportPage.setCondition(${idx},'${co}')">
            ${emoji} ${label}
          </button>`;
      }).join('');

      // Level (1..6) buttons grid
      const lvlBtns = [1,2,3,4,5,6].map(lv => {
        const active = s.infra_level === lv;
        return `
          <button class="gpx-level-btn ${active ? 'active' : ''}"
                  style="--lvl-color:${LEVEL_COLORS[lv]}"
                  title="${LEVEL_LABEL[lv]}"
                  onclick="GPXImportPage.setLevel(${idx}, ${lv})">
            ${lv}
          </button>`;
      }).join('');

      div.innerHTML = `
        <div class="d-flex justify-content-between align-items-center mb-2">
          <div class="d-flex align-items-center gap-2">
            <span class="gpx-split-num"
                  style="background:${LEVEL_COLORS[s.infra_level]}">${idx + 1}</span>
            <strong style="font-size:.85rem">Хэсэг ${idx + 1}</strong>
          </div>
          <span class="text-secondary" style="font-size:.68rem">
            ${km1} → ${km2} км · ${lenKm} км
          </span>
        </div>
        <div class="gpx-cond-row mb-2">${condPills}</div>
        <div class="gpx-sidebar-label small text-secondary mb-1">Зэрэглэл</div>
        <div class="gpx-level-row mb-1">${lvlBtns}</div>
        <div class="text-secondary text-center mt-1" style="font-size:.7rem">
          ${LEVEL_LABEL[s.infra_level] || ''}
        </div>
        ${splits.length > 1 ? `
          <button class="btn btn-sm btn-outline-danger w-100 mt-2"
                  style="font-size:.7rem"
                  onclick="GPXImportPage.removeSplit(${idx})">
            <i class="bi bi-trash"></i> Энэ хэсгийг устгах
          </button>` : ''}
      `;
      c.appendChild(div);
    });
  }

  function setCondition(idx, cond) {
    if (!splits[idx]) return;
    splits[idx].condition = cond;
    _renderRoute(); _renderSplits();
  }
  function setLevel(idx, lvl) {
    if (!splits[idx]) return;
    splits[idx].infra_level = parseInt(lvl, 10);
    _renderRoute(); _renderSplits();
  }
  function addSplit() {
    if (!splits.length) return;
    // Сонгогдсон хэсгийг хагасаар нь хувааж шинэ хэсэг үүсгэнэ
    const target = splits[selectedIdx] || splits[splits.length - 1];
    const targetIdx = splits.indexOf(target);
    const mid = Math.floor((target.from_idx + target.to_idx) / 2);
    if (mid <= target.from_idx) return;
    const newSecond = {
      from_idx: mid, to_idx: target.to_idx,
      condition: 'yellow', infra_level: target.infra_level,
    };
    target.to_idx = mid;
    splits.splice(targetIdx + 1, 0, newSecond);
    selectedIdx = targetIdx + 1;  // сонгогдсон шинэ хэсэгт шилжинэ
    _renderRoute(); _renderSplits();
  }
  function removeSplit(idx) {
    if (splits.length <= 1) return;
    const removed = splits.splice(idx, 1)[0];
    if (idx === 0) splits[0].from_idx = removed.from_idx;
    else splits[idx - 1].to_idx = removed.to_idx;
    if (selectedIdx >= splits.length) selectedIdx = splits.length - 1;
    _renderRoute(); _renderSplits();
  }

  // ── Save bulk segments ───────────────────────────────────────────
  async function save() {
    if (!parsedPoints.length || isSaving) return;
    const payload = {
      splits: splits.map(s => ({
        points: parsedPoints.slice(s.from_idx, s.to_idx + 1)
                            .map(p => ({ lat: p.lat, lng: p.lng })),
        condition:   s.condition,
        infra_level: s.infra_level,
      })),
    };
    isSaving = true;
    const btn = document.getElementById('btnSaveGPX');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Хадгалж байна...';
    try {
      const res = await API.post('/routes/gpx-import/save/', payload);
      showToast('success', `${res.created_count} сегмент хадгалагдлаа!`);
      setTimeout(() => window.location.href = '/map/', 1200);
    } catch (e) {
      showToast('danger', e.message);
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Хадгалах';
    } finally {
      isSaving = false;
    }
  }

  function clear() {
    splitLayers.forEach(l => map.removeLayer(l));
    splitMarkers.forEach(m => map.removeLayer(m));
    splitLayers = []; splitMarkers = [];
    parsedPoints = []; splits = [];
    elevations = []; distances = [];
    selectedIdx = 0;
    editMode = false;
    window._gpxBoundsFit = false;
    if (chart) { chart.destroy(); chart = null; }
    if (map) map.getContainer().style.cursor = '';
    document.getElementById('gpxStatsPanel').classList.add('d-none');
    document.getElementById('gpxSummaryPanel')?.classList.add('d-none');
    document.getElementById('gpxEditToolbar')?.classList.add('d-none');
    document.getElementById('gpxUploadZone').classList.remove('has-file');
    _setLabel('.gpx файл сонгох');
  }

  function _setLabel(html) {
    const el = document.getElementById('gpxUploadLabel');
    if (el) el.innerHTML = html;
  }

  return {
    init, load, save, clear,
    setCondition, setLevel, addSplit, removeSplit, selectSplit,
    toggleEditMode, setEditCondition,
    applyEdit, cancelEdit, undoEdit,
  };
})();

document.addEventListener('DOMContentLoaded', GPXImportPage.init);
