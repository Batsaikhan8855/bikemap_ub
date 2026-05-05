const HMAP_COLORS = {green:'#22c55e',yellow:'#f59e0b',red:'#ef4444'};
let hmap, hmapData=[];
document.addEventListener('DOMContentLoaded', async()=>{
  hmap = L.map('heatmap').setView([47.9167,106.9167],13);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    maxZoom: 19, subdomains: 'abcd',
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
  }).addTo(hmap);
  hmapData = await API.getHeatmap().catch(()=>[]);
  renderHeat();
  document.getElementById('heatFilter')?.addEventListener('change', renderHeat);
});
function renderHeat(){
  hmap.eachLayer(l=>{if(l instanceof L.CircleMarker) hmap.removeLayer(l);});
  const f = document.getElementById('heatFilter')?.value||'';
  hmapData.filter(d=>!f||d.dominant===f).forEach(d=>{
    const color=HMAP_COLORS[d.dominant]||'#888';
    const votes=Math.max(1,(d.green_votes||0)+(d.yellow_votes||0)+(d.red_votes||0));
    L.circleMarker([parseFloat(d.start_lat),parseFloat(d.start_lng)],{
      radius:Math.min(8+votes*1.5,30), fillColor:color, fillOpacity:.4, color, weight:1.5, opacity:.7,
    }).bindTooltip(`<b>${d.dominant?.toUpperCase()}</b><br>🟢${d.green_votes||0} 🟡${d.yellow_votes||0} 🔴${d.red_votes||0}`)
    .addTo(hmap);
  });
}