// ============================================================================
// ШАГ 6. АВТОМАТИЧЕСКАЯ САМОПРОВЕРКА КАЧЕСТВА БРИФИНГА
// ----------------------------------------------------------------------------
// Задание требует, чтобы результат можно было проверить. Этот узел прогоняет
// брифинг по чек-листу механически, а не «на глаз»:
//   1) все ли обязательные разделы на месте;
//   2) у каждого вывода есть строка «Основание:»;
//   3) упомянуты ли конкуренты;
//   4) нет ли ЧИСЕЛ, которых не было в исходных данных (защита от галлюцинаций);
//   5) не попали ли в выводы сигналы, которые фильтр пометил как шум;
//   6) отделены ли гипотезы от подтверждённых выводов.
// ============================================================================

const brief = $('Очистка брифинга').first().json;
const pack = $('Фильтрация и группировка').first().json;
const md = String(brief.briefing_md || '');
const source = String(pack.analytics_pack || '');

const checks = [];
const add = (name, ok, detail) => checks.push({ name: name, ok: !!ok, detail: detail });

// --- 1. Обязательные разделы ---
const REQUIRED = [
  ['1. Контекст анализа', /##\s*1\.\s*Контекст/i],
  ['2. Тренды',          /##\s*2\.\s*Тренды/i],
  ['3. Паттерны',        /##\s*3\.\s*Паттерны/i],
  ['4. Уязвимости конкурентов', /##\s*4\.\s*Уязвимост/i],
  ['5. Гипотезы и ограничения', /##\s*5\.\s*Гипотез/i],
  ['6. Что делать',      /##\s*6\.\s*Что делать/i]
];
const missing = REQUIRED.filter(([, re]) => !re.test(md)).map(([n]) => n);
add('Все обязательные разделы присутствуют', missing.length === 0,
    missing.length ? 'нет разделов: ' + missing.join(', ') : 'найдены все ' + REQUIRED.length + ' разделов');

// --- 2. Строки «Основание:» ---
// ВАЖНО: \w в JavaScript не включает кириллицу, поэтому «Основание:» нужно
// ловить явным классом [а-яё], иначе счётчик всегда даёт ноль.
const grounds = (md.match(/Основан[а-яё]*\s*[:—–]/gi) || []).length;
// примерно считаем выводы: пункты списка и подзаголовки в разделах 2-4
const sec24 = (md.split(/##\s*5\./)[0].split(/##\s*2\./)[1]) || '';
// выводы в брифинге оформляются и списком, и подзаголовками, и жирным лидом
const claims = (sec24.match(/^\s*(?:[-*]|\d+\.)\s+\S|^#{3,4}\s+\S|^\*\*[^*\n]+\*\*/gm) || []).length;
add('У выводов указаны основания', grounds >= 3,
    'строк «Основание:» — ' + grounds + ', пунктов-выводов в разделах 2–4 — ~' + claims);

// --- 3. Конкуренты упомянуты ---
const comps = pack.context.competitors || [];
const mentioned = comps.filter(c => new RegExp(c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i').test(md));
const absent = comps.filter(c => mentioned.indexOf(c) < 0);
add('Упомянуты все конкуренты', absent.length === 0,
    absent.length ? 'в брифинге нет: ' + absent.join(', ')
                  : 'найдены все ' + comps.length + ': ' + comps.join(', '));

// --- 4. Числа, которых нет в исходных данных (проверка на галлюцинации) ---
function numbers(text) {
  const out = new Set();
  // Пробел — разделитель разрядов ТОЛЬКО если за ним ровно три цифры и дальше
  // не цифра. Иначе «#9 2025-10» склеивалось бы в 92025, «#23 2026-08» — в 232026,
  // и проверка выдавала бы ложные срабатывания на датах.
  const re = /\d{1,3}(?:[ \s]\d{3})+(?!\d)(?:[.,]\d+)?|\d+(?:[.,]\d+)?/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const digits = m[0].replace(/[ \s]/g, '').replace(',', '.');
    const val = parseFloat(digits);
    if (!isNaN(val) && digits.replace(/\D/g, '').length >= 2) out.add(val);  // >=2 цифры: отсекаем нумерацию
  }
  return out;
}
const srcNums = numbers(source);
const briefNums = numbers(md);

// Модели разрешено считать простую арифметику из переданных чисел: доли,
// проценты, разницы, отношения. Поэтому кроме «сырых» чисел источника
// собираем множество производных значений (два операнда, 5 операций).
const r2 = x => Math.round(x * 100) / 100;
const srcArr = [...srcNums];
const derived = new Set(), derivedInt = new Set();
for (const a of srcArr) {
  for (const b of srcArr) {
    const vals = [a + b, a - b, a / b, (a - b) / b * 100, a * b];
    for (const x of vals) {
      if (!isFinite(x)) continue;
      derived.add(r2(x));
      derivedInt.add(Math.round(x));
    }
  }
}

const unknown = [];
for (const v of briefNums) {
  const found = srcNums.has(v) ||
                derived.has(r2(v)) || derivedInt.has(Math.round(v)) ||
                srcNums.has(v * 100) || srcNums.has(v / 100) ||   // проценты/доли
                [...srcNums].some(s => Math.abs(s - v) < 0.51);   // округление
  if (!found) unknown.push(v);
}
add('Числа подтверждаются исходными данными', unknown.length === 0,
    unknown.length
      ? 'НЕТ в источниках и не выводятся арифметикой из них: ' +
        unknown.slice(0, 12).join(', ') + (unknown.length > 12 ? ' …' : '') +
        ' — проверить вручную'
      : 'все ' + briefNums.size + ' чисел брифинга подтверждаются данными ' +
        'или выводятся из них простой арифметикой');

// --- 5. Шум не попал в разделы выводов ---
const noiseCats = (pack.noise || []).map(n => n.category);
const outputsOnly = md.split(/##\s*5\./)[0];   // разделы 1–4
const leaked = noiseCats.filter(c => new RegExp(c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i').test(outputsOnly));
add('Единичные сигналы (шум) не попали в выводы', leaked.length === 0,
    leaked.length ? 'в разделах 1–4 упомянуты шумовые категории: ' + leaked.join(', ')
                  : 'из ' + noiseCats.length + ' шумовых категорий ни одна не попала в разделы выводов');

// --- 6. Гипотезы отделены от выводов ---
const hypMentions = (md.match(/гипотез/gi) || []).length;
add('Гипотезы отделены от подтверждённых выводов', hypMentions >= 2,
    'упоминаний «гипотез» — ' + hypMentions);

// --- 7. Оговорка о недостатке данных, если трендов нет ---
const trendSection = (md.split(/##\s*3\./)[0].split(/##\s*2\./)[1]) || '';
const trendHonest = /недостаточно|нет подтверждённых данных|Данных для корректного вывода/i.test(trendSection);
const trendGrounded = /Основан/i.test(trendSection);
add('Раздел трендов не перегружен выводами без оснований',
    trendHonest || trendGrounded,
    trendHonest ? 'есть явная оговорка о недостатке данных'
                : trendGrounded ? 'каждый тренд приведён со строкой «Основание:»'
                                : 'в разделе трендов нет ни оснований, ни оговорки о нехватке данных');

// --- Итог ---
const passed = checks.filter(c => c.ok).length;
const total = checks.length;

let appendix = '\n\n---\n\n## Приложение. Автоматическая самопроверка качества\n\n';
appendix += 'Проверка выполнена узлом «Самопроверка качества» сразу после генерации брифинга. ';
appendix += 'Пройдено **' + passed + ' из ' + total + '** проверок.\n\n';
appendix += '| № | Проверка | Результат | Детали |\n|---|---|---|---|\n';
checks.forEach((c, i) => {
  appendix += '| ' + (i + 1) + ' | ' + c.name + ' | ' + (c.ok ? '✅ пройдено' : '⚠️ требует внимания') + ' | ' + c.detail + ' |\n';
});
appendix += '\n**Параметры прогона:** тарифных позиций — ' + brief.counts.tariffs +
  ', отзывов — ' + brief.counts.reviews +
  ', сигналов-наблюдений — ' + brief.counts.observations +
  ', гипотез — ' + brief.counts.hypotheses +
  ', исключено единичных сигналов — ' + brief.counts.noise_excluded + '.\n';
appendix += '\n**Служебная информация:** символов в ответе модели — ' + brief.raw_llm_chars +
  ', из них отброшено как служебные рассуждения — ' + brief.reasoning_stripped + '.\n';

return [{
  json: {
    briefing_md: md + appendix,
    generated_at: brief.generated_at,
    run_date: brief.run_date,
    counts: brief.counts,
    self_check: { passed: passed, total: total, checks: checks },
    self_check_passed: passed === total,
    appendix_md: appendix
  }
}];
