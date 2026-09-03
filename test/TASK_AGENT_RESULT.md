# Демо: Операционный ИИ-агент — Telegram → LLM → Яндекс.Календарь

## Статус: ✅ ПОЛНОСТЬЮ РАБОТОСПОСОБЕН

ИИ-агент принимает поручения в свободной форме через Webhook (GET),
обрабатывает текст с помощью локальной LLM (Ollama, модель `glm-5.2:cloud`), извлекает
задачу и срок выполнения, затем создаёт событие в Яндекс.Календаре через CalDAV.

**Все 3 тестовых сценария проходят успешно — события создаются в календаре (HTTP 201).**

## Архитектура workflow (7 узлов)

```
Webhook (GET /task-agent)
    ↓
Prepare LLM Request (Code) — извлечение сообщения, формирование промпта
    ↓
Ollama LLM Analysis (HTTP Request) — вызов локальной LLM
    ↓
Parse and Build Event (Code) — парсинг JSON, генерация iCalendar-события
    ↓
Create Yandex Calendar Event (Code) — CalDAV PUT через this.helpers.httpRequest()
    ↓
Prepare Response (Code) — формирование подтверждения
    ↓
Respond to Webhook — возврат JSON-ответа
```

**Узлов:** 7 | **URL:** `http://192.168.56.50:5678/webhook/task-agent?message=<текст>`

## Конфигурация (реальные данные)

### Yandex CalDAV
| Параметр | Значение |
|----------|----------|
| Email | `web-nnru@yandex.ru` |
| Пароль приложения | `mzffbcryjqytxefz` (16 символов) |
| Calendar ID | `events-4135431` («Мои события», read/write) |
| CalDAV URL | `https://caldav.yandex.ru/calendars/web-nnru%40yandex.ru/events-4135431/{uuid}.ics` |
| Метод | PUT, Content-Type: `text/calendar; charset=utf-8` |
| Авторизация | Basic Auth (email:app_password) |

### Ollama LLM
| Параметр | Значение |
|----------|----------|
| URL | `http://10.0.2.2:11434/api/chat` (VirtualBox host loopback) |
| Модель | `glm-5.2:cloud` |
| Формат | JSON (format: 'json', stream: false) |

### n8n
| Параметр | Значение |
|----------|----------|
| Версия | 2.35.7 |
| VM | Vagrant + VirtualBox (Bitrix VM) |
| Webhook | `http://192.168.56.50:5678/webhook/task-agent` (GET) |
| БД | `/home/vagrant/.n8n/database.sqlite` |

## Описание узлов

### 1. Webhook Telegram (`n8n-nodes-base.webhook` v2)
- Метод: **GET**, путь: `task-agent`, responseMode: `responseNode`
- Параметр: `?message=<текст поручения>`

### 2. Prepare LLM Request (`n8n-nodes-base.code` v2)
- Извлекает текст сообщения из query параметра `message`
- Вычисляет текущую дату/время UTC+3 (Москва)
- Формирует системный промпт с правилами извлечения сущностей

### 3. Ollama LLM Analysis (`n8n-nodes-base.httpRequest` v4.2)
- POST `http://10.0.2.2:11434/api/chat` — вызов локальной LLM

### 4. Parse and Build Event (`n8n-nodes-base.code` v2)
- Парсит JSON-ответ LLM, строит iCalendar VEVENT
- Вычисляет Basic Auth заголовок и CalDAV URL (с `encodeURIComponent`)

### 5. Create Yandex Calendar Event (`n8n-nodes-base.code` v2)
- **Code узел** (не HTTP Request) — использует `await this.helpers.httpRequest()`
- PUT запрос к CalDAV с raw iCalendar телом — полный контроль над кодировкой

### 6. Prepare Response (`n8n-nodes-base.code` v2)
- Формирует подтверждение с эмодзи и статусом календаря

### 7. Respond to Webhook (`n8n-nodes-base.respondToWebhook` v1)
- Возвращает JSON, код 200

## Тестовые поручения и результаты

### Тест 1: Точная дата — `Напомни подготовить отчёт по продажам к пятнице до 15:00`
```json
{
  "status": "success",
  "task": { "name": "Подготовить отчёт по продажам", "deadline": "2026-09-04T15:00:00", "priority": "medium" },
  "calendar_event": { "status": "created", "http_code": 201 }
}
```

### Тест 2: Относительный срок — `Позвонить клиенту Иванову завтра утром`
```json
{
  "status": "success",
  "task": { "name": "Позвонить клиенту Иванову", "deadline": "2026-09-04T09:00:00", "priority": "medium" },
  "calendar_event": { "status": "created", "http_code": 201 }
}
```

### Тест 3: Свободная формулировка — `Надо обновить презентацию для встречи с партнёрами`
```json
{
  "status": "success",
  "task": { "name": "Обновить презентацию для встречи с партнёрами", "deadline": "2026-09-04T09:00:00", "priority": "medium" },
  "calendar_event": { "status": "created", "http_code": 201 }
}
```

## Решённые проблемы

1. **401 Unauthorized** → пароль приложения (16 символов) вместо пароля аккаунта
2. **Получение calendarId** → PROPFIND с `Depth: 1` → `events-4135431`
3. **400 Bad Request** → замена HTTP Request node на Code node с `this.helpers.httpRequest()`
4. **URL encoding** → `encodeURIComponent(email)` для `%40`
5. **Webhook метод** → GET вместо POST

## Как протестировать

```bash
curl -s -G http://192.168.56.50:5678/webhook/task-agent \
  --data-urlencode 'message=Напомни подготовить отчёт по продажам к пятнице до 15:00'
```

## Файлы проекта

| Файл | Описание |
|------|----------|
| `n8n-workflow-task-agent.json` | Готовый workflow для импорта в n8n |
| `_code_prepare_llm.js` | Код узла Prepare LLM Request |
| `_code_parse_build.js` | Код узла Parse and Build Event (с реальными кредами) |
| `_code_caldav_put.js` | Код узла Create Yandex Calendar Event (CalDAV PUT) |
| `_code_prepare_response.js` | Код узла Prepare Response |
| `_generate_task_agent_workflow.js` | Генератор workflow JSON из JS-файлов |
| `_deploy_workflow.sh` | Скрипт деплоя на VM |
| `_test_agent.sh` | Скрипт тестирования (3 сценария) |
| `_get_calendars.sh` | Скрипт PROPFIND для списка календарей |
| `_test_caldav_put.sh` | Прямой тест CalDAV PUT через curl |