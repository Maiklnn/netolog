// ============================================================================
// ШАГ 3. ФИЛЬТРАЦИЯ ШУМА, ГРУППИРОВКА И ВЫДЕЛЕНИЕ КЛЮЧЕВЫХ СИГНАЛОВ
// ----------------------------------------------------------------------------
// Здесь заложены жёсткие правила, которые не дают агенту выдать случайный
// сигнал за вывод. Правила видны прямо в коде — это «правила workflow».
//
//   Правило 1 (порог значимости). Сигнал попадает в выводы, только если он
//     подтверждён >= MIN_SIGNAL независимыми единицами наблюдения.
//   Правило 2 (кросс-подтверждение). Сигнал усиливается, если встречается
//     более чем у одной школы ИЛИ подтверждается другим источником (обзор рынка).
//   Правило 3 (уровни аналитики). Каждый сигнал получает уровень:
//     ДАННЫЕ      — единичный факт (в выводы не идёт, остаётся в приложении);
//     НАБЛЮДЕНИЕ  — повторяется, но без объяснения значимости;
//     ИНСАЙТ      — повторяется + есть подтверждение + понятно, что с этим делать;
//     ГИПОТЕЗА    — единичный/слабый сигнал, который нельзя терять, но нельзя
//                   и подавать как вывод.
// ============================================================================

const ctx = $json.context;
const reviews = ctx.normalized.reviews || [];
const tariffs = ctx.normalized.tariffs || [];
const marketText = String(ctx.normalized.market_review_text || '');

const MIN_SIGNAL = 2;        // минимум единиц наблюдения для «наблюдения»
const MIN_INSIGHT = 3;       // минимум единиц наблюдения для «инсайта»

const uniq = a => Array.from(new Set(a));

// --- 1. Группировка: похожие сигналы объединяются в одну категорию ---
const groups = {};
for (const r of reviews) {
  const g = groups[r.category] || (groups[r.category] = {
    category: r.category, items: [], schools: [], platforms: [], months: [],
    types: { 'позитив': 0, 'негатив': 0, 'смешанный': 0 }
  });
  g.items.push(r);
  g.schools = uniq(g.schools.concat([r.school]));
  g.platforms = uniq(g.platforms.concat([r.platform]));
  if (/^\d{4}-\d{2}$/.test(r.date)) g.months = uniq(g.months.concat([r.date]));
  g.types[r.type]++;
}

// --- 2. Кросс-подтверждение из вторичного источника ---
// Ключевые слова категории, наличие которых в обзоре рынка усиливает сигнал.
const MARKET_KEYWORDS = {
  'Цена и оплата':                 [/цен|подорож|стоимост|чек/i],
  'Списания и возвраты':           [/возврат|списан|refund|оплат/i],
  'Преподаватель':                 [/преподавател|репетитор|кадр|текучк/i],
  'Платформа и техника':           [/платформ|приложен|мобильн|онлайн-урок|технолог/i],
  'Поддержка':                     [/поддержк|сервис|клиентск/i],
  'Результат и прогресс':          [/результат|эффективн|прогресс|качеств/i],
  'Отмена и перенос занятий':      [/расписан|гибк|отмен/i],
  'Навязывание услуг':             [/навязыв|дополнительн.*продаж|upsell|апсел/i],
  'Пробный урок':                  [/пробн|бесплатн|вводн/i],
  'Гибкость расписания':           [/гибк|расписан|24\/7|круглосуточн/i],
  'Разговорный клуб':              [/разговорн|speaking|клуб|практик/i],
  'Материалы и ДЗ':                [/материал|методик|учебн|контент/i],
  'Сайт и личный кабинет':         [/интерфейс|личн.*кабинет|сайт|регистрац/i],
  'Репутация компании':            [/репутац|довери|бренд|скандал/i],
  'Прочее':                        []
};
const categoryInMarket = c =>
  (MARKET_KEYWORDS[c] || []).some(re => re.test(marketText));

// --- 3. Присвоение уровней аналитики ---
const observations = [];
const noise = [];
const hypotheses = [];

