#!/bin/bash
# Прямой тест CalDAV PUT для диагностики 400
EMAIL="web-nnru@yandex.ru"
PASS="mzffbcryjqytxefz"
CALID="events-4135431"
UUID="test-$(date +%s)@n8n-agent"

# iCalendar body with real CRLF
printf 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//n8n AI Agent//RU\r\nCALSCALE:GREGORIAN\r\nBEGIN:VEVENT\r\nUID:%s\r\nDTSTAMP:20260903T120000Z\r\nDTSTART:20260904T090000Z\r\nDTEND:20260904T100000Z\r\nSUMMARY:Test Event from curl\r\nDESCRIPTION:Test description\r\nPRIORITY:5\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n' "$UUID" > /tmp/test_event.ics

echo "UUID: $UUID"
echo "=== File content ==="
cat -v /tmp/test_event.ics
echo ""
echo "=== Test 1: URL with %40 ==="
curl -sv -X PUT \
  -u "${EMAIL}:${PASS}" \
  -H "Content-Type: text/calendar; charset=utf-8" \
  --data-binary @/tmp/test_event.ics \
  "https://caldav.yandex.ru/calendars/web-nnru%40yandex.ru/${CALID}/${UUID}.ics" 2>&1 | grep -E "^(< HTTP|< Content|< Location|> PUT|400|201|204|< )|HTTP/"

echo ""
echo "=== Test 2: URL with @ ==="
curl -s -w "\nHTTP_CODE: %{http_code}\n" -X PUT \
  -u "${EMAIL}:${PASS}" \
  -H "Content-Type: text/calendar; charset=utf-8" \
  --data-binary @/tmp/test_event.ics \
  "https://caldav.yandex.ru/calendars/${EMAIL}/${CALID}/${UUID}.ics"

echo ""
echo "=== Done ==="