// ============================================================================
// ШАГ 6. ПОДГОТОВКА БРИФИНГА К ЗАПИСИ НА ДИСК
// ----------------------------------------------------------------------------
// Операция write в узле «Read/Write Files from Disk» работает с БИНАРНЫМИ
// данными, а не с текстовым полем JSON. Поэтому текст брифинга превращается
// в бинарный файл с именем briefing-<дата прогона>.md и MIME-типом text/markdown.
// ============================================================================

const b = $('Самопроверка качества').first().json;
const fileName = 'briefing-' + b.run_date + '.md';

const bin = await helpers.prepareBinaryData(
  Buffer.from(b.briefing_md, 'utf8'),
  fileName,
  'text/markdown'
);

return [{
  json: {
    run_date: b.run_date,
    file_name: fileName,
    briefing_chars: b.briefing_chars,
    self_check_passed: b.self_check_passed,
    briefing_md: b.briefing_md
  },
  binary: { data: bin }
}];
