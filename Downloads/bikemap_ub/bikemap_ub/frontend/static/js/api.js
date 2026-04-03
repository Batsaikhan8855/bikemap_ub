const API = {
  async request(method, path, body=null, isForm=false) {
    const headers = {};
    let token = Auth.getAccess();
    if (token) headers['Authorization']=`Bearer ${token}`;
    if (!isForm && body) headers['Content-Type']='application/json';
    const opts = {method, headers};
    if (body) opts.body = isForm ? body : JSON.stringify(body);
    let res = await fetch('/api'+path, opts);
    if (res.status===401 && localStorage.getItem('bm_refresh')) {
      try {
        token = await Auth.refresh();
        opts.headers = {...headers, 'Authorization':`Bearer ${token}`};
        res = await fetch('/api'+path, opts);
      } catch { Auth.clear(); window.location.href='/login/'; return; }
    }
    const ct = res.headers.get('content-type')||'';
    const data = ct.includes('json') ? await res.json() : {};
    if (!res.ok) throw new Error(Object.values(data).flat().join(' ')||`HTTP ${res.status}`);
    return data;
  },
  get:      (p)    => API.request('GET',    p),
  post:     (p,b)  => API.request('POST',   p,b),
  patch:    (p,b)  => API.request('PATCH',  p,b),
  delete:   (p)    => API.request('DELETE', p),
  postForm: (p,b)  => API.request('POST',   p,b,true),

  // Segments
  getSegments: (params={}) => API.get('/segments/?'+new URLSearchParams(params)),
  createSegment: d => API.post('/segments/', d),

  // POIs
  getPOIs:     (params={}) => API.get('/pois/?'+new URLSearchParams(params)),
  createPOI:   form => API.postForm('/pois/', form),
  votePOI:     (id,v) => API.post(`/pois/${id}/vote/`, {vote_type:v}),
  approvePOI:  id => API.post(`/pois/${id}/approve/`, {}),
  rejectPOI:   (id,reason) => API.post(`/pois/${id}/reject/`, {reason}),

  // Aggregation
  getAggregation: () => API.get('/aggregation/'),
  getHeatmap:     () => API.get('/aggregation/heatmap/'),

  // Routes
  gpxExport: data => API.post('/routes/gpx-export/', data),
  smartRoute: data => API.post('/routes/smart/', data),
  recordDistance: km => API.post('/routes/record-distance/', {distance_km: km}),

  // Dashboard
  getStats:     () => API.get('/dashboard/stats/'),
  getPendingPOIs:()=> API.get('/dashboard/pending-pois/'),
  getUsers:     () => API.get('/dashboard/users/'),
  banUser:      id => API.post(`/dashboard/users/${id}/ban/`, {}),
  exportCSV: (type,from,to) => {
    let url = `/api/dashboard/export/?type=${type}`;
    if(from) url+=`&from=${from}`;
    if(to)   url+=`&to=${to}`;
    window.open(url,'_blank');
  },
};