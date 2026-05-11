/**
 * map.js — Main Leaflet map initialisation & coordination
 */
const COND_COLORS = {green:'#22c55e', yellow:'#f59e0b', red:'#ef4444', none:'#4a5568'};

// Per-infrastructure-level visual style. Color comes from `condition`,
// shape (weight + dashArray) comes from `infra_level` so the user can
// tell *what kind of road* it is at a glance:
//   1 — Тусгаарлагдсан дугуйн зам   (solid, thickest — safest)
//   2 — Холимог ашиглалтын зам     (solid, medium)
//   3 — Хамгаалалттай дугуйн эгнээ (long-dash)
//   4 — Тэмдэглэгээт дугуйн эгнээ  (medium dash — painted only)
//   5 — Явган хүний зам            (short dash — sidewalk)
//   6 — Нийтийн зам (машинтай)    (sparse dots — shared with cars)
const INFRA_STYLE = {
  1: { weight: 6, dashArray: null,    opacity: 0.85 },
  2: { weight: 5, dashArray: null,    opacity: 0.75 },
  3: { weight: 5, dashArray: '18 4',  opacity: 0.75 },
  4: { weight: 4, dashArray: '10 6',  opacity: 0.70 },
  5: { weight: 3, dashArray: '4 6',   opacity: 0.60 },
  6: { weight: 3, dashArray: '2 8',   opacity: 0.55 },
};
const INFRA_LABEL = {
  1: 'Тусгаарлагдсан зам',
  2: 'Холимог ашиглалт',
  3: 'Хамгаалалттай эгнээ',
  4: 'Тэмдэглэгээт эгнээ',
  5: 'Явган хүний зам',
  6: 'Нийтийн зам',
};

let map, segLayer, gpxLayerGroup, allSegments=[], activeTab='map';

// Define global functions OUTSIDE DOMContentLoaded so inline onclick handlers can find them
function switchTab(tab) {
  activeTab = tab;
  ['map','route','segment'].forEach(t => {
    const btn = document.getElementById('tab'+t.charAt(0).toUpperCase()+t.slice(1));
    const content = document.getElementById('tabContent'+t.charAt(0).toUpperCase()+t.slice(1));
    if (btn) btn.classList.toggle('active', t===tab);
    if (content) content.style.display = t===tab ? 'block' : 'none';
  });
  if (tab==='segment') {
    showToast('info','Газрын зурагт эхлэл цэг тавина уу');
    if (map) map.getContainer().style.cursor='crosshair';
  } else {
    if (map) map.getContainer().style.cursor='';
    if (SegmentDraw && SegmentDraw.reset) SegmentDraw.reset();
  }
}

function activeCondFilters() {
  return [...document.querySelectorAll('.bm-filter.active')].map(b=>b.dataset.c);
}

function renderSegments() {
  if (!segLayer) return;
  segLayer.clearLayers();
  const filters = activeCondFilters();
  allSegments.filter(s=>filters.includes(s.condition)).forEach(seg => {
    const color = COND_COLORS[seg.condition] || '#4a5568';
    const lvl   = parseInt(seg.infra_level) || 4;
    const style = INFRA_STYLE[lvl] || INFRA_STYLE[4];
    const opts  = {
      pane:      'bm-segments',  // draws below the active route
      color,
      weight:    style.weight,
      opacity:   style.opacity,
      lineCap:   'round',
      lineJoin:  'round',
    };
    if (style.dashArray) opts.dashArray = style.dashArray;

    // Use stored road-snapped geometry when available, fall back to straight line
    const latlngs = (seg.geometry && seg.geometry.length >= 2)
      ? seg.geometry.map(p => [p.lat, p.lng])
      : [[parseFloat(seg.start_lat), parseFloat(seg.start_lng)],
         [parseFloat(seg.end_lat),   parseFloat(seg.end_lng)]];

    L.polyline(latlngs, opts)
    .bindTooltip(
      `<strong>${seg.condition.toUpperCase()}</strong>` +
      ` · Зэрэглэл ${lvl} — ${INFRA_LABEL[lvl] || ''}`
    )
    .on('mouseover', function() {
      if (!RoadEditMode.isActive()) this.setStyle({ weight: opts.weight + 3, opacity: 1 });
    })
    .on('mouseout',  function() {
      if (!RoadEditMode.isActive()) this.setStyle({ weight: opts.weight, opacity: opts.opacity });
    })
    .addTo(segLayer);
  });
}

