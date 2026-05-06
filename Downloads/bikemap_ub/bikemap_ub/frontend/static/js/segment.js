/**
 * Segment drawing & tagging — E2 US-010 US-011 US-012 US-013
 */
const SegmentDraw = {
  startPt: null, endPt: null, selectedCond: null,
  drawLayer: null,
  snappedGeometry: null,   // [{lat, lng}, ...] from OSRM /match
  _snapping: false,

  init(map) {
    this.map = map;
    this.drawLayer = L.layerGroup().addTo(map);

    document.querySelectorAll('.bm-cond-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.bm-cond-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.selectedCond = btn.dataset.cond;
        this._redraw();
        this._updateSaveBtn();
      });
    });
  },

  handleMapClick(latlng) {
    if (!this.startPt) {
      this.startPt = latlng;
      document.getElementById('seg_start_lbl').textContent =
        `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`;
      this.snappedGeometry = null;
      this._redraw();
    } else if (!this.endPt) {
      this.endPt = latlng;
      document.getElementById('seg_end_lbl').textContent =
        `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`;
      this._redraw();           // straight-line preview
      // Snap-to-road зөвхөн toggle-ийг идэвхжүүлсэн үед ажилла.
      const snapToggle = document.getElementById('snapToRoadToggle');
      if (snapToggle && snapToggle.checked) {
        this._snapToRoad();
      }
      this._updateSaveBtn();
    }
  },

  async _snapToRoad() {
    if (!this.startPt || !this.endPt) return;
    this._snapping = true;
    this._updateSaveBtn();
    try {
      const result = await API.snapToRoad([
        { lat: parseFloat(this.startPt.lat.toFixed(6)), lng: parseFloat(this.startPt.lng.toFixed(6)) },
        { lat: parseFloat(this.endPt.lat.toFixed(6)),   lng: parseFloat(this.endPt.lng.toFixed(6))   },
      ]);
      this.snappedGeometry = result.geometry;   // [{lat, lng}, ...]
      if (result.source === 'osrm') {
        showToast('info', `Зам дагуу тохируулагдлаа (${result.geometry.length} цэг)`);
      }
    } catch (e) {
      this.snappedGeometry = null;              // fallback: straight line on save
    } finally {
      this._snapping = false;
      this._redraw();
      this._updateSaveBtn();
    }
  },

  _redraw() {
    this.drawLayer.clearLayers();
    const colors = { green: '#22c55e', yellow: '#f59e0b', red: '#ef4444', null: '#6e7681' };
    const c = colors[this.selectedCond] || colors.null;

    if (this.startPt) {
      L.circleMarker(this.startPt, { radius: 7, color: c, fillColor: c, fillOpacity: .9 })
        .addTo(this.drawLayer);
    }

    if (this.startPt && this.endPt) {
      if (this.snappedGeometry && this.snappedGeometry.length >= 2) {
        // Road-snapped polyline — solid line
        const latlngs = this.snappedGeometry.map(p => [p.lat, p.lng]);
        L.polyline(latlngs, { color: c, weight: 5, opacity: 0.9, lineCap: 'round' })
          .addTo(this.drawLayer);
      } else {
        // Straight-line draft (before snap result or OSRM unavailable)
        L.polyline([this.startPt, this.endPt], { color: c, weight: 5, dashArray: '6 4', opacity: 0.7 })
          .addTo(this.drawLayer);
      }
    }

    if (this.endPt) {
      L.circleMarker(this.endPt, { radius: 7, color: c, fillColor: c, fillOpacity: .9 })
        .addTo(this.drawLayer);
    }
  },

  _updateSaveBtn() {
    const btn = document.getElementById('btnSaveSegment');
    if (!btn) return;
    btn.disabled = !(this.startPt && this.endPt && this.selectedCond && !this._snapping);
    btn.textContent = this._snapping ? 'Замд тохируулж байна…' : 'Хадгалах';
  },

  async save() {
    if (!Auth.isLoggedIn()) { showToast('warning', 'Нэвтэрнэ үү'); return; }
    if (!this.startPt || !this.endPt || !this.selectedCond) return;
    const infraLevel = parseInt(document.getElementById('infraLevel')?.value || 4);

    const payload = {
      start_lat:   parseFloat(this.startPt.lat.toFixed(6)),
      start_lng:   parseFloat(this.startPt.lng.toFixed(6)),
      end_lat:     parseFloat(this.endPt.lat.toFixed(6)),
      end_lng:     parseFloat(this.endPt.lng.toFixed(6)),
      condition:   this.selectedCond,
      infra_level: infraLevel,
      is_created:  true,
      geometry:    this.snappedGeometry || null,
    };

    try {
      await API.createSegment(payload);
      showToast('success', 'Сегмент хадгалагдлаа ✓');
      this.reset();
      if (window.MapMain) window.MapMain.loadSegments();
    } catch (e) {
      showToast('danger', e.message);
    }
  },

  reset() {
    this.startPt = null; this.endPt = null; this.selectedCond = null;
    this.snappedGeometry = null; this._snapping = false;
    this.drawLayer?.clearLayers();
    const sl = document.getElementById('seg_start_lbl');
    const el = document.getElementById('seg_end_lbl');
    if (sl) sl.textContent = '—';
    if (el) el.textContent = '—';
    document.querySelectorAll('.bm-cond-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById('btnSaveSegment');
    if (btn) { btn.disabled = true; btn.textContent = 'Хадгалах'; }
  },
};
