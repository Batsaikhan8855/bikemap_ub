# 🚲 BikeMap UB — v5.0
**Ulaanbaatar Bicycle Safety Crowdsourcing Platform**
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub
cd backend
---

## VS Code Terminal — Хурдан эхлэх

### 1. 
```bash

cd bikemap_ub/backend
code ..    # VS Code-д нээх (заавал биш)
```

### 2. Virtual Environment
```bash
# macOS / Linux
python3 -m venv venv
source venv/bin/activate

# Windows PowerShell
python -m venv venv
venv\Scripts\activate
```

### 3. Package суулгах
```bash
pip install -r requirements.txt
```

### 4. .env файл үүсгэх
```bash
# macOS/Linux
cp env_example.txt .env

# Windows
copy env_example.txt .env
```
`.env` файлд `SECRET_KEY` өөрчилнө:
```
SECRET_KEY=bikemap-secret-change-this-12345
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 5. Migration
```bash
python manage.py makemigrations accounts
python manage.py makemigrations segments
python manage.py makemigrations pois
python manage.py makemigrations aggregation
python manage.py migrate
```

### 6. Admin хэрэглэгч
```bash
python manage.py createsuperuser
```

### 7. Сервер асаах
```bash
python manage.py runserver
```

---

## URLs
| URL | Тайлбар |
|-----|---------|
| http://localhost:8000 | Газрын зураг (Map) |
| http://localhost:8000/register/ | Бүртгүүлэх |
| http://localhost:8000/login/ | Нэвтрэх |
| http://localhost:8000/heatmap/ | Heatmap |
| http://localhost:8000/dashboard/ | Админ дашбоард |
| http://localhost:8000/profile/ | Профайл |
| http://localhost:8000/admin/ | Django Admin |

---

## Architecture

```
bikemap_ub/
├── backend/
│   ├── apps/
│   │   ├── accounts/     # E8 — JWT auth, RBAC, profiles
│   │   ├── segments/     # E2 — Road condition tagging
│   │   ├── pois/         # E3 — POI system (6 types, voting)
│   │   ├── aggregation/  # E4 — Crowd aggregation algorithm
│   │   └── routes/       # E1 + E5 — GPS export + Smart Route (OSRM)
│   ├── config/           # Django settings, URLs
│   └── requirements.txt
├── frontend/
│   ├── templates/
│   │   ├── map/index.html      # Main map + GPS + Segment + POI
│   │   ├── map/heatmap.html    # Aggregated heatmap
│   │   ├── auth/               # Login, Register, Profile
│   │   └── dashboard/          # Admin dashboard
│   └── static/
│       ├── css/main.css
│       └── js/
│           ├── auth.js         # JWT handling
│           ├── api.js          # All API calls
│           ├── gps.js          # GPS tracking (US-001,002,003)
│           ├── segment.js      # Segment drawing (US-010–013)
│           ├── poi.js          # POI placement/voting (US-020–023)
│           ├── smart_route.js  # A→B routing (US-040,041)
│           ├── map.js          # Leaflet map init
│           ├── heatmap.js      # Heatmap viz
│           ├── dashboard.js    # Admin panel
│           └── profile.js      # User profile
```

---

## API Endpoints

### Auth (E8)
| Method | URL | Тайлбар |
|--------|-----|---------|
| POST | /api/auth/register/ | Бүртгүүлэх |
| POST | /api/auth/login/ | Нэвтрэх → JWT |
| POST | /api/auth/refresh/ | Token шинэчлэх |
| POST | /api/auth/logout/ | Гарах |
| GET/PATCH | /api/auth/profile/ | Профайл |

### Segments (E2)
| Method | URL | Тайлбар |
|--------|-----|---------|
| GET | /api/segments/ | Бүх сегмент |
| POST | /api/segments/ | Сегмент үүсгэх |
| PATCH | /api/segments/{id}/ | Нөхцөл засах |
| DELETE | /api/segments/{id}/ | Устгах |

### POIs (E3)
| Method | URL | Тайлбар |
|--------|-----|---------|
| GET | /api/pois/ | Батлагдсан POI-ууд |
| POST | /api/pois/ | POI нэмэх |
| POST | /api/pois/{id}/vote/ | Upvote/Downvote |
| POST | /api/pois/{id}/approve/ | Батлах (mod) |
| POST | /api/pois/{id}/reject/ | Татгалзах (mod) |

### Aggregation (E4)
| Method | URL | Тайлбар |
|--------|-----|---------|
| GET | /api/aggregation/ | Нэгтгэсэн сегментүүд |
| GET | /api/aggregation/heatmap/ | Heatmap өгөгдөл |

### Routes (E1, E5)
| Method | URL | Тайлбар |
|--------|-----|---------|
| POST | /api/routes/gpx-export/ | GPX файл татах |
| POST | /api/routes/smart/ | A→B ухаалаг маршрут |
| POST | /api/routes/record-distance/ | Явсан км бүртгэх |

### Dashboard (E6)
| Method | URL | Тайлбар |
|--------|-----|---------|
| GET | /api/dashboard/stats/ | Статистик |
| GET | /api/dashboard/pending-pois/ | Хүлээгдэж буй POI |
| GET | /api/dashboard/users/ | Хэрэглэгчид |
| POST | /api/dashboard/users/{id}/ban/ | Ban/Unban |
| GET | /api/dashboard/export/?type=pois | CSV экспорт |

---

## Crowd Aggregation Algorithm (US-031)
```
green=10, yellow=3, red=6  →  dominant = GREEN (most votes)
green=2,  yellow=8, red=5  →  dominant = YELLOW
green=1,  yellow=2, red=15 →  dominant = RED
```

## Road Condition Legend
| Өнгө | Утга | Дэд бүтцийн зэрэглэл |
|------|------|----------------------|
| 🟢 Green | Дугуйн зам байгаа | 1–2 |
| 🟡 Yellow | Боломжтой, тусгай зам байхгүй | 3–4 |
| 🔴 Red | Дугуй явах боломжгүй | 5–6 |

## run test
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/backend
source venv/bin/activate          # macOS/Linux

Хэрэв зөвхөн tests.py дотрох тестийг ажиллуулмаар бол:
bashpython manage.py test tests
Нэг тодорхой апп-ийн (жишээ нь accounts) тестийг ажиллуулах:
bashpython manage.py test apps.accounts
Дэлгэрэнгүй гаралт хармаар бол -v 2 нэмнэ:
bashpython manage.py test -v 2
