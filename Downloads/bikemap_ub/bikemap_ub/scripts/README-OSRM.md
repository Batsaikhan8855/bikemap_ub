# OSRM (Local routing engine) — Setup guide

Танай BikeMap UB-ийн "Маршрут тооцоолох" функц нь **OSRM** (Open Source Routing
Machine) гэдэг сервер дээр тулгуурладаг. Олон нийтийн демо сервер
(`router.project-osrm.org`) Mongolia-ын зам сүлжээг бүрэн хамардаггүй учир
бид өөрсдөө Docker-аар OSRM-ыг ажиллуулна.

---

## 1. Юу татаж бэлдэх вэ?

* **OSM extract** — Mongolia-ын газрын зургийг Geofabrik-аас (~50 MB)
* **OSRM-backend** Docker image — `ghcr.io/project-osrm/osrm-backend`
* `bicycle.lua` profile — image дотор аль хэдийн орсон

---

## 2. Алхам алхмаар

```bash
# Project root дээрээ ажиллана
cd ~/bikemap_ub/Downloads/bikemap_ub/bikemap_ub

# 2.1 Map data татах + extract/partition/customize (3 алхам автомат)
./scripts/prepare-osrm.sh
# → ~3-5 минут (extract нь ачаалал ихтэй)
# → osrm-data/mongolia-latest.osrm файлууд үүснэ

# 2.2 OSRM service асаах
docker compose up -d osrm

# 2.3 Шалгах (УБ дотор хоёр цэгийг тооцоолно)
curl 'http://localhost:5001/route/v1/cycling/106.92,47.92;106.94,47.93?overview=false' | jq .code
# → "Ok" гарвал бэлэн
```

---

## 3. Backend-тэй холбох

`backend/.env` дотор:

```env
# Django runserver-ээр локал тест
OSRM_BASE_URL=http://localhost:5001
```

Docker compose-аар бүтэн стек ажиллуулах үед `web` service-д
`OSRM_BASE_URL=http://osrm:5000` гэж compose-оос override хийгдэнэ.

---

## 4. Бүх стекийг асаах

```bash
# Эхний удаа (data бэлдэх)
./scripts/prepare-osrm.sh

# Дараа нь
docker compose up -d
```

Үйлчилгээнүүдийн порт:

| Service | Port | Тайлбар |
|---|---|---|
| nginx | 80 | Static + reverse proxy |
| web (Django) | 8000 | API + templates |
| osrm | 5001 (host) → 5000 (container) | Routing API |
| db (Postgres) | — | internal |

---

## 5. Map data шинэчлэх

OSM data 2-3 сар тутамд шинэчлэгддэг. Шинэ дата татах бол:

```bash
rm osrm-data/mongolia-latest.osm.pbf
./scripts/prepare-osrm.sh
docker compose restart osrm
```

---

## 6. Алдаа

**`Could not find any OSRM file`**
→ `prepare-osrm.sh` амжилттай ажиллаагүй. `osrm-data/` доторх файлуудыг шалга.

**`Connection refused` (web → osrm)**
→ `docker compose ps` дээр osrm "running" эсэхийг шалга. `docker compose logs osrm` лог хар.

**Маршрут одоо ч шулуун зураас**
→ Browser console-д "OSRM сервер хариу өгсөнгүй" toast гарч байвал backend
OSRM-руу холбогдож чадахгүй байна. `OSRM_BASE_URL`-ыг шалгах. Curl 5-р
алхамаар тест хий.

---

## 7. RAM шаардлага

| Map size | Extract RAM | Routed RAM |
|---|---|---|
| Mongolia (~50 MB) | ~512 MB | ~200 MB |
| Asia (~1 GB) | ~6 GB | ~2 GB |

УБ-д Mongolia extract л хангалттай.
