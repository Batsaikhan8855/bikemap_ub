# BikeMap UB — v5.0
**Ulaanbaatar Bicycle Safety Crowdsourcing Platform**

Улаанбаатар хотод дугуйгаар явах аюулгүй байдлыг crowd-sourcing аргаар сайжруулах платформ.
Хэрэглэгчид замын нөхцөл тэмдэглэж, аюултай цэгүүдийг оруулж, санал хураалтаар хамтран нийтийн мэдээллийн сан үүсгэнэ.

> Энэхүү гарын авлага **macOS** дээр (Apple Silicon M1/M2/M3 ба Intel хоёуланд) ажиллах алхмыг агуулна.

---

## Агуулга

1. [Шаардлагатай зүйлс](#1-шаардлагатай-зүйлс)
2. [Backend бэлдэх](#2-backend-бэлдэх-django)
3. [Сервер асаах](#3-сервер-асаах-)
4. [PostgreSQL тохируулах](#4-postgresql-тохируулах-заавал-биш)
5. [OSRM маршрут engine](#5-osrm-маршрут-engine--docker)
6. [УБ-ын дугуйн замыг OSM-ээс импортлох](#6-уб-ын-дугуйн-замыг-osm-ээс-импортлох-)
7. [Docker Compose (production-like)](#7-docker-compose-production-like)
8. [Тест ажиллуулах](#8-тест-ажиллуулах-)
9. [API баримт бичиг (Swagger)](#9-api-баримт-бичиг-swagger)
10. [Frontend URLs](#10-frontend-urls)
11. [API Endpoints](#11-api-endpoints)
12. [Архитектур](#12-архитектур)
13. [Алдаа & Шийдлүүд](#13-алдаа--шийдлүүд-macos)
14. [Хурдан reference](#14-хурдан-reference-cheat-sheet)

---

## 1. Шаардлагатай зүйлс

| Юу | Хэрхэн суулгах |
|---|---|
| **Python 3.11+** | `brew install python@3.11` |
| **Git** | macOS-д бэлэн (CommandLineTools-тэй ирдэг) |
| **Docker Desktop** (OSRM + PostgreSQL-д) | https://www.docker.com/products/docker-desktop |
| **curl, jq** (тестэд) | `brew install jq` |

> **Apple Silicon (M-чип):** Docker Desktop → Settings → General →
> *"Use Rosetta for x86_64/amd64 emulation on Apple Silicon"* идэвхжүүл.

---

## 2. Backend бэлдэх (Django)

```bash
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/backend

# Virtual environment үүсгэх
python3 -m venv venv
source venv/bin/activate

# Сангууд суулгах
pip install --upgrade pip
pip install -r requirements.txt

# Static файлуудыг цуглуулах (эхний удаа заавал)
python manage.py collectstatic --noinput

# Migration
python manage.py makemigrations
python manage.py migrate

# Admin хэрэглэгч үүсгэх (заавал биш)
python manage.py createsuperuser
```

### `.env` файлын чухал утгууд

```env
SECRET_KEY=<random-key>          # аль хэдийн бэлэн байна
DEBUG=True                        # development-д True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=                     # хоосон бол SQLite ашиглана
OSRM_BASE_URL=http://localhost:5001
```

> Random SECRET_KEY үүсгэх: `python -c "import secrets; print(secrets.token_urlsafe(50))"`

---

## 3. Сервер асаах ⭐

```bash
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/backend
source venv/bin/activate
python manage.py runserver
```

→ Хөтөч дээр **http://localhost:8000** нээнэ.

> **Анхаар:** `docker compose` ажиллаж байгаа бол port 8000-г эзэлдэг.
> Django runserver ашиглахын өмнө `docker compose stop web` хийнэ.

---

## 4. PostgreSQL тохируулах (заавал биш)

Энэ алхам **хэрэгтэй биш** — default нь SQLite ашигладаг бөгөөд хөгжүүлэлтэд хангалттай.
PostgreSQL ашиглахыг хүсвэл дараах 2 аргын аль нэгийг сонгоно.

### Арга A — Docker-ээр (хялбар)

```bash
# PostgreSQL container ажиллуулах
docker run -d \
  --name bikemap-db \
  -e POSTGRES_DB=bikemap_db \
  -e POSTGRES_USER=bikemap \
  -e POSTGRES_PASSWORD=bikemap_pass \
  -p 5432:5432 \
  postgres:15-alpine

# Ажиллаж байгааг шалгах
docker ps | grep bikemap-db
```

`.env` файлд холболтын тохиргоо нэмэх:

```env
DATABASE_URL=postgres://bikemap:bikemap_pass@localhost:5432/bikemap_db
```

Дараа нь migration дахин ажиллуулах:

```bash
source venv/bin/activate
python manage.py migrate
```

PostgreSQL container зогсоох:

```bash
docker stop bikemap-db
docker start bikemap-db   # дахин асаах
```

### Арга Б — Homebrew-ээр (local суулгалт)

```bash
# Суулгах
brew install postgresql@15
brew services start postgresql@15

# Database үүсгэх
psql postgres -c "CREATE USER bikemap WITH PASSWORD 'bikemap_pass';"
psql postgres -c "CREATE DATABASE bikemap_db OWNER bikemap;"

# Ажиллаж байгааг шалгах
psql -U bikemap -d bikemap_db -c "SELECT 1;"
```

`.env` файлд:

```env
DATABASE_URL=postgres://bikemap:bikemap_pass@localhost:5432/bikemap_db
```

PostgreSQL зогсоох/асаах:

```bash
brew services stop postgresql@15
brew services start postgresql@15
```

> **Зөвлөмж:** Дипломын ажлын demo-д SQLite хангалттай.
> PostgreSQL нь production/Docker deploy-д шаардлагатай.

---

## 5. OSRM маршрут engine — Docker

> OSRM ажиллаагүй бол маршрут шулуун зураас болж зурагдана
> (frontend-д шар анхааруулга гарна). Demo-д ажиллуулж байх нь сайн.

### 5.1 Эхний удаа: Mongolia OSM data бэлдэх (~5 мин)

```bash
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub
chmod +x scripts/prepare-osrm.sh
./scripts/prepare-osrm.sh
```

### 5.2 OSRM асаах

```bash
docker compose up -d osrm
docker compose logs --tail=20 osrm
# "running and waiting for requests" гарвал бэлэн
```

### 5.3 Шалгах

```bash
curl 'http://localhost:5001/route/v1/cycling/106.92,47.92;106.94,47.93?overview=false' | jq .code
# → "Ok"
```

### 5.4 Зогсоох

```bash
docker compose stop osrm
```

> **macOS AirPlay:** port 5000-г AirPlay Receiver эзэлдэг тул **5001** ашигладаг.

---

## 6. УБ-ын дугуйн замыг OSM-ээс импортлох 🗺

Map дээрээ Улаанбаатарын **бодит дугуйн замуудыг** оруулмаар бол —
OpenStreetMap (OSM) нь хамгийн зөв эх сурвалж.

> **Strava-аас яагаад татаж болохгүй вэ?**
> Strava-ийн API нь зөвхөн **өөрийнхөө activity-уудыг** буцаадаг. Бусдын
> route-ыг GPX-ээр татах нь ToS зөрчигддөг ба нийтэд нээлттэй
> endpoint байхгүй. **OSM** нь нээлттэй, төрөл бүрийн дугуйн зам
> (cycleway, lane, track) шошготой бэлэн дататай.

### 6.1 Нэг командаар импортлох

```bash
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/backend
source venv/bin/activate

# Эхлээд харж үзэх (DB-д бичихгүй)
python manage.py import_osm_bikepaths --dry-run

# Бодитоор импортлох
python manage.py import_osm_bikepaths

# Хуучныг устгаад дахин
python manage.py import_osm_bikepaths --clear
```

Энэ команд нь Overpass API-ээс УБ-ын дугуйн замуудыг татаж, OSM tag-аас
автоматаар condition (🟢/🟡/🔴) ба infra_level (1–6)-ийг дүгнэж DB-д
сегмент болгон хадгална. Үр дүнд хэдэн зуу-мянган сегмент үүснэ.

### 6.2 Сонголтууд

| Flag | Тайлбар |
|------|---------|
| `--bbox south,west,north,east` | Өөр газар нутгаас татах |
| `--dry-run` | Зөвхөн тоог харах, DB-д бичихгүй |
| `--clear` | Хуучин OSM-импортлогдсон сегментүүдийг устгана |
| `--min-meters 8` | Энэ метрээс богино segment-үүдийг алгасах |
| `--user osm_import` | Аль хэрэглэгчийн нэрээр импортлох |

### 6.3 OSM tag → infra_level хувиргалт

| OSM tag | Infra level | Condition |
|---------|-------------|-----------|
| `highway=cycleway` + `segregated=yes` | 1 — Тусгаарлагдсан | 🟢 |
| `highway=cycleway` (default) | 2 — Холимог | 🟢 |
| `cycleway[:left/:right/:both]=track` | 3 — Хамгаалалттай | 🟢 |
| `cycleway[:left/:right/:both]=lane` | 4 — Тэмдэглэгээт | 🟡 |
| `highway=path/footway` + `bicycle=yes` | 5 — Явган хүний зам | 🟡 |
| `bicycle=yes` (бусад) | 6 — Нийтийн зам | 🟡 |

### 6.4 Бусад эх үүсвэр

| Эх үүсвэр | GPX татах | Эзэмшилт |
|-----------|-----------|----------|
| **OSM (Overpass)** ⭐ | Шууд | Нийтийн |
| Komoot | Нэг бүрчлэн | Бүртгэлтэй |
| Wikiloc | Нэг бүрчлэн | Бүртгэлтэй |
| Bikemap.net | Нэг бүрчлэн | Premium |
| Strava | ❌ боломжгүй | — |

Хэрэв тодорхой дугуйчны route-уудыг нэмэхийг хүсвэл — Komoot/Wikiloc-аас
GPX татаж, frontend дээр **"GPX файл сонгох"** товчоор оруулах боломжтой.

### 6.5 Гар хийсэн дугуйн зам (geojson.io workflow) ✏️

OSM-д УБ хотын дугуйн дэд бүтэц **хэт цөөн** шошготой. Хотын төвийн
будагтай эгнээ, шинээр баригдсан зам нь OSM-д бүртгэлгүй байж болно.
Эдгээрийг гараар нэмэхэд:

#### Алхам 1 — Замаа зурах
1. Хөтөч дээр **https://geojson.io** нээгээрэй
2. Газрын зургийг УБ-руу зөөнө
3. Зүүн дээд буланд **"Draw a polyline"** (LineString) tool сонгоно
4. Дугуйн замынхаа дагуу шугам зурна (товчоо хүлээж эхлэл-төгсгөл цэгүүдээр)
5. Шугам дээр дарж **JSON edit** нээж дараах property-уудыг нэмнэ:
   ```json
   {
     "name": "Энхтайваны өргөн чөлөө дугуйн зам",
     "condition": "yellow",
     "infra_level": 4
   }
   ```
6. Бүх замаа зурж дуусгасны дараа **Save → GeoJSON** дарж файл татна

#### Алхам 2 — Файл байршуулах
Татсан файлыг project-ийн `data/` фолдерт хадгал:
```bash
mv ~/Downloads/map.geojson \
   ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/data/ub_bikepaths.geojson
```

> Шаблон жишээ: `data/ub_bikepaths.sample.geojson` — формат харах

#### Алхам 3 — Импортлох
```bash
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/backend
source venv/bin/activate

# Эхлээд дүгнэх
python manage.py import_bikepaths_geojson \
  ../data/ub_bikepaths.geojson --dry-run

# Бодитоор импортлох
python manage.py import_bikepaths_geojson \
  ../data/ub_bikepaths.geojson
```

#### Property reference

| Property | Утга | Default |
|----------|------|---------|
| `name` | Замын нэр (заавал биш) | "" |
| `condition` | `green` / `yellow` / `red` | yellow |
| `infra_level` | 1–6 | 4 |

#### Туслах зөвлөмжүүд
- Урт замыг **олон segment-эд хувааж** зурахын оронд нэг LineString-аар зурж болно — script нь ойролцоо цэгүүдийг сегментэд хувааж өгнө
- Хэрэв буруу зурвал `--clear --user manual_import` flag-аар цэвэрлэж дахин эхлэнэ
- **Strava Heatmap** (https://www.strava.com/heatmap) дээр популяр маршрут хараад түүнийг нь geojson.io дээр давтан зурж болно

> **Зөвлөмж:** Гар хийсэн зам нь `is_created=True` flag-тайгаар хадгалагдах
> тул OSM-аас орсон датагаас ялгагдана.

### 6.6 Strava Segments API-ээс импортлох 🟧

Strava-ийн **албан ёсны API** ашиглан УБ-ын popular cycling segment-уудыг
бөөнөөр татах боломжтой (хэрэглэгчдийн хамгийн их явсан үнэлгээтэй замууд).

> **Анхааруулга:** Strava API нь **access token шаардана**. Heatmap болон
> бусад "хүмүүсийн route"-ыг шууд татах боломжгүй — зөвхөн "Segments"
> (нийтэд нээлттэй challenge замууд).

#### Алхам 1 — Strava API app үүсгэх (5 минут, нэг удаа)

1. https://www.strava.com/settings/api ороорой (нэвтэрсэн байх ёстой)
2. **Create App** дарж жижиг application үүсгэнэ:

   | Талбар | Утга |
   |--------|------|
   | Application Name | BikeMap UB |
   | Category | Education |
   | Website | http://localhost:8000 |
   | Authorization Callback Domain | localhost |

3. Зураг upload (заавал — ямар ч жижиг зураг)
4. Үүсгэснийхэн дараа дэлгэцэд **"Your Access Token"** гэдэг талбар гарна.
   Тэр token-ыг хуулна уу.

> Token нь 6 цаг хүчинтэй. Хугацаа нь дуусахад дахин шинэчлэх хэрэгтэй
> (settings/api дотроос дахин харна).

#### Алхам 2 — Token-ыг тохируулах

```bash
# Терминалд token-ыг env var болгох
export STRAVA_ACCESS_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# эсвэл --token параметрээр шууд дамжуулж болно
```

#### Алхам 3 — Импортлох

```bash
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/backend
source venv/bin/activate

# Эхлээд харах
python manage.py import_strava_segments --dry-run

# Бодитоор импортлох
python manage.py import_strava_segments

# Илүү нарийн grid-ээр (илүү олон segment татах)
python manage.py import_strava_segments --grid 6

# Хуучныг устгаад дахин
python manage.py import_strava_segments --clear
```

#### Команд нь юу хийдэг вэ?

1. УБ-ын bbox-ыг N×N grid-д хуваана (default 4×4 = 16 нүд)
2. Нүд тус бүрд `/segments/explore` API-руу хүсэлт явуулна (нүд тус бүрд max 10 segment ирнэ)
3. Олдсон segment бүрийн encoded polyline-ыг decode хийнэ
4. Сегмент бүрийг `Segment` row болгож DB-д хадгална (default condition=green, level=2)

#### Sonголтууд

| Flag | Тайлбар |
|------|---------|
| `--token <str>` | Token-ыг env var-аас сонгохгүй бол шууд дамжуулна |
| `--grid 6` | 4×4-аас илүү нарийн grid (илүү дуудалт = илүү дата) |
| `--bbox sw_lat,sw_lng,ne_lat,ne_lng` | Өөр газар нутгаас |
| `--default-condition yellow` | Strava segment-ийн default condition |
| `--default-level 4` | Default infra level |
| `--clear` | Strava-аас өмнө импортлогдсонг устгах |
| `--dry-run` | Тоог харах, бичихгүй |

#### Хязгаарлалт

- **Heatmap нь PNG зураг** учир тэмдэгтгүй (raster) → зөвхөн зүй харж тэр чигээр нь geojson.io дээр давтан зурах хэрэгтэй
- Strava API нь нэг bbox-аас **дээд тал нь 10 segment** буцаадаг → grid-ээр хуваах нь үүний шийдэл
- Rate limit: token бүр **200 хүсэлт / 15 мин** — энгийн ажиллагаанд хангалттай
- Strava-ийн **API ToS**-ийг уншиж байгаарай (https://www.strava.com/legal/api). Энэхүү команд нь educational/research зориулалттай.

---

## 7. Docker Compose (production-like)

PostgreSQL + Django (gunicorn) + Nginx бүгдийг хамт асаах:

```bash
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub
docker compose up -d
docker compose ps
docker compose logs -f web    # логийг дагах
```

| Service | URL |
|---|---|
| Frontend / API (nginx-р) | http://localhost |
| Django gunicorn | http://localhost:8000 |
| OSRM | http://localhost:5001 |

Зогсоох:

```bash
docker compose down
docker compose down -v    # volume-тэй хамт бүгдийг устгах
```

> **Анхаар:** Docker compose ажиллаж байх үед `python manage.py runserver`
> port 8000-г эзэлдэг тул зөрчилдөнө. `docker compose stop web` хийж гарна.

---

## 8. Тест ажиллуулах ✅

```bash
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/backend
source venv/bin/activate

# Бүх тест (65 test case)
python manage.py test

# Дэлгэрэнгүй гаралттай
python manage.py test --verbosity=2

# Зөвхөн нэг app-ийн тест
python manage.py test apps.accounts
python manage.py test apps.pois
python manage.py test apps.aggregation
python manage.py test apps.audit_log

# Үндсэн tests.py (40 test)
python manage.py test tests

# Нэг class/method
python manage.py test tests.AuthTest
python manage.py test tests.VoteTest.test_upvote_increments
```

### Тестийн бүтэц

| Файл | Тест class | Тоо | Хамрах хүрээ |
|------|-----------|-----|-------------|
| `tests.py` | `UserModelTest` | 5 | User model |
| `tests.py` | `AuthTest` | 6 | Бүртгэл, нэвтрэлт, профайл |
| `tests.py` | `SegmentTest` | 8 | Segment CRUD, bulk import |
| `tests.py` | `POITest` | 7 | POI CRUD, батлах/татгалзах |
| `tests.py` | `VoteTest` | 6 | upvote/downvote toggle |
| `tests.py` | `GPXImportTest` | 4 | GPX upload |
| `tests.py` | `AggregationTest` | 4 | Majority vote |
| `apps/accounts/tests.py` | `RegisterLoginTest` | 4 | Login, banned user |
| `apps/accounts/tests.py` | `RBACTest` | 2 | RBAC эрхийн удирдлага |
| `apps/pois/tests.py` | `POICreateTest` | 1 | POI үүсгэх |
| `apps/pois/tests.py` | `POIVoteTest` | 5 | Vote логик |
| `apps/pois/tests.py` | `POIApprovalTest` | 3 | Батлах/татгалзах |
| `apps/aggregation/tests.py` | `CrowdAggregationModelTest` | 6 | Алгоритм unit test |
| `apps/aggregation/tests.py` | `UpdateAggregationTest` | 2 | Integration test |
| `apps/audit_log/tests.py` | `AuditLogTest` | 2 | Audit trail |
| **Нийт** | | **65** | **≥ 40% coverage** |

Хүлээгдэх үр дүн:
```
Ran 65 tests in ~17s
OK
```

---

## 9. API баримт бичиг (Swagger)

Server асаасны дараа:

| URL | Тайлбар |
|-----|---------|
| http://localhost:8000/api/docs/ | **Swagger UI** — endpoint туршиж болно |
| http://localhost:8000/api/redoc/ | ReDoc харагдац |
| http://localhost:8000/api/schema/ | OpenAPI JSON schema |

---

## 10. Frontend URLs

| URL | Тайлбар |
|-----|---------|
| http://localhost:8000/ | Газрын зураг (Map) |
| http://localhost:8000/login/ | Нэвтрэх |
| http://localhost:8000/register/ | Бүртгүүлэх |
| http://localhost:8000/heatmap/ | Heatmap |
| http://localhost:8000/dashboard/ | Админ дашбоард |
| http://localhost:8000/profile/ | Профайл |
| http://localhost:8000/admin/ | Django Admin |

---

## 11. API Endpoints

### Auth (E8)
| Method | URL | Тайлбар | Эрх |
|--------|-----|---------|-----|
| POST | `/api/auth/register/` | Бүртгүүлэх | Public |
| POST | `/api/auth/login/` | Нэвтрэх → JWT cookie | Public |
| POST | `/api/auth/refresh/` | Token шинэчлэх | Public |
| POST | `/api/auth/logout/` | Гарах | Cyclist+ |
| GET/PATCH | `/api/auth/profile/` | Профайл харах/засах | Cyclist+ |
| POST | `/api/auth/password-reset/` | Нууц үг сэргээх хүсэлт | Public |
| POST | `/api/auth/password-reset/confirm/` | Нууц үг солих | Public |

### Segments (E2)
| Method | URL | Тайлбар | Эрх |
|--------|-----|---------|-----|
| GET | `/api/segments/` | Бүх сегмент | Public |
| POST | `/api/segments/` | Сегмент үүсгэх | Cyclist+ |
| PATCH | `/api/segments/{id}/` | Нөхцөл засах | Owner/Mod |
| DELETE | `/api/segments/{id}/` | Устгах | Owner/Mod |
| POST | `/api/segments/bulk-import/` | GPX-ийн сегментүүд нэмэх (≤500) | Cyclist+ |

### POIs (E3)
| Method | URL | Тайлбар | Эрх |
|--------|-----|---------|-----|
| GET | `/api/pois/` | Батлагдсан POI-ууд | Public |
| POST | `/api/pois/` | POI нэмэх | Cyclist+ |
| DELETE | `/api/pois/{id}/` | Устгах | Owner/Mod |
| POST | `/api/pois/{id}/vote/` | Upvote / Downvote | Cyclist+ |
| POST | `/api/pois/{id}/approve/` | Батлах | Mod/Admin |
| POST | `/api/pois/{id}/reject/` | Татгалзах | Mod/Admin |

### Aggregation (E4)
| Method | URL | Тайлбар | Эрх |
|--------|-----|---------|-----|
| GET | `/api/aggregation/` | Нэгтгэсэн сегментүүд | Public |
| GET | `/api/aggregation/heatmap/` | Heatmap өгөгдөл | Public |

### Routes (E1, E5)
| Method | URL | Тайлбар | Эрх |
|--------|-----|---------|-----|
| POST | `/api/routes/gpx-export/` | GPX файл татах | Cyclist+ |
| POST | `/api/routes/gpx-import/` | GPX файлаас сегмент үүсгэх | Cyclist+ |
| POST | `/api/routes/smart/` | A→B smart маршрут (OSRM) | Public |
| POST | `/api/routes/record-distance/` | Явсан км бүртгэх | Cyclist+ |

### Dashboard (E6)
| Method | URL | Тайлбар | Эрх |
|--------|-----|---------|-----|
| GET | `/api/dashboard/stats/` | Статистик | Mod/Admin |
| GET | `/api/dashboard/pending-pois/` | Хүлээгдэж буй POI | Mod/Admin |
| GET | `/api/dashboard/users/` | Хэрэглэгчдийн жагсаалт | Admin |
| POST | `/api/dashboard/users/{id}/ban/` | Ban / Unban | Admin |
| GET | `/api/dashboard/export/?type=pois` | CSV экспорт | Mod/Admin |
| GET | `/api/dashboard/audit-log/` | Үйлдлийн бүртгэл | Admin |

---

## 12. Архитектур

```
bikemap_ub/
├── backend/
│   ├── apps/
│   │   ├── accounts/      # JWT auth, RBAC, profiles, password reset
│   │   ├── segments/      # Road condition tagging, bulk import
│   │   ├── pois/          # POI system (6 types, voting, image upload)
│   │   ├── aggregation/   # Crowd aggregation algorithm (SHA256 hashing)
│   │   ├── routes/        # GPX export/import, Smart Route (OSRM)
│   │   └── audit_log/     # Admin action audit trail
│   ├── config/            # Django settings, URLs
│   ├── tests.py           # 40 core test cases
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── templates/
│   │   ├── map/index.html        # Map + GPS + Segment + POI + GPX import
│   │   ├── map/heatmap.html      # Dark Matter heatmap
│   │   ├── auth/                 # login / register / profile
│   │   └── dashboard/            # Admin dashboard
│   └── static/
│       ├── css/main.css
│       └── js/
│           ├── auth.js           # httpOnly JWT cookie auth
│           ├── api.js            # API helpers, CSRF
│           ├── gps.js            # GPS recording
│           ├── segment.js        # Drawing segments
│           ├── poi.js            # POIs
│           ├── smart_route.js    # OSRM routing
│           ├── gpx_import.js     # GPX upload + bulk import
│           ├── map.js            # Leaflet init
│           ├── heatmap.js        # Heatmap (CartoDB Dark Matter)
│           ├── dashboard.js      # Admin dashboard
│           └── profile.js        # User profile
├── scripts/
│   └── prepare-osrm.sh           # OSRM data prep (one-time)
├── docker-compose.yml            # web + db + nginx + osrm
├── nginx.conf                    # Nginx reverse proxy config
└── README.md
```

### Crowd Aggregation алгоритм

```
green=10, yellow=3, red=6   →  dominant = GREEN
green=2,  yellow=8, red=5   →  dominant = YELLOW
green=1,  yellow=2, red=15  →  dominant = RED
```

Spatial hashing: SHA256(round(lat,3) + round(lng,3)) — ойрын сегментүүдийг нэгтгэнэ.

### Сегментийн өнгө

| Өнгө | Утга | Дэд бүтцийн зэрэглэл |
|------|------|----------------------|
| 🟢 Green  | Дугуйн зам байгаа | 1–2 |
| 🟡 Yellow | Боломжтой, тусгай зам байхгүй | 3–4 |
| 🔴 Red    | Дугуй явах боломжгүй | 5–6 |

---

## 13. Алдаа & Шийдлүүд (macOS)

### `port 8000 already in use`
Docker compose web container ажиллаж байна:
```bash
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub
docker compose stop web
```

### `port 5000: bind: address already in use`
macOS AirPlay Receiver port 5000-г эзэлдэг. Config-д **5001** тохируулсан — өөрчлөх шаардлагагүй.

### `Server Error (500)` хөтөч дээр
Static файлуудын manifest дутуу байж болно:
```bash
source venv/bin/activate
python manage.py collectstatic --noinput
```

### `no matching manifest for linux/arm64/v8`
Apple Silicon дээр. `docker-compose.yml`-д `platform: linux/amd64` тохируулна.
Docker Desktop → "Use Rosetta…" асааж байгаа эсэхийг шалга.

### `psycopg2 build fails`
```bash
brew install postgresql@15 libpq
export LDFLAGS="-L/opt/homebrew/opt/libpq/lib"
export CPPFLAGS="-I/opt/homebrew/opt/libpq/include"
pip install -r requirements.txt
```

### Маршрут шулуун зураас болж байна
1. `docker compose ps` — osrm "running" эсэхийг шалга
2. `curl http://localhost:5001/...` туршиж үз
3. `backend/.env`-д `OSRM_BASE_URL=http://localhost:5001` байгаа эсэхийг шалга
4. runserver дахин асаа

### `ModuleNotFoundError: No module named 'django'`
Virtual environment идэвхгүй байна:
```bash
source venv/bin/activate
```

---

## 14. Хурдан reference (cheat-sheet)

```bash
# ── Сервер асаах ──────────────────────────────────────────
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/backend
source venv/bin/activate
python manage.py runserver
# → http://localhost:8000

# ── Бүх тест ──────────────────────────────────────────────
python manage.py test --verbosity=2
# → Ran 65 tests … OK

# ── Нэг app-ийн тест ──────────────────────────────────────
python manage.py test apps.pois
python manage.py test apps.accounts

# ── PostgreSQL Docker-ээр асаах ────────────────────────────
docker run -d --name bikemap-db \
  -e POSTGRES_DB=bikemap_db \
  -e POSTGRES_USER=bikemap \
  -e POSTGRES_PASSWORD=bikemap_pass \
  -p 5432:5432 postgres:15-alpine
# .env → DATABASE_URL=postgres://bikemap:bikemap_pass@localhost:5432/bikemap_db
python manage.py migrate

# ── OSRM ──────────────────────────────────────────────────
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub
./scripts/prepare-osrm.sh        # эхний удаа
docker compose up -d osrm
docker compose stop osrm         # зогсоох

# ── УБ-ын дугуйн зам OSM-ээс татах ────────────────────────
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub/backend
source venv/bin/activate
python manage.py import_osm_bikepaths --dry-run   # эхлээд харах
python manage.py import_osm_bikepaths             # бодитоор импортлох

# ── Static файл ───────────────────────────────────────────
python manage.py collectstatic --noinput

# ── Swagger ───────────────────────────────────────────────
# → http://localhost:8000/api/docs/

# ── Browser hard reload ───────────────────────────────────
Cmd+Shift+R
```
# segment harah
python manage.py segment_stats

---

*Оюутан: Э.Батсайхан (B222270809) | Дипломын ажил | 2026*
