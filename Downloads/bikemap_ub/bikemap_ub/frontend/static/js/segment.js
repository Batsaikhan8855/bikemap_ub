/**
 * Segment drawing & tagging — E2 US-010 US-011 US-012 US-013
 */
const SegmentDraw = {
  startPt: null, endPt: null, selectedCond: null,
  drawLayer: null,

  init(map) {
    this.map = map;
    this.drawLayer = L.layerGroup().addTo(map);

    // Condition buttons
    document.querySelectorAll('.bm-cond-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.bm-cond-btn').forEach(b=>b.classList.remove('active'));
        btn.classList.add('active');
        this.selectedCond = btn.dataset.cond;
        this._updateSaveBtn();
      });
    });
  },

  handleMapClick(latlng) {
    if (!this.startPt) {
      this.startPt = latlng;
      document.getElementById('seg_start_lbl').textContent =
        `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`;
      this._redraw();
    } else if (!this.endPt) {
      this.endPt = latlng;
      document.getElementById('seg_end_lbl').textContent =
        `${latlng.lat.toFixed(4)}, ${latlng.lng.toFixed(4)}`;
      this._redraw();
      this._updateSaveBtn();
    }
  },

  _redraw() {
    this.drawLayer.clearLayers();
    const colors = {green:'#22c55e', yellow:'#f59e0b', red:'#ef4444', null:'#6e7681'};
    const c = colors[this.selectedCond] || colors.null;
    if (this.startPt) L.circleMarker(this.startPt,{radius:6,color:c,fillColor:c,fillOpacity:.9}).addTo(this.drawLayer);
    if (this.startPt && this.endPt)
      L.polyline([this.startPt, this.endPt],{color:c,weight:5,dashArray:'6 4'}).addTo(this.drawLayer);
    if (this.endPt) L.circleMarker(this.endPt,{radius:6,color:c,fillColor:c,fillOpacity:.9}).addTo(this.drawLayer);
  },

  _updateSaveBtn() {
    const btn = document.getElementById('btnSaveSegment');
    if (btn) btn.disabled = !(this.startPt && this.endPt && this.selectedCond);
  },

  async save() {
    if (!Auth.isLoggedIn()) { showToast('warning','Нэвтэрнэ үү'); return; }
    if (!this.startPt || !this.endPt || !this.selectedCond) return;
    const infraLevel = parseInt(document.getElementById('infraLevel')?.value || 4);
    try {
      await API.createSegment({
        start_lat:   parseFloat(this.startPt.lat.toFixed(6)),
        start_lng:   parseFloat(this.startPt.lng.toFixed(6)),
        end_lat:     parseFloat(this.endPt.lat.toFixed(6)),
        end_lng:     parseFloat(this.endPt.lng.toFixed(6)),
        condition:   this.selectedCond,
        infra_level: infraLevel,
        is_created:  true,
      });
      showToast('success','Сегмент хадгалагдлаа ✓');
      this.reset();
      if (window.MapMain) window.MapMain.loadSegments();
    } catch(e) { showToast('danger', e.message); }
  },

  reset() {
    this.startPt=null; this.endPt=null; this.selectedCond=null;
    this.drawLayer?.clearLayers();
    document.getElementById('seg_start_lbl').textContent='—';
    document.getElementById('seg_end_lbl').textContent='—';
    document.querySelectorAll('.bm-cond-btn').forEach(b=>b.classList.remove('active'));
    document.getElementById('btnSaveSegment').disabled=true;
  },
};