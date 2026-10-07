// Проверка разбора ответа модели: на реальном выводе прогона 83 и на образцах.
// Запуск:  node tools/test-extract-json.js
//
// Берём функцию extractJson прямо из 03-build-prompts.js, чтобы тест проверял
// боевой код, а не его копию.
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '03-build-prompts.js'), 'utf8');
const start = src.indexOf('function balanced');
const end = src.indexOf('const parsed = extractJson(raw);');
if (start < 0 || end < 0) {
  console.error('не нашёл extractJson в 03-build-prompts.js');
  process.exit(1);
}
const extractJson = new Function(
  src.slice(start, end) + '\n return extractJson;'
)();

let failed = 0;
function check(name, text, expectVariants) {
  const got = extractJson(text);
  const n = got && Array.isArray(got.variants) ? got.variants.length : 0;
  const ok = n === expectVariants;
  if (!ok) failed++;
  console.log('%s %s вариантов=%d (ожидалось %d)',
    ok ? 'OK  ' : 'ПРОВАЛ', name.padEnd(46, ' '), n, expectVariants);
  return got;
}

// 1. Чистый JSON — базовый случай.
check('чистый JSON', '{"variants":[{"id":"V1","prompt":"a"}]}', 1);

// 2. JSON в тройных бэктиках.
check('JSON в ```json', 'Вот результат:\n```json\n{"variants":[{"id":"V1","prompt":"a"},{"id":"V2","prompt":"b"}]}\n```', 2);

// 3. Боевые случаи: размышление модели склеено с JSON, и начало объекта
//    потеряно. В прогоне 83 пропали только `{"` (ключ «variants» уцелел),
//    в прогоне 84 — вместе с ключом, осталось `…Output JSON only.ants":[…]}»`.
//    Поэтому проверяем оба: разбор должен вытянуть варианты из целого массива.
const samples = [
  ['agent-full-output.txt', 'реальный вывод прогона 83'],
  ['agent-full-output-84.txt', 'реальный вывод прогона 84']
];
samples.forEach(function (s) {
  const file = path.join(__dirname, 'fixtures', s[0]);
  if (!fs.existsSync(file)) {
    console.log('ПРОПУСК ' + s[1] + ': нет файла tools/fixtures/' + s[0]);
    return;
  }
  const got = check(s[1], fs.readFileSync(file, 'utf8'), 4);
  if (got) {
    got.variants.forEach(function (v) {
      console.log('       %s: слов=%d, style_swap=%s, negative=%s',
        v.id, String(v.prompt).split(/\s+/).length,
        v.style_swap ? 'есть' : 'нет',
        /[А-Яа-яЁё]/.test(String(v.negative || '')) ? 'РУССКИЙ' : 'английский');
    });
  }
});

// 4. Испорченный ключ: остался чужой ключ вместо «variants» — берём по массиву.
check('массив под другим ключом', '{"prompts":[{"id":"V1","prompt":"a"}]}', 1);

// 4. Мусор вместо JSON — должен вернуть null, чтобы сработал запасной промт.
check('проза без JSON', 'Let me think about this. The brief says...', 0);

// 5. Сломанный JSON — тоже null.
check('битый JSON', '{"variants":[{"id":"V1",}]}', 0);

console.log(failed ? '\nПРОВАЛОВ: ' + failed : '\nвсе проверки пройдены');
process.exit(failed ? 1 : 0);
