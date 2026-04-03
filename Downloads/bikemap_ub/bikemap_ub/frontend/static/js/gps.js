/**
 * GPS Route Tracking — E1 US-001 US-002 US-003
 * Route is stored in browser session ONLY (not in DB).
 */
const GPS = {
  watchId:    null,
  coords:     [],   // [{lat, lng, timestamp}]
  startTime:  null,
  timerInterval: null,
  routeLayer: null,

  start() {
    if (!Auth.isLoggedIn()) {
      showToast('warning','GPS ашиглахын тулд нэвтэрнэ үү.');
      setTimeout(()=>window.location.href='/login/',1200); return;
    }
    if (!navigator.geolocation) {
      showToast('danger','Энэ төхөөрөмж GPS дэмждэггүй.'); return;
    }
    this.coords = []; this.startTime = Date.now();

    // Update UI
    document.getElementById('btnStartRoute')?.classList.add('d-none');
    document.getElementById('btnStopRoute')?.classList.remove('d-none');
    document.getElementById('gpsBanner')?.classList.remove('d-none');

    // Start watch
    this.watchId = navigator.geolocation.watchPosition(
      pos => this._onPosition(pos),
      err => showToast('danger', `GPS алдаа: ${err.message}`),
      { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 }
    );

    // Timer
    this.timerInterval = setInterval(()=>this._updateTimer(), 1000);
    showToast('success','GPS бичлэг эхэллээ 🚲');
  },

  _onPosition(pos) {
    const { latitude: lat, longitude: lng } = pos.coords;
    const timestamp = new Date().toISOString();
    this.coords.push({ lat, lng, timestamp });

    // Draw on map
    if (window.gpxLayerGroup) {
      window.gpxLayerGroup.clearLayers();
      if (this.coords.length > 1) {
        const latlngs = this.coords.map(c=>[c.lat, c.lng]);
        L.polyline(latlngs, {color:'#22c55e', weight:4, opacity:.8}).addTo(window.gpxLayerGroup);
      }
    }

    // Update km
    const km = this._calcDistance();
    document.getElementById('routeKm').textContent    = km.toFixed(2);
    document.getElementById('routePoints').textContent = this.coords.length;
    document.getElementById('gpsBannerDist').textContent = km.toFixed(2)+' км';
  },

  _calcDistance() {
    let d = 0;
    for (let i=1; i<this.coords.length; i++) {
      d += this._haversine(this.coords[i-1], this.coords[i]);
    }
    return d;
  },

  _haversine(a, b) {
    const R=6371, dLat=(b.lat-a.lat)*Math.PI/180, dLng=(b.lng-a.lng)*Math.PI/180;
    const x = Math.sin(dLat/2)**2 + Math.cos(a.lat*Math.PI/180)*Math.cos(b.lat*Math.PI/180)*Math.sin(dLng/2)**2;
    return R * 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1-x));
  },

  _updateTimer() {
    const elapsed = Math.floor((Date.now()-this.startTime)/1000);
    const m=String(Math.floor(elapsed/60)).padStart(2,'0');
    const s=String(elapsed%60).padStart(2,'0');
    document.getElementById('routeTime').textContent = `${m}:${s}`;
    document.getElementById('gpsBannerTime').textContent = `${m}:${s}`;
  },

  stop() {
    if (this.watchId !== null) navigator.geolocation.clearWatch(this.watchId);
    clearInterval(this.timerInterval);
    this.watchId = null;

    document.getElementById('btnStopRoute')?.classList.add('d-none');
    document.getElementById('btnStartRoute')?.classList.remove('d-none');
    document.getElementById('gpsBanner')?.classList.add('d-none');
    document.getElementById('btnGPXExport')?.classList.remove('d-none');

    const km = this._calcDistance();
    showToast('info', `Route дуусгалаа — ${km.toFixed(2)} км явлаа!`);

    // Record distance in user profile (US-060)
    if (km > 0 && Auth.isLoggedIn()) {
      API.recordDistance(km).catch(()=>{});
    }
  },

  async exportGPX() {
    if (!this.coords.length) { showToast('warning','Координат байхгүй.'); return; }
    try {
      const res = await fetch('/api/routes/gpx-export/', {
        method:'POST',
        headers:{
          'Content-Type':'application/json',
          'Authorization':`Bearer ${Auth.getAccess()}`
        },
        body: JSON.stringify({
          coordinates: this.coords,
          distance_km: this._calcDistance(),
        }),
      });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href = url; a.download = 'bikemap_route.gpx'; a.click();
      URL.revokeObjectURL(url);
      showToast('success','GPX файл татагдлаа!');
    } catch(e) { showToast('danger', e.message); }
  },
};