for (const g of Object.values(groups).sort((a, b) => b.items.length - a.items.length)) {
  const count = g.items.length;
  const crossSchool = g.schools.length >= 2;
  const crossSource = categoryInMarket(g.category);
  const negative = g.types['негатив'] || 0;
  const positive = g.types['позитив'] || 0;
  const dominant = negative > positive ? 'негатив'
                 : positive > negative ? 'позитив' : 'смешанный';

  const signal = {
    category: g.category,
    count: count,
    schools: g.schools,
    platforms: g.platforms,
    months: g.months,
    types: g.types,
    dominant_sentiment: dominant,
    cross_school: crossSchool,
    cross_source: crossSource,
    examples: g.items.slice(0, 4).map(r => '#' + r.id + ' (' + r.school + ', ' + r.date + '): ' + r.text.slice(0, 200)),
    schools_negative: uniq(g.items.filter(r => r.type === 'негатив').map(r => r.school))
  };

  if (count >= MIN_INSIGHT && (crossSchool || crossSource)) {
    // Правило 2+3: повторяется, подтверждается, понятно что делать — ИНСАЙТ
    signal.level = 'ИНСАЙТ (подтверждён: ' + count + ' наблюдений, школ: ' + g.schools.length +
                   (crossSource ? ', + подтверждение из обзора рынка' : '') + ')';
    observations.push(signal);
  } else if (count >= MIN_SIGNAL) {
    // Правило 1: повторяется в нескольких единицах наблюдения — НАБЛЮДЕНИЕ
    signal.level = 'НАБЛЮДЕНИЕ (повторяется: ' + count + ' упоминаний' +
                   (crossSchool ? ', у ' + g.schools.length + ' школ' : '') + ')';
    observations.push(signal);
  } else if (negative >= 1 || crossSource) {
    // Единичное упоминание: выводом быть не может, но и терять его нельзя — ГИПОТЕЗА.
    // Отдельно помечаем случай, когда сигнал всё-таки подтверждён вторым источником.
    signal.level = 'ГИПОТЕЗА (единичное упоминание' +
                   (crossSource ? ', но подтверждено обзором рынка' : ', подтверждений недостаточно') + ')';
    hypotheses.push(signal);
  } else {
    // Единичный нейтральный или позитивный сигнал — ДАННЫЕ, в выводы не идёт
    signal.level = 'ДАННЫЕ (единичный факт, исключён из выводов)';
    noise.push(signal);
  }
}

// --- 4. Уязвимости конкурентов: только повторяющиеся (>=2) негативные сигналы ---
const weaknesses = [];
for (const school of ctx.competitors) {
  const bad = reviews.filter(r => r.school === school && r.type === 'негатив');
  const byCat = {};
  for (const r of bad) byCat[r.category] = (byCat[r.category] || 0) + 1;
  const confirmed = Object.entries(byCat).filter(([, n]) => n >= MIN_SIGNAL)
    .sort((a, b) => b[1] - a[1]);
  if (confirmed.length) {
    weaknesses.push({
      school: school,
      negative_total: bad.length,
      negative_share: reviews.filter(r => r.school === school).length
        ? Math.round(bad.length / reviews.filter(r => r.school === school).length * 100) : 0,
      confirmed: confirmed.map(([c, n]) => ({ category: c, mentions: n })),
      single_mentions: Object.entries(byCat).filter(([, n]) => n < MIN_SIGNAL).map(([c]) => c),
      examples: bad.filter(r => confirmed.some(([c]) => c === r.category))
        .slice(0, 4).map(r => '#' + r.id + ' (' + r.category + '): ' + r.text.slice(0, 180))
    });
  }
}

// --- 5. Сводка по тарифам (первичный источник) ---
const tariffSummary = ctx.competitors.map(school => {
  const rows = tariffs.filter(t => t.school === school);
  const prices = rows.map(r => r.price_per_lesson).filter(Boolean);
  const froms = rows.map(r => r.price_from).filter(Boolean);
  const tos = rows.map(r => r.price_to).filter(Boolean);
  return {
    school: school,
    plans: rows.length,
    // Минимум и максимум считаются ВНУТРИ одной школы, поэтому смешения валют
    // не происходит: у каждой школы своя валюта (Россия — рубли, EnglishDom — гривны).
    currency: uniq(rows.map(r => r.currency).filter(Boolean)).join('/') || '₽',
    price_per_lesson_min: prices.length ? Math.min(...prices) : null,
    price_per_lesson_max: prices.length ? Math.max(...prices) : null,
    price_from_min: froms.length ? Math.min(...froms) : null,
    price_to_max: tos.length ? Math.max(...tos) : null,
    lesson_minutes: uniq(rows.map(r => r.lesson_minutes).filter(Boolean)),
    formats: uniq(rows.map(r => r.format).filter(Boolean)),
    trial: uniq(rows.map(r => r.trial_lesson).filter(Boolean)),
    notes: uniq(rows.map(r => r.notes).filter(Boolean)).slice(0, 6),
    urls: uniq(rows.map(r => r.source_url).filter(Boolean))
  };
});

// --- 6. Упаковка для LLM: только то, что прошло фильтр ---
function tbl(rows) {
  return rows.map(r => '| ' + r.join(' | ') + ' |').join('\n');
}

const monthly = Object.entries(ctx.stats.by_month).sort();

let pack = '# ПОДГОТОВЛЕННЫЙ КОНТЕКСТ ДЛЯ АНАЛИЗА\n\n';
pack += '## Контекст\n';
pack += '- Объект анализа: ' + ctx.object + '\n';
pack += '- Конкуренты: ' + ctx.competitors.join(', ') + '\n';
pack += '- Период данных: ' + ctx.stats.date_range + '\n';
pack += '- Дата подготовки: ' + ctx.prepared_at + '\n';
pack += '- Источники: ' + Object.entries(ctx.sources)
  .map(([k, v]) => v.type + ' (' + v.role + ') — ' + (v.file || k) +
       (v.items ? ', единиц: ' + v.items : '')).join('; ') + '\n\n';

