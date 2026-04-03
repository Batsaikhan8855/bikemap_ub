document.addEventListener('DOMContentLoaded',async()=>{
  const user=Auth.getUser();
  if(!user){window.location.href='/login/';return;}
  document.getElementById('profUsername').textContent=user.username;
  document.getElementById('profRole').textContent=user.role;
  document.getElementById('profAvatar').textContent=user.username.charAt(0).toUpperCase();
  try{
    const p=await API.get('/auth/profile/');
    document.getElementById('profKm').textContent=(p.total_distance_km||0).toFixed(1);
    document.getElementById('profPois').textContent=p.total_pois||0;
    document.getElementById('profSegs').textContent=p.total_segments||0;
  }catch(e){showToast('danger',e.message);}
  try{
    const pois=await API.getPOIs({});
    const data=pois.results||pois;
    const myPOIs=data.filter(p=>p.user?.id===user.id);
    const el=document.getElementById('myPOIList');
    const POI_ICONS={danger:'🚨',no_bike_lane:'🚫',road_damage:'🛣',parking_problem:'🅿',bike_repair:'🔧',bike_parking:'🅿'};
    if(!myPOIs.length){el.innerHTML='<p class="text-secondary small py-3 text-center">POI байхгүй</p>';return;}
    el.innerHTML=`<table class="table table-dark table-sm mb-0 small"><thead><tr>
      <th class="text-secondary">Төрөл</th><th class="text-secondary">Статус</th><th class="text-secondary">Огноо</th>
    </tr></thead><tbody>${myPOIs.map(p=>`<tr>
      <td>${POI_ICONS[p.poi_type]||''} ${p.poi_type}</td>
      <td><span class="badge ${p.status==='approved'?'bg-success':p.status==='pending'?'bg-warning text-dark':'bg-danger'}">${p.status}</span></td>
      <td>${new Date(p.created_at).toLocaleDateString()}</td>
    </tr>`).join('')}</tbody></table>`;
  }catch(e){}
});