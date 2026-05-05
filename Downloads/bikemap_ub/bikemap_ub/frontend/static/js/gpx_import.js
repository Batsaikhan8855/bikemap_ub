/**
 * gpx_import.js — GPX file import: upload → preview on map → bulk-save segments
 */
const GPXImport = (() => {
  const COLORS = { green: '#22c55e', yellow: '#f59e0b', red: '#ef4444' };
  let previewLayer = null;
  let parsedPoints = [];
  let selectedCond = 'green';
  let isSaving     = false;

  async function load(input) {
    const file = input.files[0];
    if (!file) return;
    input.value = '';   // allow re-selecting same file

    const form = new FormData();
    form.append('gpx_file', file);

    _setLoading(true);
    try {
      const data = await API.gpxImport(form);
      parsedPoints = data.points;
      _showPreview(data);
      document.getElementById('gpxImportPanel').classList.remove('d-none');
    } catch (e) {
      showToast('danger', 'GPX алдаа: ' + e.message);
    } finally {
      _setLoading(false);
    }
  }

  function _showPreview(data) {
    _clearLayer();
    const latlngs = data.points.map(p => [p.lat, p.lng]);
    previewLayer = L.polyline(latlngs, {
      color:      COLORS[selectedCond],
      weight:     4,
      opacity:    0.85,
      dashArray:  '10 5',
    }).addTo(map);
    map.fitBounds(previewLayer.getBounds(), { padding: [30, 30] });

    const info = document.getElementById('gpxPreviewInfo');
    if (info) {
      info.innerHTML =
        `<span class="text-secondary" style="font-size:.75rem">` +
        `${data.total_original} цэг → <strong class="text-light">${data.segment_count}</strong> сегмент</span>`;
    }
  }

  function setCond(cond) {
    selectedCond = cond;
    ['green', 'yellow', 'red'].forEach(c => {
      const btn = document.getElementById('gpxCond' + c.charAt(0).toUpperCase() + c.slice(1));
      if (btn) btn.classList.toggle('active', c === cond);
    });
    if (previewLayer) previewLayer.setStyle({ color: COLORS[cond] });
  }

  async function save() {
    if (!parsedPoints.length || isSaving) return;

    const segs = [];
    for (let i = 0; i < parsedPoints.length - 1; i++) {
      segs.push({
        start_lat:   parsedPoints[i].lat,
        start_lng:   parsedPoints[i].lng,
        end_lat:     parsedPoints[i + 1].lat,
        end_lng:     parsedPoints[i + 1].lng,
        condition:   selectedCond,
        infra_level: parseInt(document.getElementById('gpxInfraLevel')?.value || '4', 10),
        is_created:  false,
      });
    }

    isSaving = true;
    const btn = document.getElementById('btnSaveGPX');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Хадгалж байна...'; }

    try {
      const res = await API.bulkImportSegs(segs);
      showToast('success', `${res.created} сегмент хадгалагдлаа!`);
      if (res.errors?.length) showToast('warning', `${res.errors.length} сегмент алдаатай`);
      clear();
      MapMain.loadSegments();
    } catch (e) {
      showToast('danger', e.message);
    } finally {
      isSaving = false;
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Хадгалах'; }
    }
  }

  function clear() {
    _clearLayer();
    parsedPoints = [];
    selectedCond = 'green';
    document.getElementById('gpxImportPanel')?.classList.add('d-none');
    setCond('green');
    const info = document.getElementById('gpxPreviewInfo');
    if (info) info.innerHTML = '';
  }

  function _clearLayer() {
    if (previewLayer) { map.removeLayer(previewLayer); previewLayer = null; }
  }

  function _setLoading(on) {
    const lbl = document.getElementById('gpxFileLabel');
    if (!lbl) return;
    lbl.innerHTML = on
      ? '<span class="spinner-border spinner-border-sm me-1"></span>Уншиж байна...'
      : '<i class="bi bi-upload me-1"></i>GPX файл сонгох';
    lbl.classList.toggle('disabled', on);
  }

  return { load, setCond, save, clear };
})();
