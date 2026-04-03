/**
 * map.js — Main Leaflet map initialisation & coordination
 */
const COND_COLORS = {green:'#22c55e', yellow:'#f59e0b', red:'#ef4444', none:'#4a5568'};
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
    const color = COND_COLORS[seg.condition]||'#4a5568';
    L.polyline([
      [parseFloat(seg.start_lat), parseFloat(seg.start_lng)],
      [parseFloat(seg.end_lat),   parseFloat(seg.end_lng)],
    ], {color, weight:5, opacity:.8})
    .bindTooltip(`<strong>${seg.condition.toUpperCase()}</strong> · Зэрэглэл ${seg.infra_level}`)
    .addTo(segLayer);
  });
}

function renderSegmentList(q='') {
  const filters = activeCondFilters();
  const ql = q.toLowerCase();
  const items = allSegments.filter(s =>
    filters.includes(s.condition)
  );
  const el = document.getElementById('segmentList');
  if (!items.length) {
    el.innerHTML='<p class="text-secondary small text-center py-3">Сегмент олдсонгүй.</p>';
    return;
  }
  const labels = {green:'🟢 Дугуйн зам', yellow:'🟡 Боломжтой', red:'🔴 Боломжгүй'};
  el.innerHTML = items.map(s=>`
    <div class="card bg-dark border-secondary mb-2 bm-segment-card ${s.condition}" style="cursor:pointer"
         onclick="map.setView([${s.start_lat},${s.start_lng}],15)">
      <div class="card-body py-2 px-3">
        <div class="d-flex justify-content-between align-items-center">
          <span class="small fw-semibold">${labels[s.condition]||s.condition}</span>
          <span class="text-secondary" style="font-size:.7rem">Lvl ${s.infra_level}</span>
        </div>
        <div class="text-secondary" style="font-size:.7rem">${s.user?.username||'—'} · ${new Date(s.created_at).toLocaleDateString()}</div>
      </div>
    </div>`).join('');
}

async function loadSegments() {
  try {
    const data = await API.getSegments();
    allSegments = data.results || data;
    renderSegments();
    renderSegmentList();
  } catch(e) {
    const el = document.getElementById('segmentList');
    if (el) el.innerHTML = `<div class="alert alert-danger small">${e.message}</div>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const mapEl = document.getElementById('map');
  if (!mapEl) return;
  
  map = L.map('map').setView([47.9167, 106.9167], 13);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom:19, attribution:'© OpenStreetMap'
  }).addTo(map);

  segLayer      = L.layerGroup().addTo(map);
  gpxLayerGroup = L.layerGroup().addTo(map);
  window.gpxLayerGroup = gpxLayerGroup;

  // Init modules
  try { SegmentDraw.init(map); } catch(e) { console.error('SegmentDraw init error:', e); }
  try { POIManager.init(map); } catch(e) { console.error('POIManager init error:', e); }
  try { SmartRoute.init(map); } catch(e) { console.error('SmartRoute init error:', e); }

  // Map click dispatch
  map.on('click', e => {
    if (activeTab === 'segment') { SegmentDraw.handleMapClick(e.latlng); return; }
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

window.MapMain = { loadSegments };