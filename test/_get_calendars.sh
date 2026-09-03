#!/bin/bash
EMAIL="web-nnru@yandex.ru"
PASS="mzffbcryjqytxefz"

BODY='<?xml version="1.0" encoding="UTF-8"?><propfind xmlns="DAV:"><prop><displayname/><resourcetype/><current-user-privilege-set/><calendar-color/></prop></propfind>'

echo "=== 1) PROPFIND /calendars/{email}/ (Depth:1) ==="
curl -s -w "\nHTTP_CODE: %{http_code}\n" -X PROPFIND \
  -u "${EMAIL}:${PASS}" \
  -H "Depth: 1" \
  -H "Content-Type: application/xml" \
  -d "${BODY}" \
  "https://caldav.yandex.ru/calendars/${EMAIL}/"

echo ""
echo "=== 2) PROPFIND / (Depth:0) ==="
curl -s -w "\nHTTP_CODE: %{http_code}\n" -X PROPFIND \
  -u "${EMAIL}:${PASS}" \
  -H "Depth: 0" \
  -H "Content-Type: application/xml" \
  -d "${BODY}" \
  "https://caldav.yandex.ru/"

echo ""
echo "=== 3) PROPFIND principal (Depth:0) ==="
curl -s -w "\nHTTP_CODE: %{http_code}\n" -X PROPFIND \
  -u "${EMAIL}:${PASS}" \
  -H "Depth: 0" \
  -H "Content-Type: application/xml" \
  -d '<?xml version="1.0" encoding="UTF-8"?><propfind xmlns="DAV:"><prop><calendar-home-set xmlns="urn:ietf:params:xml:ns:caldav"/></prop></propfind>' \
  "https://caldav.yandex.ru/principals/users/${EMAIL}/"