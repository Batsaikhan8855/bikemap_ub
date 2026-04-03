/**
 * POI management — E3 US-020 US-021 US-022 US-023
 */
const POIManager = {
  poiModal: null,
  pickingCoord: false,
  pendingLat: null, pendingLng: null,
  selectedType: null,
  poiLayer: null,

  POI_COLORS: {
    danger:'#ef4444', no_bike_lane:'#f97316',
    road_damage:'#eab308', parking_problem:'#6366f1',
    bike_repair:'#22c55e', bike_parking:'#06b6d4',
  },
  POI_ICONS: {
    danger:'🚨', no_bike_lane:'🚫', road_damage:'🛣',
    parking_problem:'🅿', bike_repair:'🔧', bike_parking:'🅿',
  },

  init(map) {
    this.map = map;
    this.poiLayer = L.layerGroup().addTo(map);  

    // DO NOT initialize modal here - just bind button listeners
    const typeButtons = document.querySelectorAll('.bm-poi-type');
    typeButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.bm-poi-type').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        this.selectedType = btn.dataset.type;
      });
    });
  },

  startPicking() {
    this.pickingCoord = true;
    this.map.getContainer().style.cursor = 'crosshair';
    showToast('info','Газрын зурагт байршил дарна уу');
  },

  handleMapClick(latlng) {
    if (!this.pickingCoord) return false;
    this.pendingLat = latlng.lat;
    this.pendingLng = latlng.lng;
    this.pickingCoord = false;
    this.map.getContainer().style.cursor = '';
    const alert = document.getElementById('poiCoordAlert');
    if (alert) alert.innerHTML =
      `<i class="bi bi-check-circle-fill text-success me-1"></i>Байршил: ${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`;
    this._showModal();
    return true;
  },

  _showModal() {
    // Lazy initialize modal only when needed
    if (!this.poiModal) {
      const poiEl = document.getElementById('poiModal');
      if (!poiEl) {
        showToast('danger', 'Modal элемент олдсонгүй');
        return;
      }
      try {
        this.poiModal = new bootstrap.Modal(poiEl, {backdrop: 'static', keyboard: false});
      } catch(e) {
        console.error('Modal init error:', e);
        showToast('danger', 'Modal үүсгэх алдаа');
        return;
      }
    }
    if (this.poiModal && typeof this.poiModal.show === 'function') {
      this.poiModal.show();
    }
  },

  async submit() {
    if (!Auth.isLoggedIn()) { showToast('warning','Нэвтэрнэ үү'); return; }
    if (!this.selectedType) { showToast('warning','POI төрөл сонгоно уу'); return; }
    if (!this.pendingLat)   { showToast('warning','Байршил сонгоно уу'); return; }

    const form = new FormData();
    form.append('latitude',   this.pendingLat);
    form.append('longitude',  this.pendingLng);
    form.append('poi_type',   this.selectedType);
    form.append('description',document.getElementById('poiDesc')?.value || '');
    const imgFile = document.getElementById('poiImage')?.files[0];
    if (imgFile) {
      if (imgFile.size > 5*1024*1024) { showToast('danger','Зураг 5MB-аас ихгүй байна'); return; }
      form.append('image', imgFile);
    }
    try {
      await API.createPOI(form);
      if (this.poiModal && typeof this.poiModal.hide === 'function') {
        this.poiModal.hide();
      }
      showToast('success','POI илгээгдлээ! Батлагдахыг хүлээнэ.');
      this.selectedType=null; this.pendingLat=null; this.pendingLng=null;
      document.querySelectorAll('.bm-poi-type').forEach(b=>b.classList.remove('active'));
      const poiDescEl = document.getElementById('poiDesc');
      if (poiDescEl) poiDescEl.value='';
      await this.loadPOIs();
    } catch(e) { showToast('danger', e.message); }
  },

  async loadPOIs() {
    this.poiLayer.clearLayers();
    try {
      const data = await API.getPOIs({status:'approved'});
      const pois = data.results || data;
      // Cluster by proximity — US-021
      const clusters = this._cluster(pois);
      clusters.forEach(cluster => {
        if (cluster.length >= 3) {
          // Dense zone — show pulsing circle
          const center = this._centroid(cluster);
          const radius = Math.min(20 + cluster.length*4, 60);
          L.circle(center, {radius, color:'#ef4444', fillColor:'#ef4444', fillOpacity:.2, weight:2})
           .bindTooltip(`${cluster.length} аюулын цэг`)
           .addTo(this.poiLayer);
        }
        cluster.forEach(poi => this._addMarker(poi));
      });
    } catch(e) { console.error('POI load error', e); }
  },

  _addMarker(poi) {
    const color = this.POI_COLORS[poi.poi_type] || '#888';
    const icon  = this.POI_ICONS[poi.poi_type]  || '?';
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 28 36" width="28" height="36">
      <path d="M14 0C6.27 0 0 6.27 0 14c0 8.5 14 22 14 22S28 22.5 28 14C28 6.27 21.73 0 14 0z" fill="${color}" opacity=".9"/>
      <text x="14" y="19" text-anchor="middle" font-size="13">${icon}</text>
    </svg>`;
    const leafIcon = L.divIcon({html:svg,className:'',iconSize:[28,36],iconAnchor:[14,36],popupAnchor:[0,-36]});
    L.marker([parseFloat(poi.latitude), parseFloat(poi.longitude)], {icon:leafIcon})
     .bindPopup(this._popupHTML(poi))
     .addTo(this.poiLayer);
  },

  _popupHTML(poi) {
    const color = this.POI_COLORS[poi.poi_type]||'#888';
    const img   = poi.image ? `<img src="${poi.image}" class="img-fluid rounded mb-2" style="max-height:120px">` : '';
    return `<div style="min-width:190px">
      <strong>${this.POI_ICONS[poi.poi_type]||''} ${poi.poi_type.replace(/_/g,' ').toUpperCase()}</strong>
      ${img}
      <p class="mb-1 small">${poi.description||''}</p>
      <div class="d-flex gap-1">
        <button class="btn btn-outline-success btn-sm py-0 px-1" onclick="POIManager.vote(${poi.id},'up')">▲ ${poi.upvotes}</button>
        <button class="btn btn-outline-danger btn-sm py-0 px-1" onclick="POIManager.vote(${poi.id},'down')">▼ ${poi.downvotes}</button>
      </div>
    </div>`;
  },

  async vote(id, type) {
    if (!Auth.isLoggedIn()) { showToast('warning','Нэвтэрнэ үү'); return; }
    try {
      await API.votePOI(id, type);
      showToast('success','Санал бүртгэгдлээ!');
      await this.loadPOIs();
    } catch(e) { showToast('danger', e.message); }
  },

  _cluster(pois) {
    // Simple proximity clustering (radius ~100m)
    const used = new Set(), clusters = [];
    for (let i=0; i<pois.length; i++) {
      if (used.has(i)) continue;
      const cluster = [pois[i]];
      used.add(i);
      for (let j=i+1; j<pois.length; j++) {
        if (used.has(j)) continue;
        const dlat = Math.abs(parseFloat(pois[i].latitude)-parseFloat(pois[j].latitude));
        const dlng = Math.abs(parseFloat(pois[i].longitude)-parseFloat(pois[j].longitude));
        if (dlat<0.001 && dlng<0.001) { cluster.push(pois[j]); used.add(j); }
      }
      clusters.push(cluster);
    }
    return clusters;
  },

  _centroid(pois) {
    const lat = pois.reduce((s,p)=>s+parseFloat(p.latitude),0)/pois.length;
    const lng = pois.reduce((s,p)=>s+parseFloat(p.longitude),0)/pois.length;
    return [lat, lng];
  },
};

function openPOIModal() {
  if (!Auth.isLoggedIn()) {
    showToast('warning','POI нэмэхийн тулд нэвтэрнэ үү');
    setTimeout(()=>window.location.href='/login/',1200); return;
  }
  POIManager.startPicking();
}