#!/usr/bin/env bash
# Uso na VPS ou no PC: bash scripts/check_api.sh [HOST]
# Por defeito testa 127.0.0.1:8090
set -e
H="${1:-http://127.0.0.1:8090}"
echo "=== $H ==="
for p in /api/health /api/stats /api/metrics /api/model-info /api/model; do
  code=$(curl -s -o /tmp/epi.json -w "%{http_code}" "$H$p" || true)
  echo "$code  GET $p"
  if [ "$code" = "200" ] && [ -s /tmp/epi.json ]; then head -c 120 /tmp/epi.json; echo; fi
done
