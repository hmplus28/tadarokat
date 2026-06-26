#!/usr/bin/env bash
# تست API همه بخش‌های سامانه
set -uo pipefail
BASE="http://127.0.0.1:8000/api"
PASS=0
FAIL=0

api_code() {
  local method="$1" path="$2" token="${3:-}" body="${4:-}"
  local args=(-s -o /tmp/e2e_body.json -w "%{http_code}" -X "$method" "${BASE}${path}")
  [[ -n "$token" ]] && args+=(-H "Authorization: Bearer $token")
  [[ -n "$body" ]] && args+=(-H "Content-Type: application/json" -d "$body")
  curl "${args[@]}"
}

check() {
  local name="$1" got="$2" expect="$3"
  if [[ "$got" == "$expect" ]]; then
    echo "  [OK] $name -> HTTP $got"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $name -> HTTP $got (expect $expect)"
    FAIL=$((FAIL + 1))
  fi
}

login() {
  local user="$1" pass="$2"
  local code
  code=$(api_code POST "/auth/login" "" "{\"username\":\"$user\",\"password\":\"$pass\"}")
  if [[ "$code" != "200" ]]; then
    echo "  [FAIL] login $user -> HTTP $code"
    FAIL=$((FAIL + 1))
    return 1
  fi
  python3 -c "import json; print(json.load(open('/tmp/e2e_body.json'))['access_token'])"
}

test_role() {
  local key="$1" user="$2" pass="$3" role="$4"
  echo ""
  echo "=== $key ($role) ==="
  local token
  token=$(login "$user" "$pass") || return

  local code
  code=$(api_code GET "/health" "$token"); check "health" "$code" 200
  code=$(api_code GET "/stats" "$token"); check "stats" "$code" 200
  code=$(api_code GET "/reports/dashboard" "$token"); check "dashboard" "$code" 200
  code=$(api_code GET "/requests?page=1&page_size=10" "$token"); check "requests" "$code" 200
  code=$(api_code GET "/requests?page=1&page_size=10&filter=no_inquiry" "$token"); check "no_inquiry" "$code" 200

  if [[ "$role" == "expert" ]]; then
    code=$(api_code GET "/inquiries?page=1&page_size=10" "$token"); check "inquiries blocked" "$code" 403
    code=$(api_code GET "/inquiries/mine?page=1&page_size=10" "$token"); check "my_inquiries" "$code" 200
    code=$(api_code GET "/reports/purchase" "$token"); check "report_purchase blocked" "$code" 403
    code=$(api_code GET "/reports/reorder?page=1&page_size=10" "$token"); check "report_reorder blocked" "$code" 403
    python3 -c "import json; d=json.load(open('/tmp/e2e_body.json')); print('       expert_timeline:', 'expert_timeline' in d, '| no experts list:', 'experts' not in d)"
  else
    code=$(api_code GET "/inquiries?page=1&page_size=10" "$token"); check "inquiries" "$code" 200
  fi

  code=$(api_code GET "/orders?page=1&page_size=10" "$token"); check "orders" "$code" 200
  code=$(api_code GET "/deliveries?page=1&page_size=10" "$token"); check "deliveries" "$code" 200

  if [[ "$role" == "warehouse" ]]; then
    code=$(api_code GET "/warehouse/dashboard" "$token"); check "warehouse_dashboard" "$code" 200
    code=$(api_code GET "/warehouse/purchases?page=1&page_size=10" "$token"); check "warehouse_purchases" "$code" 200
    code=$(api_code GET "/notifications" "$token"); check "notifications" "$code" 200
    code=$(api_code GET "/reports/purchase" "$token"); check "report_purchase blocked" "$code" 403
    code=$(api_code GET "/reports/reorder?page=1&page_size=10" "$token"); check "report_reorder blocked" "$code" 403
  elif [[ "$role" == "manager" || "$role" == "admin" ]]; then
    code=$(api_code GET "/inquiries/local?page=1&page_size=10" "$token"); check "inquiry_review" "$code" 200
    code=$(api_code GET "/reports/expert" "$token"); check "report_expert" "$code" 200
    code=$(api_code GET "/reports/duration" "$token"); check "report_duration" "$code" 200
    code=$(api_code GET "/reports/purchase" "$token"); check "report_purchase" "$code" 200
    code=$(api_code GET "/reports/reorder?page=1&page_size=10" "$token"); check "report_reorder" "$code" 200
  fi
}

test_role mostafa mostafa mostafa123 expert
test_role manager manager manager123 manager
test_role anbar anbar anbar123 warehouse
test_role admin admin admin123 admin

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
if [[ "$FAIL" -eq 0 ]]; then exit 0; else exit 1; fi