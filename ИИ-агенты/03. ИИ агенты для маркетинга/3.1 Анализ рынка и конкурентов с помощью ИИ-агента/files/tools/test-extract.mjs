// ============================================================================
// Локальная проверка экстрактора брифинга из ответа LLM.
// ----------------------------------------------------------------------------
// Берём НАСТОЯЩИЙ код из tools/04-clean-output.js (не копию), чтобы тест
// проверял именно то, что поедет на сервер, и прогоняем на двух случаях:
//   1) реальный сырой ответ модели (data/fixture-raw-llm.md);
//   2) синтетический ответ с планом-заглушкой и склеенным заголовком —
//      именно на нём ломался старый экстрактор.
//
// Запуск:  node tools/test-extract.mjs
// ============================================================================
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(HERE, '04-clean-output.js'), 'utf8');

// Вырезаем только определение экстрактора — остальной файл требует $input.
const from = src.indexOf('const SEC_KEYWORDS');
const to = src.indexOf('let briefing = extractBriefing(raw);');
if (from < 0 || to < 0) {
  console.error('Не нашёл границы блока в 04-clean-output.js');
  process.exit(1);
}
const extractBriefing = new Function(src.slice(from, to) + '\nreturn extractBriefing;')();

let failed = 0;
function check(name, cond, detail) {
  console.log((cond ? '  OK   ' : '  FAIL ') + name + (detail ? ' — ' + detail : ''));
  if (!cond) failed++;
}

// --- Случай 1: реальный ответ модели -----------------------------------------
console.log('\n[1] Реальный сырой ответ модели (data/fixture-raw-llm.md)');
const raw = readFileSync(join(HERE, '..', 'data', 'fixture-raw-llm.md'), 'utf8');
const got1 = extractBriefing(raw);
check('начинается с раздела 1', /^#{1,6}\s*1\./.test(got1), got1.slice(0, 40).replace(/\n/g, ' '));
check('содержит все 6 разделов',
  [1, 2, 3, 4, 5, 6].every(n => new RegExp('#{1,6}\\s*' + n + '\\.').test(got1)));
check('не содержит англоязычных рассуждений', !/Let me |I'll write|Writing now/.test(got1));
check('раздел «Что делать» не пустой', got1.split(/#{1,6}\s*6\./)[1].trim().length > 300);

// --- Случай 2: план-заглушка + склеенный заголовок (прошлый сбой) --------------
console.log('\n[2] План-заглушка со склеенным заголовком (прошлый сбой)');
const body = (n, len) => ('Содержательный текст раздела номер ' + n + '. ').repeat(len);
const fake = [
  'Let me write the briefing following the structure strictly.',
  '',
  '## 1. Контекст анализа',
  'Что анализировалось: ниша онлайн-школ. Конкуренты: Skyeng, Инглекс, EnglishDom.',
  'Ограничения данных: перечислить.',
  '',
  '## 2. Тренды',
  '...',
  '',
  '## 3. Паттерны',
  '...',
  '',
  '## 4. Уязвимости конкурентов',
  '...',
  '',
  '## 5. Гипотезы и ограничения',
  '...',
  '',
  '## 6. Что делать',
  '3-5 действий.',
  '',
  'Let me write it out.',
  '',
  'Pattern 1: Пакетная скидка растёт с размером пакета.',
  'Основание: tariffs.csv, 27 тарифов.',
  '',
  "I'll write concisely but completely.##### 1. Контекст анализа",
  '',
  body('1', 30),
  '',
  '##### 2. Тренды',
  '',
  body('2', 30),
  '',
  '##### 3. Паттерны',
  '',
  body('3', 30),
  '',
  '##### 4. Уязвимости конкурентов',
  '',
  body('4', 30),
  '',
  '##### 5. Гипотезы и ограничения',
  '',
  body('5', 30),
  '',
  '##### 6. Что делать',
  '',
  body('6', 30)
].join('\n');

const got2 = extractBriefing(fake);
check('выбран настоящий брифинг, а не план', got2.startsWith('##### 1. Контекст анализа'),
  got2.slice(0, 45).replace(/\n/g, ' '));
check('внутри нет заглушек «...»', !/^\.\.\.$/m.test(got2));
check('нет служебной фразы «Let me write it out»', !/Let me write it out/.test(got2));
check('есть все 6 разделов',
  [1, 2, 3, 4, 5, 6].every(n => new RegExp('#{1,6}\\s*' + n + '\\.').test(got2)));

console.log(failed === 0 ? '\nВсе проверки пройдены.' : '\nПровалено проверок: ' + failed);
process.exit(failed === 0 ? 0 : 1);
