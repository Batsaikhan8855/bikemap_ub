const API_BASE = '/api';
const Auth = {
  save(access, refresh, user) {
    localStorage.setItem('bm_access', access);
    localStorage.setItem('bm_refresh', refresh);
    localStorage.setItem('bm_user', JSON.stringify(user));
  },
  clear() { ['bm_access','bm_refresh','bm_user'].forEach(k=>localStorage.removeItem(k)); },
  getAccess() { return localStorage.getItem('bm_access'); },
  getUser() { const u=localStorage.getItem('bm_user'); return u?JSON.parse(u):null; },
  isLoggedIn() { return !!this.getAccess(); },
  async refresh() {
    const refresh = localStorage.getItem('bm_refresh');
    if (!refresh) throw new Error('No refresh token');
    const res = await fetch(`${API_BASE}/auth/refresh/`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({refresh}),
    });
    if (!res.ok) { this.clear(); throw new Error('Session expired'); }
    const d = await res.json();
    localStorage.setItem('bm_access', d.access);
    return d.access;
  },
  async login(email, password) {
    const res = await fetch(`${API_BASE}/auth/login/`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email, password}),
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Login failed');
    this.save(d.access, d.refresh, d.user); return d;
  },
  async register(form) {
    const res = await fetch(`${API_BASE}/auth/register/`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(form),
    });
    const d = await res.json();
    if (!res.ok) throw new Error(Object.values(d).flat().join(' '));
    this.save(d.access, d.refresh, d.user); return d;
  },
  async logout() {
    const refresh = localStorage.getItem('bm_refresh');
    if (refresh && this.getAccess()) {
      await fetch(`${API_BASE}/auth/logout/`, {
        method:'POST', headers:{'Content-Type':'application/json','Authorization':`Bearer ${this.getAccess()}`},
        body: JSON.stringify({refresh}),
      }).catch(()=>{});
    }
    this.clear(); window.location.href='/login/';
  },
};
const AuthState = {
  init() {
    const user = Auth.getUser();
    const guest=document.getElementById('navGuest');
    const userEl=document.getElementById('navUser');
    const unEl=document.getElementById('navUsername');
    const adminNav=document.getElementById('navAdmin');
    const profNav=document.getElementById('navProfile');
    if (user) {
      if(guest)  guest.style.display='none';
      if(userEl) userEl.style.display='flex';
      if(unEl)   unEl.textContent=`@${user.username}`;
      if(profNav) profNav.style.display='block';
      if(adminNav && ['admin','moderator'].includes(user.role)) adminNav.style.display='block';
    } else {
      if(guest)  guest.style.display='flex';
      if(userEl) userEl.style.display='none';
    }
  },
};
function showToast(type, msg) {
  const c=document.getElementById('toastContainer');
  if(!c) return;
  const id='t'+Date.now();
  const colors={success:'bg-success',danger:'bg-danger',warning:'bg-warning text-dark',info:'bg-info text-dark'};
  c.insertAdjacentHTML('beforeend',`
    <div id="${id}" class="toast align-items-center ${colors[type]||'bg-secondary'} border-0 show" role="alert">
      <div class="d-flex">
        <div class="toast-body fw-semibold">${msg}</div>
        <button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`);
  setTimeout(()=>document.getElementById(id)?.remove(), 3500);
}