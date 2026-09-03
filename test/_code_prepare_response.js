/* Подготовка ответа пользователю */
const eventData = $('Parse and Build Event').first().json;
const calResult = $input.first();

let calStatus = 'created';
let calError = '';
let calHttpCode = null;

if (calResult && calResult.json) {
  calHttpCode = calResult.json.statusCode || calResult.json.status || null;
  if (calResult.json.error || (calHttpCode && calHttpCode >= 400)) {
    calStatus = 'failed';
    calError = String((calResult.json.error && calResult.json.error.message) || calResult.json.error || ('HTTP ' + calHttpCode));
  }
}

const task = {
  name: eventData.task_name,
  deadline: eventData.deadline,
  description: eventData.description,
  priority: eventData.priority,
  duration_minutes: eventData.duration_minutes
};

const calLine = calStatus === 'created'
  ? '✅ Событие создано в Яндекс.Календаре'
  : '⚠️ Событие в календаре не создано: ' + calError;

const confirmation = [
  '✅ Задача принята!',
  '',
  '📋 ' + task.name,
  '📅 Срок: ' + task.deadline,
  '⏱ Длительность: ' + task.duration_minutes + ' мин',
  '📊 Приоритет: ' + task.priority,
  '',
  calLine
].join('\n');

return [{
  json: {
    status: 'success',
    confirmation: confirmation,
    task: task,
    calendar_event: {
      status: calStatus,
      uid: eventData.event_uid,
      http_code: calHttpCode,
      error: calError
    },
    timestamp: new Date().toISOString()
  }
}];