function renderSegmentList(q='') {
  const filters = activeCondFilters();
  const ql = q.toLowerCase();
  const items = allSegments.filter(s =>
    filters.includes(s.condition) &&
    (!ql || s.condition.includes(ql) || (s.user?.username || '').toLowerCase().includes(ql))
  );
  const el = document.getElementById('segmentList');
  if (!items.length) {
    el.innerHTML='<p class="text-secondary small text-center py-3">Сегмент олдсонгүй.</p>';
    return;
  }
  const labels = {green:'🟢 Дугуйн зам', yellow:'🟡 Боломжтой', red:'🔴 Боломжгүй'};
  const me = (Auth?.getUser?.() || null);
  const myId = me?.id || null;
  const isMod = me && ['admin', 'moderator'].includes(me.role);

  el.innerHTML = items.map(s => {
    const canEdit = (myId && s.user?.id === myId) || isMod;
    return `
    <div class="card bg-dark border-secondary mb-2 bm-segment-card ${s.condition}">
      <div class="card-body py-2 px-3">
        <div class="d-flex justify-content-between align-items-center"
             style="cursor:pointer"
             onclick="map.setView([${s.start_lat},${s.start_lng}],15)">
          <span class="small fw-semibold">${labels[s.condition]||s.condition}</span>
          <span class="text-secondary" style="font-size:.7rem">Lvl ${s.infra_level}</span>
        </div>
        <div class="text-secondary" style="font-size:.7rem">
          ${s.user?.username||'—'} · ${new Date(s.created_at).toLocaleDateString()}
        </div>
        ${canEdit ? `
        <div class="d-flex gap-1 mt-2">
          <button class="btn btn-outline-warning btn-sm py-0 px-2"
                  style="font-size:.7rem"
                  onclick="event.stopPropagation(); SegmentEdit.open(${s.id})">
            <i class="bi bi-pencil"></i> Засах
          </button>
          <button class="btn btn-outline-danger btn-sm py-0 px-2"
                  style="font-size:.7rem"
                  onclick="event.stopPropagation(); SegmentEdit.remove(${s.id})">
            <i class="bi bi-trash"></i> Устгах
          </button>
        </div>` : ''}
      </div>
    </div>`;
  }).join('');
}

// ── Segment edit / delete module ────────────────────────────────────
const SegmentEdit = {
  open(id) {
    const seg = allSegments.find(s => s.id === id);
    if (!seg) return;

    // Modal үүсгэх
    let modal = document.getElementById('segEditModal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'segEditModal';
      modal.className = 'modal fade';
      modal.setAttribute('tabindex', '-1');
      document.body.appendChild(modal);
    }
    modal.innerHTML = `
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content bg-dark text-light border border-secondary">
          <div class="modal-header border-secondary">
            <h6 class="modal-title">
              <i class="bi bi-pencil-square me-1"></i>Сегмент засварлах
            </h6>
            <button class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label small text-secondary">Замын нөхцөл</label>
              <div class="d-flex gap-2">
                ${['green','yellow','red'].map(c => `
                  <button class="btn flex-fill ${seg.condition===c?'active':''}"
                          data-cond="${c}"
                          style="background:${ {green:'#22c55e',yellow:'#f59e0b',red:'#ef4444'}[c] };color:#000"
                          onclick="SegmentEdit._setCond('${c}')">
                    ${c==='green'?'🟢 Ногоон':c==='yellow'?'🟡 Шар':'🔴 Улаан'}
                  </button>`).join('')}
              </div>
            </div>
            <div class="mb-3">
              <label class="form-label small text-secondary">Дэд бүтцийн зэрэглэл (1..6)</label>
              <select class="form-select bg-dark text-light border-secondary" id="segEditLevel">
                <option value="1" ${seg.infra_level===1?'selected':''}>1 — Тусгаарлагдсан дугуйн зам</option>
                <option value="2" ${seg.infra_level===2?'selected':''}>2 — Холимог ашиглалт</option>
                <option value="3" ${seg.infra_level===3?'selected':''}>3 — Хамгаалалттай эгнээ</option>
                <option value="4" ${seg.infra_level===4?'selected':''}>4 — Тэмдэглэгээт эгнээ</option>
                <option value="5" ${seg.infra_level===5?'selected':''}>5 — Явган хүний зам</option>
                <option value="6" ${seg.infra_level===6?'selected':''}>6 — Дундаа ашиглах зам</option>
              </select>
            </div>
            <input type="hidden" id="segEditId" value="${seg.id}">
            <input type="hidden" id="segEditCond" value="${seg.condition}">
          </div>
          <div class="modal-footer border-secondary">
            <button class="btn btn-secondary" data-bs-dismiss="modal">Цуцлах</button>
            <button class="btn btn-success" onclick="SegmentEdit._save()">
              <i class="bi bi-check-lg me-1"></i>Хадгалах
            </button>
          </div>
        </div>
      </div>`;
    new bootstrap.Modal(modal).show();
  },

  _setCond(c) {
    document.getElementById('segEditCond').value = c;
    document.querySelectorAll('#segEditModal [data-cond]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.cond === c);
    });
  },

  async _save() {
    const id    = document.getElementById('segEditId').value;
    const cond  = document.getElementById('segEditCond').value;
    const level = parseInt(document.getElementById('segEditLevel').value, 10);
    try {
      await API.updateSegment(id, { condition: cond, infra_level: level });
      showToast('success', 'Сегмент шинэчлэгдлээ');
      bootstrap.Modal.getInstance(document.getElementById('segEditModal')).hide();
      loadSegments();
    } catch (e) {
      showToast('danger', e.message);
    }
  },

  async remove(id) {
    if (!confirm('Энэ сегментийг устгах уу?')) return;
    try {
      await API.deleteSegment(id);
      showToast('success', 'Сегмент устгагдлаа');
      loadSegments();
    } catch (e) {
      showToast('danger', e.message);
    }
  },
};

