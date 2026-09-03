/* Парсинг ответа LLM и построение iCalendar-события */
const input = $input.first().json;
const rawContent = input.message?.content ?? input.content ?? '';
const originalMessage = $('Prepare LLM Request').first().json.originalMessage || '';

// Парсим JSON из ответа LLM (с обработкой markdown-обёрток)
let text = String(rawContent).trim();
text = text.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/i, '').trim();

let parsed = {};
try {
  parsed = JSON.parse(text);
} catch (e) {
  const match = text.match(/\{[\s\S]*\}/);
  if (match) {
    try { parsed = JSON.parse(match[0]); } catch (e2) { parsed = {}; }
  }
}

// Извлекаем поля
const taskName = String(parsed.task_name || 'Задача без названия');
const description = String(parsed.description || originalMessage);
const priority = String(parsed.priority || 'medium');
const durationMinutes = parseInt(parsed.duration_minutes) || 60;

// Парсим дедлайн
let deadline;
try {
  deadline = parsed.deadline ? new Date(parsed.deadline) : new Date(Date.now() + 86400000);
  if (isNaN(deadline.getTime())) {
    deadline = new Date(Date.now() + 86400000);
  }
} catch (e) {
  deadline = new Date(Date.now() + 86400000);
}

// Конвертация в iCalendar UTC формат: YYYYMMDDTHHMMSSZ
function toICAL(date) {
  return date.getUTCFullYear().toString() +
    String(date.getUTCMonth() + 1).padStart(2, '0') +
    String(date.getUTCDate()).padStart(2, '0') + 'T' +
    String(date.getUTCHours()).padStart(2, '0') +
    String(date.getUTCMinutes()).padStart(2, '0') +
    String(date.getUTCSeconds()).padStart(2, '0') + 'Z';
}

const dtStart = toICAL(deadline);
const endDate = new Date(deadline.getTime() + durationMinutes * 60000);
const dtEnd = toICAL(endDate);
const dtStamp = toICAL(new Date());

// Генерируем UID события
const uuid = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10) + '@n8n-agent';

// Приоритет iCalendar (1=высокий, 5=средний, 9=низкий)
const icalPriority = priority === 'high' ? 1 : priority === 'low' ? 9 : 5;

// Очистка текста для iCalendar
function cleanICAL(text) {
  return String(text).replace(/[\n;,\\]/g, ' ').trim();
}

// Строим iCalendar-тело (CRLF — стандарт iCalendar)
const icalBody = [
  'BEGIN:VCALENDAR',
  'VERSION:2.0',
  'PRODID:-//n8n AI Agent//RU',
  'CALSCALE:GREGORIAN',
  'BEGIN:VEVENT',
  'UID:' + uuid,
  'DTSTAMP:' + dtStamp,
  'DTSTART:' + dtStart,
  'DTEND:' + dtEnd,
  'SUMMARY:' + cleanICAL(taskName),
  'DESCRIPTION:' + cleanICAL(description),
  'PRIORITY:' + icalPriority,
  'END:VEVENT',
  'END:VCALENDAR'
].join('\r\n') + '\r\n';

// Данные для Yandex Calendar (CalDAV)
const yandexEmail = 'web-nnru@yandex.ru';
const yandexPassword = 'mzffbcryjqytxefz';
const calendarId = 'events-4135431';

const caldavUrl = 'https://caldav.yandex.ru/calendars/' + encodeURIComponent(yandexEmail) + '/' + calendarId + '/' + uuid + '.ics';
const authHeader = 'Basic ' + Buffer.from(yandexEmail + ':' + yandexPassword).toString('base64');

return [{
  json: {
    original_message: originalMessage,
    task_name: taskName,
    deadline: parsed.deadline || deadline.toISOString(),
    deadline_ical: dtStart,
    duration_minutes: durationMinutes,
    description: description,
    priority: priority,
    event_uid: uuid,
    ical_body: icalBody,
    caldav_url: caldavUrl,
    auth_header: authHeader,
    status: 'parsed'
  }
}];