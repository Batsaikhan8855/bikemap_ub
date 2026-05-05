const POI_TYPES={danger:'🚨 Аюул',no_bike_lane:'🚫 Зам байхгүй',road_damage:'🛣 Эвдрэл',
  parking_problem:'🅿 Зогсолт',bike_repair:'🔧 Засвар',bike_parking:'🅿 Зогсоол'};
document.addEventListener('DOMContentLoaded',()=>{
  if(!Auth.isLoggedIn()){showToast('warning','Нэвтэрнэ үү');setTimeout(()=>window.location.href='/login/',1200);return;}
  loadDashboard();
});
async function loadDashboard(){
  try{
    const s=await API.getStats();
    document.getElementById('dTotalSegs').textContent=s.total_segments;
    document.getElementById('dTotalPois').textContent=s.total_pois;
    document.getElementById('dPending').textContent=s.pending_pois;
    document.getElementById('dUsers').textContent=s.total_users;
    document.getElementById('dCoverage').textContent=s.bike_lane_coverage+'%';
    const bar=document.getElementById('dCoverageBar');
    if(bar) setTimeout(()=>{bar.style.width=Math.min(parseFloat(s.bike_lane_coverage)||0,100)+'%';},50);
    document.getElementById('pendingBadge').textContent=s.pending_pois;
  }catch(e){showToast('danger','Stats алдаа: '+e.message);}
  try{
    const pois=await API.getPendingPOIs();
    renderPending(pois.results||pois);
  }catch(e){showToast('danger',e.message);}
  try{
    const users=await API.getUsers();
    renderUsers(users.results||users);
  }catch(e){showToast('warning','Хэрэглэгч: '+e.message);}
}
function renderPending(pois){
  const tb=document.getElementById('pendingTbody');
  if(!pois.length){tb.innerHTML='<tr><td colspan="6" class="text-center text-secondary py-3">Хүлээгдэж буй POI байхгүй</td></tr>';return;}
  tb.innerHTML=pois.map(p=>`<tr>
    <td class="text-secondary">#${p.id}</td>
    <td>${POI_TYPES[p.poi_type]||p.poi_type}</td>
    <td class="small text-secondary">${parseFloat(p.latitude).toFixed(4)}, ${parseFloat(p.longitude).toFixed(4)}</td>
    <td class="small">${p.user?.username||'—'}</td>
    <td class="small text-secondary">${new Date(p.created_at).toLocaleDateString()}</td>
    <td><div class="d-flex gap-1">
      <button class="btn btn-outline-success btn-sm py-0 px-2" style="font-size:.7rem" onclick="approvePOI(${p.id},this)">Батлах</button>
      <button class="btn btn-outline-danger btn-sm py-0 px-2" style="font-size:.7rem" onclick="rejectPOI(${p.id},this)">Татгалзах</button>
    </div></td>
  </tr>`).join('');
}
function renderUsers(users){
  const tb=document.getElementById('userTbody');
  tb.innerHTML=users.map(u=>`<tr>
    <td class="text-secondary">#${u.id}</td>
    <td class="fw-semibold">@${u.username}</td>
    <td><span class="badge bg-secondary">${u.role}</span></td>
    <td>${u.total_distance_km?.toFixed(1)||0}</td>
    <td>${u.total_pois||0}</td>
    <td class="small text-secondary">${new Date(u.created_at).toLocaleDateString()}</td>
    <td><button class="btn btn-outline-warning btn-sm py-0 px-2" style="font-size:.7rem" onclick="banUser(${u.id},this)">
      ${u.is_banned?'Unban':'Ban'}
    </button></td>
  </tr>`).join('');
}
async function approvePOI(id,btn){
  btn.disabled=true;
  try{await API.approvePOI(id);showToast('success','POI батлагдлаа!');btn.closest('tr').style.opacity='.4';setTimeout(()=>{btn.closest('tr').remove();loadDashboard();},500);}
  catch(e){showToast('danger',e.message);btn.disabled=false;}
}
async function rejectPOI(id,btn){
  const reason=prompt('Татгалзах шалтгаан:');
  if(!reason)return;
  btn.disabled=true;
  try{await API.rejectPOI(id,reason);showToast('warning','Татгалзлаа.');btn.closest('tr').style.opacity='.4';setTimeout(()=>{btn.closest('tr').remove();loadDashboard();},500);}
  catch(e){showToast('danger',e.message);btn.disabled=false;}
}
async function banUser(id,btn){
  btn.disabled=true;
  try{const r=await API.banUser(id);showToast('info',r.is_banned?`@${r.username} ban хийгдлээ`:`@${r.username} unban хийгдлээ`);loadDashboard();}
  catch(e){showToast('danger',e.message);btn.disabled=false;}
}
function exportCSV(type){API.exportCSV(type);}