async function loadSegments() {
  try {
    const data = await API.getSegments();
    allSegments = data.results || data;
    renderSegments();
    renderSegmentList();
    const badge = document.getElementById('segCount');
    if (badge) badge.textContent = allSegments.length;
  } catch(e) {
    const el = document.getElementById('segmentList');
    if (el) el.innerHTML = `<div class="alert alert-danger small">${e.message}</div>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const mapEl = document.getElementById('map');
  if (!mapEl) return;
  
  map = L.map('map').setView([47.9167, 106.9167], 13);

  // ─── Custom panes for stacking order ───────────────────────────────
  // Default Leaflet pane z-indices (for reference):
  //   tilePane 200 · overlayPane 400 · markerPane 600 · tooltipPane 650
  // We slot 3 custom panes between overlayPane and markerPane so:
  //   • segments stay BELOW the active route
  //   • route gets a dark "casing" beneath a bright top line (halo effect)
  //   • markers (start/end pins, hazards) stay above everything by default
  const _pane = (name, z, extraClass) => {
    const p = map.createPane(name);
    p.style.zIndex = String(z);
    if (extraClass) p.classList.add(extraClass);
    return p;
  };
  _pane('bm-segments',      410, 'bm-segments-pane');
  _pane('bm-edit-highlight',450, '');                     // road edit selection highlight
  _pane('bm-route-casing',  460, 'bm-route-casing-pane');
  _pane('bm-route-line',    470, 'bm-route-line-pane');

  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    maxZoom: 19,
    subdomains: 'abcd',
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
  }).addTo(map);

  segLayer      = L.layerGroup().addTo(map);
  gpxLayerGroup = L.layerGroup().addTo(map);
  window.gpxLayerGroup = gpxLayerGroup;

  // Init modules
  try { SegmentDraw.init(map); }    catch(e) { console.error('SegmentDraw init:', e); }
  try { POIManager.init(map); }     catch(e) { console.error('POIManager init:', e); }
  try { SmartRoute.init(map); }     catch(e) { console.error('SmartRoute init:', e); }
  try { RoadEditMode.init(map); }   catch(e) { console.error('RoadEditMode init:', e); }

  // Map click dispatch
  map.on('click', e => {
    if (RoadEditMode.isActive())    { RoadEditMode.handleMapClick(e.latlng); return; }
    if (activeTab === 'segment')    { SegmentDraw.handleMapClick(e.latlng); return; }
    if (POIManager.handleMapClick(e.latlng)) return;
    if (SmartRoute.handleMapClick(e.latlng)) return;
  });

  // Filter buttons
  document.querySelectorAll('.bm-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      btn.classList.toggle('active');
      renderSegments();
    });
  });

  // Search
  document.getElementById('segSearch')?.addEventListener('input', e => {
    renderSegmentList(e.target.value);
  });

  loadSegments();
  try { POIManager.loadPOIs(); } catch(e) { console.error('POI load error during init:', e); }
});

window.MapMain = { loadSegments, getSegments: () => allSegments };