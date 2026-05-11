/**
 * gpx_import.js — GPX file import with **split labeling**:
 *   1. файл upload  → /api/routes/gpx-import/  (preview + simplified points)
 *   2. UI: route-г n хэсэгт хувааж тус бүрд condition + infra_level (1..6) сонгох
 *   3. save → /api/routes/gpx-import/save/  bulk Segment үүсгэнэ
 */
const GPXImport = (() => {
  const COLORS = {
    green:  '#22c55e',
    yellow: '#f59e0b',
    red:    '#ef4444',
  };
  // 6 түвшний дэд бүтцийн өнгийг визуалчлахад
  const LEVEL_COLORS = {
    1: '#15803d',  // тусгаарлагдсан — хамгийн аюулгүй (хар ногоон)
    2: '#22c55e',  // холимог
    3: '#84cc16',  // хамгаалалттай
    4: '#f59e0b',  // тэмдэглэгээт
    5: '#f97316',  // явган хүний зам
    6: '#ef4444',  // дундаа ашиглах — хамгийн эрсдэлтэй
  };

  let parsedPoints = [];
  let splitLayers  = [];   // массив тус Leaflet polyline-ууд
  let splits       = [];   // [{ from_idx, to_idx, condition, infra_level }]
  let isSaving     = false;

  // ── 1. GPX файл upload ─────────────────────────────────────────────
  async function load(input) {
    const file = input.files[0];
    if (!file) return;
    input.value = '';  // allow re-selecting same file

    const form = new FormData();
    form.append('gpx_file', file);

    _setLoading(true);
    try {
      const data = await API.gpxImport(form);
      parsedPoints = data.points;
      // Эхэнд ганц split — бүх route-д нэг condition
      splits = [{
        from_idx:    0,
        to_idx:      parsedPoints.length - 1,
        condition:   'green',
        infra_level: 4,
      }];
      _renderPreview();
      _renderSplitsUI();
      document.getElementById('gpxImportPanel').classList.remove('d-none');
      _showInfo(`${data.total_original} цэг → ${data.segment_count} сегмент. Доор хэсэг хэсгээр condition / зэрэглэл тэмдэглэнэ үү.`);
    } catch (e) {
      showToast('danger', 'GPX алдаа: ' + e.message);
    } finally {
      _setLoading(false);
    }
  }

  // ── 2. Splits-ийг газрын зурагт зурах ──────────────────────────────
  function _renderPreview() {
    _clearLayers();
    if (!parsedPoints.length) return;

    splits.forEach(s => {
      const slice = parsedPoints.slice(s.from_idx, s.to_idx + 1);
      const latlngs = slice.map(p => [p.lat, p.lng]);
      const layer = L.polyline(latlngs, {
        color:     COLORS[s.condition],
        weight:    5,
        opacity:   0.85,
        dashArray: '10 5',
      }).addTo(map);
      splitLayers.push(layer);
    });
    // Хамгийн эхний split-ийн bounds-аар fit
    if (splitLayers.length) {
      const all = L.featureGroup(splitLayers);
      map.fitBounds(all.getBounds(), { padding: [30, 30] });
    }
  }

  // ── 3. Splits UI зурах (control panel) ─────────────────────────────
  function _renderSplitsUI() {
    const container = document.getElementById('gpxSplitsContainer');
    if (!container) return;
    container.innerHTML = '';

    splits.forEach((s, idx) => {
      const total = parsedPoints.length - 1;
      const pctFrom = Math.round((s.from_idx / total) * 100);
      const pctTo   = Math.round((s.to_idx   / total) * 100);

      const row = document.createElement('div');
      row.className = 'border border-secondary rounded p-2 mb-2';
      row.style.background = 'rgba(255,255,255,.04)';
      row.innerHTML = `
        <div class="d-flex justify-content-between mb-2">
          <strong style="color:${COLORS[s.condition]}">Хэсэг ${idx + 1}</strong>
          <span class="text-muted" style="font-size:.7rem">
            ${pctFrom}% → ${pctTo}%  (цэг ${s.from_idx + 1}–${s.to_idx + 1})
          </span>
        </div>
        <div class="d-flex gap-1 mb-2">
          <button class="btn btn-sm btn-success ${s.condition === 'green' ? 'active' : ''}"
                  onclick="GPXImport.setCondition(${idx},'green')">🟢 ногоон</button>
          <button class="btn btn-sm btn-warning ${s.condition === 'yellow' ? 'active' : ''}"
                  onclick="GPXImport.setCondition(${idx},'yellow')">🟡 шар</button>
          <button class="btn btn-sm btn-danger ${s.condition === 'red' ? 'active' : ''}"
                  onclick="GPXImport.setCondition(${idx},'red')">🔴 улаан</button>
        </div>
        <div class="d-flex align-items-center gap-2 mb-2">
          <small class="text-muted" style="font-size:.7rem">Зэрэглэл:</small>
          <select class="form-select form-select-sm" style="max-width:120px"
                  onchange="GPXImport.setLevel(${idx}, this.value)">
            <option value="1" ${s.infra_level === 1 ? 'selected' : ''}>1 — тусгаарлагдсан</option>
            <option value="2" ${s.infra_level === 2 ? 'selected' : ''}>2 — холимог</option>
            <option value="3" ${s.infra_level === 3 ? 'selected' : ''}>3 — хамгаалалттай</option>
            <option value="4" ${s.infra_level === 4 ? 'selected' : ''}>4 — тэмдэглэгээт</option>
            <option value="5" ${s.infra_level === 5 ? 'selected' : ''}>5 — явган хүний</option>
            <option value="6" ${s.infra_level === 6 ? 'selected' : ''}>6 — дундаа</option>
          </select>
          ${splits.length > 1 ? `
            <button class="btn btn-sm btn-outline-danger ms-auto"
                    onclick="GPXImport.removeSplit(${idx})"
                    title="Хэсэг хасах">
              <i class="bi bi-trash"></i>
            </button>` : ''}
        </div>
      `;
      container.appendChild(row);
    });

    // Хэсэг нэмэх товч
    const addBtn = document.createElement('button');
    addBtn.className = 'btn btn-sm btn-outline-light w-100 mt-2';
    addBtn.innerHTML = '<i class="bi bi-plus-lg me-1"></i>Шинэ хэсэг нэмэх (route-г 2-т хуваана)';
    addBtn.onclick = () => addSplit();
    container.appendChild(addBtn);
  }

  // ── 4. Split удирдах функцууд ──────────────────────────────────────
  function setCondition(idx, cond) {
    if (!splits[idx]) return;
    splits[idx].condition = cond;
    _renderPreview();
    _renderSplitsUI();
  }

  function setLevel(idx, lvl) {
    if (!splits[idx]) return;
    splits[idx].infra_level = parseInt(lvl, 10);
    _renderSplitsUI();
  }

  function addSplit() {
    // Хамгийн сүүлийн split-ийг 50/50-аар хувааж өгнө
    if (!splits.length) return;
    const last = splits[splits.length - 1];
    const mid  = Math.floor((last.from_idx + last.to_idx) / 2);
    if (mid <= last.from_idx) return;

    const newSecond = {
      from_idx:    mid,
      to_idx:      last.to_idx,
      condition:   'yellow',
      infra_level: last.infra_level,
    };
    last.to_idx = mid;
    splits.push(newSecond);
    _renderPreview();
    _renderSplitsUI();
  }

  function removeSplit(idx) {
    if (splits.length <= 1) return;
    // Зэргэлдээ хэсэгт нь нэмж шингээх
    const removed = splits.splice(idx, 1)[0];
    if (idx === 0) {
      splits[0].from_idx = removed.from_idx;
    } else {
      splits[idx - 1].to_idx = removed.to_idx;
    }
    _renderPreview();
    _renderSplitsUI();
  }

  // ── 5. Save → /api/routes/gpx-import/save/ ─────────────────────────
  async function save() {
    if (!parsedPoints.length || isSaving) return;

    const payload = {
      splits: splits.map(s => ({
        points: parsedPoints
                  .slice(s.from_idx, s.to_idx + 1)
                  .map(p => ({ lat: p.lat, lng: p.lng })),
        condition:   s.condition,
        infra_level: s.infra_level,
      })),
    };

    isSaving = true;
    const btn = document.getElementById('btnSaveGPX');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Хадгалж байна...';
    }

    try {
      const res = await API.post('/routes/gpx-import/save/', payload);
      showToast('success', `${res.created_count} сегмент хадгалагдлаа!`);
      clear();
      MapMain.loadSegments?.();
    } catch (e) {
      showToast('danger', e.message);
    } finally {
      isSaving = false;
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Хадгалах';
      }
    }
  }

  // ── 6. Cleanup ─────────────────────────────────────────────────────
  function clear() {
    _clearLayers();
    parsedPoints = [];
    splits = [];
    document.getElementById('gpxImportPanel')?.classList.add('d-none');
    const c = document.getElementById('gpxSplitsContainer');
    if (c) c.innerHTML = '';
    _showInfo('');
  }

  function _clearLayers() {
    splitLayers.forEach(l => map.removeLayer(l));
    splitLayers = [];
  }

  function _showInfo(text) {
    const info = document.getElementById('gpxPreviewInfo');
    if (info) info.innerHTML = text
      ? `<span class="text-secondary" style="font-size:.75rem">${text}</span>`
      : '';
  }

  function _setLoading(on) {
    const lbl = document.getElementById('gpxFileLabel');
    if (!lbl) return;
    lbl.innerHTML = on
      ? '<span class="spinner-border spinner-border-sm me-1"></span>Уншиж байна...'
      : '<i class="bi bi-upload me-1"></i>GPX файл сонгох';
    lbl.classList.toggle('disabled', on);
  }

  return {
    load, save, clear,
    setCondition, setLevel,
    addSplit, removeSplit,
    getPoints: () => parsedPoints,
    LEVEL_COLORS,
  };
})();