pack += '## Тарифы конкурентов (первичный источник, нормализовано)\n';
pack += '| Школа | Тариф | Занятий | Цена занятия | Валюта | Мин | Макс | Длит., мин | Формат | Пробный | Примечание |\n';
pack += '|---|---|---|---|---|---|---|---|---|---|---|\n';
pack += tbl(tariffs.map(t => [t.school, t.plan, t.lessons,
  t.price_per_lesson || '—', t.currency || '₽', t.price_from || '—', t.price_to || '—',
  t.lesson_minutes || '—', t.format || '—', t.trial_lesson || '—', (t.notes || '').slice(0, 160)])) + '\n\n';

// Предупреждение обязательно: иначе модель складывает гривны с рублями.
const currencies = uniq(tariffs.map(t => t.currency));
if (currencies.length > 1) {
  pack += 'ВНИМАНИЕ К ТАБЛИЦЕ ТАРИФОВ: цены приведены в РАЗНЫХ валютах (колонка «Валюта»). ' +
    'Тарифы EnglishDom — в гривнах (грн), потому что школа работает на украинском рынке; ' +
    'рублёвых тарифов у неё нет. Численно сравнивать гривны с рублями НЕЛЬЗЯ, ' +
    'суммы и средние по разным валютам не считай.\n\n';
}

pack += '## Сводка по тарифам\n';
pack += '| Школа | Тарифов | Валюта | Мин за занятие | Макс за занятие | Длительность | Форматы | Пробный урок |\n|---|---|---|---|---|---|---|---|\n';
pack += tbl(tariffSummary.map(s => [s.school, s.plans, s.currency,
  s.price_per_lesson_min || '—', s.price_per_lesson_max || '—',
  s.lesson_minutes.join('/') || '—', s.formats.join('; ') || '—', s.trial.join('; ') || '—'])) + '\n\n';

pack += '## Отзывы пользователей: частоты (поведенческий источник)\n';
pack += 'Всего отзывов: ' + ctx.stats.reviews_total + '. По школам: ' +
  Object.entries(ctx.stats.by_school).map(([k, v]) => k + ' — ' + v).join(', ') + '.\n';
pack += 'Тональность: ' + Object.entries(ctx.stats.by_type).map(([k, v]) => k + ' — ' + v).join(', ') + '.\n';
pack += 'Площадки: ' + Object.entries(ctx.stats.platforms).map(([k, v]) => k + ' — ' + v).join(', ') + '.\n';
if (monthly.length) pack += 'По месяцам: ' + monthly.map(([m, n]) => m + ' — ' + n).join(', ') + '.\n';
pack += '\n### Повторяющиеся сигналы (прошли фильтр шума, порог >= ' + MIN_SIGNAL + ')\n';
for (const s of observations) {
  pack += '\n**' + s.category + '** — ' + s.level + '\n';
  pack += '  школ: ' + s.schools.join(', ') + '; тональность: ' + s.dominant_sentiment +
          ' (негатив ' + s.types['негатив'] + ', позитив ' + s.types['позитив'] + ', смешанный ' + s.types['смешанный'] + ')\n';
  if (s.months.length) pack += '  месяцы: ' + s.months.join(', ') + '\n';
  for (const e of s.examples) pack += '  - ' + e + '\n';
}
pack += '\n### Сигналы ниже порога (переданы как ГИПОТЕЗЫ, не как выводы)\n';
if (!hypotheses.length) pack += '- нет\n';
for (const h of hypotheses) {
  pack += '- ' + h.category + ' — упоминаний: ' + h.count + ' (школы: ' + h.schools.join(', ') + ')\n';
}
pack += '\n### Единичные факты (ШУМ, в выводы НЕ включать)\n';
if (!noise.length) pack += '- нет\n';
for (const n of noise) {
  pack += '- ' + n.category + ' — 1 упоминание (' + n.schools.join(', ') + ')\n';
}

pack += '\n## Уязвимости конкурентов (повторяющиеся негативные сигналы, >= ' + MIN_SIGNAL + ')\n';
for (const w of weaknesses) {
  pack += '\n**' + w.school + '** — негативных отзывов ' + w.negative_total + ' из ' +
          reviews.filter(r => r.school === w.school).length + ' (' + w.negative_share + '%)\n';
  for (const c of w.confirmed) pack += '  - ' + c.category + ' — подтверждено ' + c.mentions + ' отзывами\n';
  if (w.single_mentions.length) pack += '  - единичные жалобы (не выводы): ' + w.single_mentions.join(', ') + '\n';
  for (const e of w.examples) pack += '  - пример: ' + e + '\n';
}

pack += '\n## Отраслевой обзор рынка (вторичный источник, полный текст)\n';
pack += marketText + '\n';

return [{
  json: {
    context: ctx,
    analytics_pack: pack,
    counts: {
      reviews: reviews.length, tariffs: tariffs.length,
      observations: observations.length, hypotheses: hypotheses.length,
      noise_excluded: noise.length, weaknesses: weaknesses.length
    },
    observations: observations, hypotheses: hypotheses, noise: noise,
    weaknesses: weaknesses, tariff_summary: tariffSummary
  }
}];
