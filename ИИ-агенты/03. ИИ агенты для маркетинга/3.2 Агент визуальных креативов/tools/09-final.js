// ============================================================================
// ФИНАЛЬНЫЙ УЗЕЛ
// ----------------------------------------------------------------------------
// Отдаёт короткую сводку прогона: её видно в интерфейсе n8n и получает тот,
// кто дёрнул агент по ссылке (webhook отвечает результатом последнего узла).
// Полные данные лежат в registry.json / registry.csv / registry.md на диске.
// ============================================================================

const s = $('Регистр креативов').first().json.summary;

const text = [
  'Готово. Креативов: ' + s.variants + ', из них с правкой: ' + s.fixed + '.',
  'Файлы: ' + s.files.join(', ') + '.',
  s.checks_failed.length
    ? 'Замечания чек-листа: ' + s.checks_failed.join('; ') + '.'
    : 'Чек-лист пройден без замечаний.'
].join(' ');

return [{
  json: {
    status: s.status,
    generated_at: s.generated_at,
    variants: s.variants,
    fixed: s.fixed,
    files: s.files,
    checks_failed: s.checks_failed,
    difference_source: s.difference_source,
    text: text
  }
}];
