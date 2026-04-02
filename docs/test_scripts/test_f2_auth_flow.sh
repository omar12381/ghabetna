#!/usr/bin/env bash
# F2 — Tests manuels flow login/refresh/logout
# Usage: bash docs/test_scripts/test_f2_auth_flow.sh
# Pré-requis : docker-compose up, jq installé, un user valide en DB

set -euo pipefail

AUTH="http://localhost:8001"
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
check_status() { [ "$1" = "$2" ] && pass "$3 (HTTP $1)" || fail "$3 — attendu $2, obtenu $1"; }

# ── Paramètres à adapter ─────────────────────────────────────────────────────
VALID_EMAIL="${TEST_EMAIL:-admin@ghabetna.tn}"
VALID_PASS="${TEST_PASS:-admin123}"
# ─────────────────────────────────────────────────────────────────────────────

echo "=== F2 — Auth flow tests ==="
echo "Auth service : $AUTH"
echo ""

# Scénario 1 — Login valide
echo "--- Scénario 1 : Login valide ---"
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$AUTH/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$VALID_EMAIL&password=$VALID_PASS")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)
check_status "$HTTP_CODE" "200" "Login valide"
ACCESS_TOKEN=$(echo "$BODY" | jq -r '.access_token')
REFRESH_TOKEN=$(echo "$BODY" | jq -r '.refresh_token')
ROLE=$(echo "$BODY" | jq -r '.role')
echo "  access_token  : ${ACCESS_TOKEN:0:40}..."
echo "  refresh_token : ${REFRESH_TOKEN:0:40}..."
echo "  role          : $ROLE"
echo ""

# Scénario 2 — Login invalide (mauvais password)
echo "--- Scénario 2 : Login invalide ---"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$VALID_EMAIL&password=WRONG_PASSWORD")
check_status "$HTTP_CODE" "401" "Mauvais mot de passe"
echo ""

# Scénario 4 — Refresh valide
echo "--- Scénario 4 : Refresh valide ---"
REFRESH_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$AUTH/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")
HTTP_CODE=$(echo "$REFRESH_RESPONSE" | tail -1)
BODY=$(echo "$REFRESH_RESPONSE" | head -1)
check_status "$HTTP_CODE" "200" "Refresh valide"
NEW_ACCESS_TOKEN=$(echo "$BODY" | jq -r '.access_token')
NEW_REFRESH_TOKEN=$(echo "$BODY" | jq -r '.refresh_token')
echo "  nouveau access_token  : ${NEW_ACCESS_TOKEN:0:40}..."
echo ""

# Scénario 5 — Refresh après logout
echo "--- Scénario 5 : Refresh après logout ---"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH/auth/logout" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$NEW_REFRESH_TOKEN\"}")
check_status "$HTTP_CODE" "200" "Logout"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH/auth/refresh" \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$NEW_REFRESH_TOKEN\"}")
check_status "$HTTP_CODE" "401" "Refresh après logout → 401"
echo ""

echo "=== F2 terminé ==="
echo ""
echo "NOTE Scénario 3 (compte inactif) : désactiver manuellement un user"
echo "  UPDATE users SET actif=false WHERE email='...'; puis tester login."
echo ""
echo "NOTE Scénario 6 (token expiré) : changer ACCESS_TOKEN_EXPIRE_MINUTES=1 dans .env"
echo "  Attendre 1 min, puis appeler GET /forests/ avec l'ancien access_token → 401"
