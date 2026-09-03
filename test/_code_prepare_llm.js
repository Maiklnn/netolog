/* Подготовка запроса к Ollama для извлечения задачи */
const inputData = $input.first().json;
const body = inputData.body || {};
const query = inputData.query || {};

// Поддержка Telegram-формата и простого {message: "..."}
let message = '';
if (typeof body === 'object' && body !== null) {
  message = (body.message && body.message.text) || body.message || body.text || '';
} else if (typeof body === 'string') {
  message = body;
}
if (!message && query.message) {
  message = query.message;
}
message = String(message).trim();

// Текущая дата/время в UTC+3 (Москва) для разрешения относительных сроков
const now = new Date();
const tzOffset = 3; // Europe/Moscow = UTC+3
const localTime = new Date(now.getTime() + tzOffset * 3600000);
const currentDateStr = localTime.toISOString().replace('T', ' ').slice(0, 19);

const systemPrompt = [
  'Ты — ИИ-агент-ассистент. Анализируй поручения пользователя и извлекай структурированные данные для создания задачи в календаре.',
  '',
  'Текущая дата и время (UTC+3, Europe/Moscow): ' + currentDateStr,
  '',
  'Из входящего сообщения извлеки следующие поля:',
  '1. task_name — краткое и понятное название задачи (что нужно сделать)',
  '2. deadline — срок выполнения в формате ISO 8601 (YYYY-MM-DDTHH:MM:SS), время в часовом поясе UTC+3',
  '3. duration_minutes — предполагаемая длительность в минутах (по умолчанию 60)',
  '4. description — краткое описание или контекст задачи',
  '5. priority — приоритет: high, medium или low (по умолчанию medium)',
  '',
  'Правила определения срока:',
  '- "завтра утром" → завтра 09:00',
  '- "завтра днем" → завтра 13:00',
  '- "завтра вечером" → завтра 18:00',
  '- "к пятнице" → ближайшая пятница 18:00',
  '- "к пятнице до 15:00" → ближайшая пятница 15:00',
  '- "до 15:00" → сегодня 15:00 (если уже позже — завтра 15:00)',
  '- "через 3 дня" → текущая дата + 3 дня 09:00',
  '- "на следующей неделе" → понедельник следующей недели 09:00',
  '- если срок не указан → завтра 09:00',
  '',
  'Верни ТОЛЬКО валидный JSON (без markdown, без кодовых блоков, без пояснений):',
  '{"task_name":"...","deadline":"YYYY-MM-DDTHH:MM:SS","duration_minutes":60,"description":"...","priority":"medium"}'
].join('\n');

const requestBody = {
  model: 'glm-5.2:cloud',
  stream: false,
  format: 'json',
  messages: [
    { role: 'system', content: systemPrompt },
    { role: 'user', content: message }
  ]
};

return [{ json: { requestBody, originalMessage: message } }];