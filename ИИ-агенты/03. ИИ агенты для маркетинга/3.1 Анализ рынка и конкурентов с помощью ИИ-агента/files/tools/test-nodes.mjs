// Локальная проверка JS-кода узлов n8n без сервера.
// Эмулирует окружение Code-узла: $input, $, $now.
// Запуск: node tools/test-nodes.mjs
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');
const DATA = path.join(ROOT, 'data');
// Промежуточные результаты прогона пишем в tmp/, а не в data/: data/ — это
// исходные данные агента, их не должен засорять тестовый прогон.
const TMP = path.join(ROOT, 'tmp');
fs.mkdirSync(TMP, { recursive: true });

const read = f => fs.readFileSync(path.join(HERE, f), 'utf8');
const readData = f => {
  const p = path.join(DATA, f);
  return fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : '';
};

// --- эмуляция узла: выполняем jsCode с подставленными $input / $ ------------
function runNode(jsCode, items, nodeResolver) {
  const $input = { all: () => items, first: () => items[0], item: items[0] };
  const $ = name => {
    const r = nodeResolver(name);
    if (!r) throw new Error('Нет узла с именем: ' + name);
    return r;
  };
  const $now = {
    setZone: () => ({ toFormat: (fmt) => fmt.replace('yyyy', '2026').replace('MM', '09')
      .replace('dd', '23').replace('HH', '12').replace('mm', '00') })
  };
  const $json = (items[0] && items[0].json) || {};
  const $item = items[0] || { json: {} };
  const ctx = vm.createContext({ $input, $, $json, $item, $now, console, JSON, Date, Math, String, Number, Object, Array, RegExp, parseFloat, parseInt, isNaN, Set, Boolean });
  const fn = new vm.Script('(function(){' + jsCode + '})()');
  return fn.runInContext(ctx).map(o => o.json ? o : { json: o });
}

const files = {
  '1. Тарифы (текст)': { data: readData('tariffs.csv') },
  '2. Отзывы (текст)': { data: readData('reviews.csv') },
  '3. Обзор рынка (текст)': { data: readData('market-review.md') }
};
const resolver = name => {
  if (!files[name]) return null;
  return { first: () => ({ json: files[name] }), all: () => [{ json: files[name] }], item: { json: files[name] } };
};

console.log('=== Узел 1: Нормализация данных ===');
let out;
try {
  out = runNode(read('01-normalize.js'), [{ json: {} }], resolver);
} catch (e) {
  console.error('ОШИБКА:', e.message);
  process.exit(1);
}
const ctx = out[0].json.context;
console.log('тарифов:', ctx.normalized.tariffs.length);
console.log('отзывов:', ctx.normalized.reviews.length);
console.log('период:', ctx.stats.date_range);
console.log('по школам:', ctx.stats.by_school);
console.log('тональность:', ctx.stats.by_type);
console.log('площадки:', ctx.stats.platforms);
console.log('категории:', ctx.stats.by_category.map(c => c.category + '=' + c.total).join(', '));
if (ctx.normalized.reviews.some(r => !r.school || r.school === '')) console.log('!!! есть отзывы без школы');
if (ctx.normalized.reviews.some(r => r.category === 'Прочее')) {
  console.log('!!! категория «Прочее» у:', ctx.normalized.reviews.filter(r => r.category === 'Прочее').map(r => r.id).join(','));
}

console.log('\n=== Узел 2: Фильтрация и группировка ===');
const items2 = [{ json: { context: ctx, context_json: JSON.stringify(ctx) } }];
let out2;
try {
  out2 = runNode(read('02-filter-group.js'), items2, resolver);
} catch (e) {
  console.error('ОШИБКА:', e.message);
  process.exit(1);
}
const j2 = out2[0].json;
console.log('счётчики:', j2.counts);
console.log('\nНАБЛЮДЕНИЯ/ИНСАЙТЫ:');
j2.observations.forEach(o => console.log('  -', o.category, '|', o.count, '|', o.level));
console.log('\nГИПОТЕЗЫ:');
j2.hypotheses.forEach(h => console.log('  -', h.category, '|', h.count));
console.log('\nШУМ (исключено):');
j2.noise.forEach(n => console.log('  -', n.category, '|', n.count));
console.log('\nУЯЗВИМОСТИ:');
j2.weaknesses.forEach(w => console.log('  -', w.school, '| негатив', w.negative_total, '|', w.confirmed.map(c => c.category + '(' + c.mentions + ')').join(', ')));

const packPath = path.join(TMP, 'analytics-pack.md');
fs.writeFileSync(packPath, j2.analytics_pack, 'utf8');
console.log('\nanalytics_pack сохранён:', packPath, '(' + j2.analytics_pack.length + ' символов)');

// сохраняем context для повторного использования
fs.writeFileSync(path.join(TMP, 'context.json'), JSON.stringify(j2, null, 2), 'utf8');
console.log('результат узла 2 сохранён: tmp/context.json');
