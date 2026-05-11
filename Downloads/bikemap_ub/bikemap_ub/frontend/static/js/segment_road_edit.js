/**
 * RoadEditMode — GPX маршрутын дагуу сегмент үүсгэх
 * 1-р дарж → GPX-ийн хамгийн ойр цэгт эхлэл тавих
 * 2-р дарж → төгсгөл тавих → тэр хэсгийг highlight → нөхцөл/зэрэглэл → save
 */
const RoadEditMode = (() => {
  let _map            = null;
  let _active         = false;
  let _step           = 0;    // 1=waiting start  2=waiting end  3=editing
  let _startIdx       = -1;
  let _endIdx         = -1;
  let _lastCreatedId  = null; // undo-д ашиглана
  let _hlLayer        = null;
  let _mkLayer        = null;

  const COLORS = { green: '#22c55e', yellow: '#f59e0b', red: '#ef4444' };

  // ── public ──────────────────────────────────────────────────────────

  function init(map) {
    _map     = map;
    _hlLayer = L.layerGroup();
    _mkLayer = L.layerGroup();
  }

  function toggle() { _active ? _exit() : _enter(); }

  function handleMapClick(latlng) {
    if (!_active) return false;
    const pts = GPXImport.getPoints();
    if (!pts || !pts.length) {
      showToast('warning', 'Эхлээд GPX файл оруулна уу');
      return true;
    }
    if (_step === 1) { _placeStart(latlng, pts); return true; }
    if (_step === 2) { _placeEnd(latlng, pts);   return true; }
    return true;
  }

  function setCond(c) {
    document.querySelectorAll('#roadEditPanel [data-cond]')
      .forEach(b => b.classList.toggle('active', b.dataset.cond === c));
    document.getElementById('repCondHidden').value = c;
    _hlLayer.eachLayer(l => { if (l.options._isTop) l.setStyle({ color: COLORS[c] || '#facc15' }); });
  }

  async function save() {
    const pts   = GPXImport.getPoints();
    const cond  = document.getElementById('repCondHidden').value;
    const level = parseInt(document.getElementById('repLevel').value, 10);
    if (_startIdx < 0 || _endIdx < 0 || !pts.length) return;

    const s     = Math.min(_startIdx, _endIdx);
    const e     = Math.max(_startIdx, _endIdx);
    const slice = pts.slice(s, e + 1);
    if (slice.length < 2) { showToast('warning', 'Хэтэрхий богино хэсэг'); return; }

    const btn = document.getElementById('btnRepSave');
    if (btn) { btn.disabled = true; btn.textContent = 'Хадгалж байна…'; }

    try {
      const res = await API.createSegment({
        start_lat:   slice[0].lat,
        start_lng:   slice[0].lng,
        end_lat:     slice[slice.length - 1].lat,
        end_lng:     slice[slice.length - 1].lng,
        condition:   cond,
        infra_level: level,
        geometry:    slice,
      });
      _lastCreatedId = res.id;
      const undoBtn = document.getElementById('btnRoadUndo');
      if (undoBtn) undoBtn.style.display = '';
      showToast('success', 'Сегмент нэмэгдлээ ✓');
      await window.MapMain.loadSegments();
      cancel();
    } catch (err) {
      showToast('danger', err.message);
    } finally {
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Хадгалах'; }
    }
  }

  async function undo() {
    if (!_lastCreatedId) { showToast('warning', 'Буцаах зүйл алга'); return; }
    try {
      await API.deleteSegment(_lastCreatedId);
      _lastCreatedId = null;
      const undoBtn = document.getElementById('btnRoadUndo');
      if (undoBtn) undoBtn.style.display = 'none';
      showToast('info', 'Өмнөх байдалд буцлаа');
      window.MapMain.loadSegments();
    } catch (err) {
      showToast('danger', err.message);
    }
  }

  function cancel() {
    _step = 1; _startIdx = -1; _endIdx = -1;
    _hlLayer.clearLayers();
    _mkLayer.clearLayers();
    _setPrompt('Эхлэх цэгийг тавина уу');
    _panel(false);
  }

  function isActive() { return _active; }

  // ── private ─────────────────────────────────────────────────────────

  function _enter() {
    const pts = GPXImport.getPoints();
    if (!pts || !pts.length) {
      showToast('warning', 'Эхлээд GPX файл оруулна уу');
      return;
    }
    _active = true; _step = 1;
    _hlLayer.addTo(_map); _mkLayer.addTo(_map);
    _map.getContainer().style.cursor = 'crosshair';
    _setPrompt('Эхлэх цэгийг тавина уу');
    _panel(false);
    const btn = document.getElementById('btnRoadEdit');
    if (btn) { btn.classList.add('active'); btn.innerHTML = '<i class="bi bi-x-lg me-1"></i>Гарах'; }
  }

  function _exit() {
    _active = false; _step = 0;
    _startIdx = -1; _endIdx = -1;
    _map.getContainer().style.cursor = '';
    _setPrompt('');
    _panel(false);
    _hlLayer.clearLayers(); _mkLayer.clearLayers();
    if (_map.hasLayer(_hlLayer)) _map.removeLayer(_hlLayer);
    if (_map.hasLayer(_mkLayer)) _map.removeLayer(_mkLayer);
    const btn = document.getElementById('btnRoadEdit');
    if (btn) { btn.classList.remove('active'); btn.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Зам засах'; }
  }

  function _nearestIdx(latlng, pts) {
    let best = 0, bestD = Infinity;
    for (let i = 0; i < pts.length; i++) {
      const dlat = pts[i].lat - latlng.lat;
      const dlng = pts[i].lng - latlng.lng;
      const d = dlat * dlat + dlng * dlng;
      if (d < bestD) { bestD = d; best = i; }
    }
    return best;
  }

  function _placeStart(latlng, pts) {
    _startIdx = _nearestIdx(latlng, pts);
    _mkLayer.clearLayers();
    _hlLayer.clearLayers();
    _mkMarker([pts[_startIdx].lat, pts[_startIdx].lng], 'А');
    _step = 2;
    _setPrompt('Төгсгөлийн цэгийг тавина уу');
  }

  function _placeEnd(latlng, pts) {
    _endIdx = _nearestIdx(latlng, pts);
    _mkMarker([pts[_endIdx].lat, pts[_endIdx].lng], 'Б');
    _step = 3;
    _setPrompt('');
    _highlightSlice(pts);
  }

  function _mkMarker(latlng, label) {
    L.circleMarker(latlng, {
      radius: 8, color: '#fff', weight: 2,
      fillColor: '#3b82f6', fillOpacity: 1,
      pane: 'markerPane',
    }).bindTooltip(label, { permanent: true, direction: 'top',
                            className: 'bm-edit-tip' })
      .addTo(_mkLayer);
  }

  function _highlightSlice(pts) {
    const s     = Math.min(_startIdx, _endIdx);
    const e     = Math.max(_startIdx, _endIdx);
    const slice = pts.slice(s, e + 1);

    _hlLayer.clearLayers();

    if (slice.length < 2) {
      showToast('warning', 'Хэтэрхий богино хэсэг — өөр цэг сонгоно уу');
      cancel();
      return;
    }

    const lls = slice.map(p => [p.lat, p.lng]);
    L.polyline(lls, { pane: 'bm-edit-highlight', color: '#fff', weight: 12, opacity: 0.35 }).addTo(_hlLayer);
    L.polyline(lls, { pane: 'bm-edit-highlight', color: '#facc15', weight: 6,  opacity: 1, _isTop: true }).addTo(_hlLayer);

    _panel(true, 'green', 4, slice.length);
  }

  function _setPrompt(msg) {
    const el = document.getElementById('roadEditPrompt');
    if (!el) return;
    const span = el.querySelector('span') || el;
    span.textContent = msg;
    el.style.display = msg ? 'flex' : 'none';
  }

  function _panel(show, cond = 'green', level = 4, count = 0) {
    const el = document.getElementById('roadEditPanel');
    if (!el) return;
    if (!show) { el.style.display = 'none'; return; }
    document.getElementById('repCount').textContent = count;
    document.getElementById('repLevel').value = String(level);
    document.querySelectorAll('#roadEditPanel [data-cond]')
      .forEach(b => b.classList.toggle('active', b.dataset.cond === cond));
    document.getElementById('repCondHidden').value = cond;
    el.style.display = 'block';
  }

  return { init, toggle, handleMapClick, setCond, save, undo, cancel, isActive };
})();
