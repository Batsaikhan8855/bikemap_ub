const POI_ICONS = {
  danger:          '🚨',
  no_bike_lane:    '🚫',
  road_damage:     '🛣',
  parking_problem: '🚗',
  bike_repair:     '🔧',
  bike_parking:    '🅿',
};
const POI_LABELS = {
  danger:          'Аюулын бүс',
  no_bike_lane:    'Дугуйн зам байхгүй',
  road_damage:     'Замын эвдрэл',
  parking_problem: 'Зогсолтын асуудал',
  bike_repair:     'Засварын цэг',
  bike_parking:    'Дугуй зогсоол',
};

document.addEventListener('DOMContentLoaded', async () => {
  const user = Auth.getUser();
  if (!user) { window.location.href = '/login/'; return; }

  document.getElementById('profUsername').textContent = user.username;
  document.getElementById('profRole').textContent = user.role;
  document.getElementById('profAvatar').textContent = user.username.charAt(0).toUpperCase();

  // Role badge styling
  const badge = document.getElementById('profRoleBadge');
  if (badge) {
    badge.className = `bm-role-badge ${user.role}`;
    const icons = { cyclist: 'bi-bicycle', moderator: 'bi-shield-check', admin: 'bi-star-fill' };
    badge.querySelector('i').className = `bi ${icons[user.role] || 'bi-person'}`;
  }

  try {
    const p = await API.get('/auth/profile/');
    document.getElementById('profKm').textContent = (p.total_distance_km || 0).toFixed(1);
    document.getElementById('profPois').textContent = p.total_pois || 0;
    document.getElementById('profSegs').textContent = p.total_segments || 0;
  } catch (e) {
    showToast('danger', e.message);
  }

  try {
    const pois = await API.getPOIs({});
    const data = pois.results || pois;
    const myPOIs = data.filter(p => p.user?.id === user.id);
    const el = document.getElementById('myPOIList');
    const badge = document.getElementById('myPoiCount');
    if (badge) badge.textContent = myPOIs.length;

    if (!myPOIs.length) {
      el.innerHTML = `
        <div class="bm-empty py-4">
          <div class="bm-empty-icon"><i class="bi bi-pin-map"></i></div>
          <span>POI байхгүй байна</span>
        </div>`;
      return;
    }

    el.innerHTML = myPOIs.map(p => {
      const statusCls = p.status === 'approved' ? 'bg-success' : p.status === 'pending' ? 'bg-warning text-dark' : 'bg-danger';
      const statusIcon = p.status === 'approved' ? 'bi-check-circle-fill' : p.status === 'pending' ? 'bi-hourglass-split' : 'bi-x-circle-fill';
      return `
        <div class="bm-poi-row">
          <div class="bm-poi-icon-cell">${POI_ICONS[p.poi_type] || '📍'}</div>
          <div class="flex-grow-1 min-w-0">
            <div class="small fw-semibold text-truncate">${POI_LABELS[p.poi_type] || p.poi_type}</div>
            <div class="text-secondary" style="font-size:.7rem">${new Date(p.created_at).toLocaleDateString()}</div>
          </div>
          <span class="badge ${statusCls} d-flex align-items-center gap-1" style="font-size:.68rem">
            <i class="bi ${statusIcon}"></i>${p.status}
          </span>
        </div>`;
    }).join('');
  } catch (e) {}
});
