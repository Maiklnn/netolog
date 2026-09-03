# Active Context

## Текущая задача
ИИ-агент для Telegram-поручений: Webhook → Ollama LLM → Яндекс.Календарь (CalDAV). **ЗАВЕРШЁН.**

## Статус
- **ГОТОВО:** Workflow (7 узлов) импортирован, активирован, протестирован с реальными креденшалами
- **Workflow ID:** c52f7bc2-811e-4da3-95ee-ab82b02e129d
- **Webhook:** GET /task-agent — работает, отвечает JSON
- **LLM:** Ollama glm-5.2:cloud — извлекает task_name, deadline, description, priority
- **Календарь:** ✅ CalDAV PUT работает — события создаются (HTTP 201)
- **Реальные креды:** email=web-nnru@yandex.ru, app_password=16 символов, calendarId=events-4135431
- **n8n:** healthz=200, запущен через setsid

## Архитектура (7 узлов)
1. Webhook Telegram (GET, responseNode) — параметр ?message=
2. Prepare LLM Request (Code) — системный промпт
3. Ollama LLM Analysis (HTTP Request POST)
4. Parse and Build Event (Code) — JSON→iCalendar + encodeURIComponent(email)
5. Create Yandex Calendar Event (Code) — CalDAV PUT через this.helpers.httpRequest()
6. Prepare Response (Code) — подтверждение
7. Respond to Webhook — JSON 200

## Ключевые паттерны
- jsCode в отдельных .js файлах, генератор читает их (без ручного JSON-экранирования)
- responseMode: "responseNode" (не "lastNode")
- **CalDAV PUT через Code node (this.helpers.httpRequest), не HTTP Request node** — v4.2 ломает raw тело
- encodeURIComponent(email) для %40 в CalDAV URL
- Деплой: _deploy_workflow.sh (stop→delete→import→activate→start)
- n8n CLI import требует UUID id в workflow JSON

## Важные файлы
- `n8n-workflow-task-agent.json` — workflow (с реальными кредами)
- `TASK_AGENT_RESULT.md` — итоговый документ
- `_code_*.js` — код узлов (включая новый _code_caldav_put.js)
- `_generate_task_agent_workflow.js` — генератор
- `_deploy_workflow.sh` — деплой на VM
- `_test_agent.sh` — тестирование
- `_get_calendars.sh` — PROPFIND для списка календарей