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

  _renderRoute(data) {
    this.routeLayer.clearLayers();
    const COLORS = {green:'#22c55e',yellow:'#f59e0b',red:'#ef4444',unknown:'#6e7681'};
    // Draw segments with colour
    if (data.segments?.length) {
      data.segments.forEach(seg => {
        const color = COLORS[seg.colour]||COLORS.unknown;
        L.polyline([[seg.from[1],seg.from[0]],[seg.to[1],seg.to[0]]],
          {color,weight:5,opacity:.85}).addTo(this.routeLayer);
      });
    } else if (data.coordinates?.length) {
      const lls = data.coordinates.map(c=>[c[1],c[0]]);
      L.polyline(lls,{color:'#22c55e',weight:5}).addTo(this.routeLayer);
    }
    // Hazard markers
    (data.hazards||[]).forEach(h => {
      L.circleMarker([h.lat,h.lng],{radius:8,color:'#ef4444',fillColor:'#ef4444',fillOpacity:.5})
       .bindTooltip(`⚠ ${h.poi_type}`)
       .addTo(this.routeLayer);
    });
  },

  clear() {
    this.routeLayer?.clearLayers();
    this.startMarker?.remove(); this.endMarker?.remove();
    this.startMarker=null; this.endMarker=null;
    document.getElementById('routeStart').value='';
    document.getElementById('routeEnd').value='';
    delete document.getElementById('routeStart').dataset.lat;
    delete document.getElementById('routeEnd').dataset.lat;
  },
};