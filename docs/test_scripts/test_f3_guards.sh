#!/usr/bin/env bash
# F3 — Tests guards RBAC sur user-forest-service
# Usage: bash docs/test_scripts/test_f3_guards.sh
# Pré-requis : docker-compose up, jq installé, users admin + superviseur + agent en DB

set -euo pipefail

AUTH="http://localhost:8001"
API="http://localhost:8000"
SERVICE_SECRET="${SERVICE_SECRET:-dev-service-secret-change-in-production}"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; }
check_status() { [ "$1" = "$2" ] && pass "$3 (HTTP $1)" || fail "$3 — attendu $2, obtenu $1"; }

# ── Paramètres à adapter ─────────────────────────────────────────────────────
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@ghabetna.tn}"
ADMIN_PASS="${ADMIN_PASS:-admin123}"
SUPERVISEUR_EMAIL="${SUPERVISEUR_EMAIL:-superviseur@ghabetna.tn}"
SUPERVISEUR_PASS="${SUPERVISEUR_PASS:-super123}"
AGENT_EMAIL="${AGENT_EMAIL:-agent@ghabetna.tn}"
AGENT_PASS="${AGENT_PASS:-agent123}"
# ─────────────────────────────────────────────────────────────────────────────

_login() {
  local email=$1 pass=$2
  curl -s -X POST "$AUTH/auth/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$email&password=$pass" | jq -r '.access_token'
}

echo "=== F3 — Guards RBAC tests ==="
echo ""

# Récupération des tokens
echo "Obtention des tokens..."
ADMIN_TOKEN=$(_login "$ADMIN_EMAIL" "$ADMIN_PASS")
SUPERVISEUR_TOKEN=$(_login "$SUPERVISEUR_EMAIL" "$SUPERVISEUR_PASS")
AGENT_TOKEN=$(_login "$AGENT_EMAIL" "$AGENT_PASS")
echo "  admin token        : ${ADMIN_TOKEN:0:30}..."
echo "  superviseur token  : ${SUPERVISEUR_TOKEN:0:30}..."
echo "  agent token        : ${AGENT_TOKEN:0:30}..."
echo ""

# --- Sans token ---
echo "--- Sans token : GET /forests/ → 401 ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/forests/")
check_status "$CODE" "401" "GET /forests/ sans token"
echo ""

# --- Token agent : lecture OK, écriture KO ---
echo "--- Token agent : GET /forests/ → 200 ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/forests/" \
  -H "Authorization: Bearer $AGENT_TOKEN")
check_status "$CODE" "200" "GET /forests/ avec token agent"

echo "--- Token agent : POST /forests/ → 403 ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/forests/" \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"test","geometry":{"type":"Polygon","coordinates":[]}}')
check_status "$CODE" "403" "POST /forests/ avec token agent"
echo ""

# --- Token superviseur ---
echo "--- Token superviseur : DELETE /users/{id} → 403 ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$API/users/9999" \
  -H "Authorization: Bearer $SUPERVISEUR_TOKEN")
check_status "$CODE" "403" "DELETE /users/9999 avec token superviseur"
echo ""

# --- Token admin ---
echo "--- Token admin : DELETE /users/9999 → 404 (non 403) ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$API/users/9999" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
check_status "$CODE" "404" "DELETE /users/9999 avec token admin (user inexistant → 404)"
echo ""

# --- /health public ---
echo "--- GET /health → 200 sans token ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/health")
check_status "$CODE" "200" "GET /health public"
echo ""

# --- /users/by-email ---
echo "--- GET /users/by-email sans X-Service-Secret → 403 ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/users/by-email/$ADMIN_EMAIL")
check_status "$CODE" "403" "GET /users/by-email sans secret"

echo "--- GET /users/by-email avec X-Service-Secret correct → 200 ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/users/by-email/$ADMIN_EMAIL" \
  -H "X-Service-Secret: $SERVICE_SECRET")
check_status "$CODE" "200" "GET /users/by-email avec secret"

echo "--- GET /users/by-email absent dans Swagger ---"
SWAGGER=$(curl -s "$API/openapi.json")
if echo "$SWAGGER" | grep -q "by-email"; then
  fail "/users/by-email visible dans Swagger (include_in_schema=False manquant)"
else
  pass "/users/by-email absent du Swagger public"
fi
echo ""

echo "=== F3 terminé ==="
