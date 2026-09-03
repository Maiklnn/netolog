# Progress

## Проект 1: Классификация сообщений (Webhook → Ollama → File)
- ✅ Workflow JSON: 6 узлов, Execute Command вместо Google Sheets
- ✅ NODES_EXCLUDE=[] — Execute Command включён
- ✅ Startup-скрипт создан

## Проект 2: ИИ-агент Telegram → LLM → Яндекс.Календарь — ✅ ЗАВЕРШЁН
- ✅ Workflow JSON: 7 узлов (Webhook GET, Prepare LLM, Ollama, Parse&Build, CalDAV PUT Code, Response, Respond)
- ✅ Импортирован в n8n (ID: c52f7bc2-811e-4da3-95ee-ab82b02e129d)
- ✅ Активирован, webhook зарегистрирован (GET /task-agent)
- ✅ Реальные креды: web-nnru@yandex.ru + app password (16 символов) + calendarId=events-4135431
- ✅ Тест 1 (точная дата): "к пятнице до 15:00" → 2026-09-04T15:00, ✅ 201 Created
- ✅ Тест 2 (относительный срок): "завтра утром" → 2026-09-04T09:00, ✅ 201 Created
- ✅ Тест 3 (без срока): "обновить презентацию" → 2026-09-04T09:00, ✅ 201 Created
- ✅ Все события реально созданы в Яндекс.Календаре
- ⬜ Интеграция с Telegram Bot API (опционально)

## Известные проблемы
- n8n CLI import требует UUID id в workflow JSON (иначе SQLITE_CONSTRAINT)
- responseMode "lastNode" конфликтует с respondToWebhook → использовать "responseNode"
- nohup не удерживает n8n после SSH disconnect → нужен setsid
- PowerShell искажает кириллические пути → использовать node или относительные пути
- **n8n HTTP Request v4.2 ломает raw body (iCalendar)** → решено заменой на Code node с this.helpers.httpRequest()
- **Yandex CalDAV требует app-specific password** (не пароль аккаунта) → 401 без него
- **@ в CalDAV URL требует %40** → encodeURIComponent(email)

## Эволюция решений
1. Генератор JSON: jsCode в отдельных .js файлах → JSON.stringify (без ручного экранирования)
2. Деплой: скрипт _deploy_workflow.sh (stop→delete by name→import→activate→start setsid)
3. SSL: allowUnauthorizedCerts: true на HTTP Request к Yandex CalDAV
4. Webhook: POST → GET (для простого тестирования через curl -G)
5. CalDAV хост: cal.yandex.ru → caldav.yandex.ru (правильный endpoint)
6. CalDAV auth: пароль аккаунта → app-specific password (16 символов)
7. CalDAV calendarId: получен через PROPFIND Depth:1 → events-4135431
8. CalDAV PUT: HTTP Request node → Code node с this.helpers.httpRequest() (фикс 400 Bad Request)
9. URL encoding: encodeURIComponent(email) для %40 в CalDAV URL