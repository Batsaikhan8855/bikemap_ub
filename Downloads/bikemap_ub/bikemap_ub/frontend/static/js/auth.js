/**
 * auth.js — Authentication helpers
 * JWT-ийг httpOnly cookie-д хадгална (XSS-аас хамгаалсан).
 * localStorage-д зөвхөн мэдрэмжгүй хэрэглэгчийн мэдээлэл ({id, username, role}) хадгалагдана.
 */
const API_BASE = '/api';

// ── CSRF helper ────────────────────────────────────────────────────────────────
function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

const Auth = {
  // Only store non-sensitive user info in localStorage
  saveUser(user) {
    localStorage.setItem('bm_user', JSON.stringify(user));
  },
  clearUser() {
    localStorage.removeItem('bm_user');
  },
  getUser() {
    const u = localStorage.getItem('bm_user');
    return u ? JSON.parse(u) : null;
  },
  isLoggedIn() {
    return !!this.getUser();
  },

  async refresh() {
    // Refresh token is in httpOnly cookie — no body needed
    const res = await fetch(`${API_BASE}/auth/refresh/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
      credentials: 'same-origin',
    });
    if (!res.ok) { this.clearUser(); throw new Error('Session expired'); }
    // New access cookie is set by server automatically
  },

  async login(email, password) {
    const res = await fetch(`${API_BASE}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify({ email, password }),
      credentials: 'same-origin',
    });
    const d = await res.json();
    if (!res.ok) throw new Error(d.error || 'Login failed');
    this.saveUser(d.user);
    return d;
  },

  async register(form) {
    const res = await fetch(`${API_BASE}/auth/register/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
      body: JSON.stringify(form),
      credentials: 'same-origin',
    });
    const d = await res.json();
    if (!res.ok) throw new Error(Object.values(d).flat().join(' '));
    this.saveUser(d.user);
    return d;
  },

  async logout() {
    await fetch(`${API_BASE}/auth/logout/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
      credentials: 'same-origin',
    }).catch(() => {});
    this.clearUser();
    window.location.href = '/login/';
  },

  // Backward-compat shim — some pages call Auth.getAccess() to check login state
  getAccess() { return this.isLoggedIn() ? 'cookie' : null; },
};

const AuthState = {
  init() {
    const user    = Auth.getUser();
    const guest   = document.getElementById('navGuest');
    const userEl  = document.getElementById('navUser');
    const unEl    = document.getElementById('navUsername');
    const adminNav = document.getElementById('navAdmin');
    const profNav  = document.getElementById('navProfile');
    const gpxNav   = document.getElementById('navGpxImport');
    if (user) {
      if (guest)   guest.style.display   = 'none';
      if (userEl)  userEl.style.display  = 'flex';
      if (unEl)    unEl.textContent      = `@${user.username}`;
      if (profNav) profNav.style.display = 'block';
      if (gpxNav)  gpxNav.style.display  = 'block';
      if (adminNav && ['admin', 'moderator'].includes(user.role))
        adminNav.style.display = 'block';
    } else {
      if (guest)  guest.style.display  = 'flex';
      if (userEl) userEl.style.display = 'none';
    }
  },
};

function showToast(type, msg) {
  const c = document.getElementById('toastContainer');
  if (!c) return;
  const id = 't' + Date.now();
  const colors = {
    success: 'bg-success',
    danger:  'bg-danger',
    warning: 'bg-warning text-dark',
    info:    'bg-info text-dark',
  };
  c.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="toast align-items-center ${colors[type] || 'bg-secondary'} border-0 show" role="alert">
      <div class="d-flex">
        <div class="toast-body fw-semibold">${msg}</div>
        <button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`);
  setTimeout(() => document.getElementById(id)?.remove(), 3500);
}
