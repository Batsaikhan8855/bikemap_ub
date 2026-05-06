#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  prepare-osrm.sh
#
#  Downloads the Mongolia OpenStreetMap extract from Geofabrik and runs the
#  three OSRM preprocessing steps (extract → partition → customize) using the
#  bicycle profile, so that osrm-routed can serve Ulaanbaatar bike routes
#  locally inside Docker.
#
#  Usage (run from project root):
#     ./scripts/prepare-osrm.sh
#
#  Output is written to ./osrm-data/, which docker-compose mounts into the
#  osrm service at /data.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DATA_DIR="$(cd "$(dirname "$0")/.." && pwd)/osrm-data"
PBF_URL="https://download.geofabrik.de/asia/mongolia-latest.osm.pbf"
PBF_FILE="mongolia-latest.osm.pbf"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend:latest"
PROFILE="/opt/bicycle.lua"   # built into the OSRM image

# Apple Silicon (M1/M2/M3) дээр arm64 build байхгүй тул amd64 emulation
# (Rosetta) ашиглана. Intel Mac / Linux дээр энэ flag-ийг үл тоон явдаг.
echo "→ Forcing platform: linux/amd64 (Rosetta emulation on Apple Silicon)"

mkdir -p "$DATA_DIR"
cd "$DATA_DIR"

# ── 1. Download the OSM extract (≈50 MB) ─────────────────────────────────────
if [[ ! -f "$PBF_FILE" ]]; then
  echo "→ Downloading Mongolia OSM extract from Geofabrik…"
  curl -L -o "$PBF_FILE" "$PBF_URL"
else
  echo "→ $PBF_FILE already present, skipping download."
fi

# ── 2. osrm-extract (slow, ~1–3 min on Mongolia) ─────────────────────────────
echo "→ osrm-extract (bicycle profile)…"
docker run --rm --platform linux/amd64 -v "$DATA_DIR:/data" "$OSRM_IMAGE" \
  osrm-extract -p "$PROFILE" "/data/$PBF_FILE"

# ── 3. osrm-partition + osrm-customize (MLD algorithm) ──────────────────────
BASE="${PBF_FILE%.osm.pbf}"   # → "mongolia-latest"
echo "→ osrm-partition…"
docker run --rm --platform linux/amd64 -v "$DATA_DIR:/data" "$OSRM_IMAGE" \
  osrm-partition  "/data/${BASE}.osrm"

echo "→ osrm-customize…"
docker run --rm --platform linux/amd64 -v "$DATA_DIR:/data" "$OSRM_IMAGE" \
  osrm-customize  "/data/${BASE}.osrm"

echo
echo "✓ OSRM data ready in $DATA_DIR"
echo "  Now start the stack:"
echo "      docker compose up -d osrm"
echo "  Health-check (note port 5001 — macOS AirPlay holds 5000):"
echo "      curl 'http://localhost:5001/route/v1/cycling/106.92,47.92;106.94,47.93?overview=false'"
