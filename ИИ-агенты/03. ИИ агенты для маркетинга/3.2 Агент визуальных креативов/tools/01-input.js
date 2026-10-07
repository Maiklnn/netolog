// ============================================================================
// ШАГ 1. ВХОДНОЙ БРИФ
// ----------------------------------------------------------------------------
// Узел работает сразу после триггеров (ручная кнопка и webhook) и определяет,
// ОТКУДА брать бриф. По умолчанию — файл brief.json на диске сервера.
// Через webhook можно передать другой путь и точечные правки:
//
//   curl -X POST http://192.168.56.10:5678/webhook/visual-creatives \
//        -H 'Content-Type: application/json' \
//        -d '{"brief_path":"/var/lib/n8n/.n8n-files/visual-creatives/brief.json"}'
//
// Узел не падает, если запущен вручную: у ручного триггера json пустой.
// ============================================================================

const DEFAULT_BRIEF = '/var/lib/n8n/.n8n-files/visual-creatives/brief.json';

const first = $input.first();
const raw = (first && first.json) ? first.json : {};

// webhook в n8n 2.x кладёт тело запроса в поле body, ручной запуск тела не имеет
const body = (raw.body && typeof raw.body === 'object') ? raw.body : raw;

const briefPath = (body.brief_path && String(body.brief_path).trim())
  ? String(body.brief_path).trim()
  : DEFAULT_BRIEF;

// Правки поверх брифа: {"fix_threshold": 0} — например, чтобы принудительно
// прогнать ветку исправления при демонстрации.
const overrides = (body.overrides && typeof body.overrides === 'object') ? body.overrides : {};

return [{
  json: {
    brief_path: briefPath,
    overrides: overrides,
    source: body.brief_path ? 'webhook' : 'default',
    started_at: $now.setZone('Europe/Moscow').toFormat('yyyy-MM-dd HH:mm:ss')
  }
}];
